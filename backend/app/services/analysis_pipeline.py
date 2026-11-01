"""Pipeline service orchestrating end-to-end repository analysis stages."""

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.analyzers.deps_vulns import analyze_dependencies_vulnerabilities
from backend.app.analyzers.developer_stats import compute_developer_statistics
from backend.app.analyzers.duplication import detect_duplication
from backend.app.analyzers.inventory import scan_inventory
from backend.app.analyzers.lint_python import analyze_python_lint
from backend.app.analyzers.metrics import analyze_repository_metrics
from backend.app.analyzers.readme_parser import parse_and_score_readme
from backend.app.analyzers.secrets import scan_repository_secrets
from backend.app.analyzers.semgrep_runner import run_semgrep_analysis
from backend.app.config import get_settings
from backend.app.core.github_client import get_github_client
from backend.app.core.jobs import update_job
from backend.app.core.sandbox import (
    cleanup_work_dir,
    clone_bare_repo,
    create_work_dir,
    materialize_tree,
)
from backend.app.db.models import Analysis, Result, StageRun
from backend.app.db.session import SessionLocal
from backend.app.errors import AppError
from backend.app.ml.features import (
    compute_file_history_features,
    compute_repo_history_features,
    parse_git_log_history,
)
from backend.app.ml.registry import get_model_registry
from backend.app.recommend.rules import generate_recommendations
from backend.app.services.quality_service import calculate_quality_scores

logger = logging.getLogger(__name__)
ANALYZER_VERSION = "1.0.0"


async def fetch_repository_metadata(github, owner: str, repo: str, db: Session) -> Dict[str, Any]:
    """Execute Stage 2: Retrieve metadata, languages, issues, PRs, and commit activity."""
    # 1. Base repository information
    repo_info = await github.request("GET", f"https://api.github.com/repos/{owner}/{repo}", db=db)

    # 2. Languages breakdown
    languages_raw = await github.request("GET", f"https://api.github.com/repos/{owner}/{repo}/languages", db=db)
    total_bytes = sum(languages_raw.values()) or 1
    languages_pct = {
        lang: round((count / total_bytes) * 100, 2)
        for lang, count in languages_raw.items()
    }

    # 3. Contributors (capped at 100)
    try:
        contributors = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            params={"per_page": 100},
            db=db,
        )
        contributors_count = len(contributors) if isinstance(contributors, list) else 0
    except Exception:
        contributors = []
        contributors_count = 0

    # 4. Releases (capped at 100)
    try:
        releases = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/releases",
            params={"per_page": 100},
            db=db,
        )
        releases_count = len(releases) if isinstance(releases, list) else 0
    except Exception:
        releases = []
        releases_count = 0

    # 5. Issues & PRs (sample capped at 500)
    open_issues = 0
    closed_issues = 0
    open_prs = 0
    closed_prs = 0
    issues_truncated = False

    try:
        issues_raw = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            params={"state": "all", "per_page": 100},
            db=db,
        )
        if isinstance(issues_raw, list):
            for item in issues_raw:
                is_pr = "pull_request" in item
                is_open = item.get("state") == "open"
                if is_pr:
                    if is_open:
                        open_prs += 1
                    else:
                        closed_prs += 1
                else:
                    if is_open:
                        open_issues += 1
                    else:
                        closed_issues += 1
    except Exception:
        pass

    # 6. Weekly Commit Activity (52 weeks)
    try:
        commit_activity = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity",
            db=db,
        )
        if not isinstance(commit_activity, list):
            commit_activity = []
    except Exception:
        commit_activity = []

    # 7. README content
    readme_text = ""
    readme_path = "README.md"
    try:
        readme_data = await github.request("GET", f"https://api.github.com/repos/{owner}/{repo}/readme", db=db)
        if isinstance(readme_data, dict):
            readme_path = readme_data.get("name", "README.md")
            raw_content = readme_data.get("content", "")
            if readme_data.get("encoding") == "base64" and raw_content:
                readme_text = base64.b64decode(raw_content).decode("utf-8", errors="replace")
            else:
                readme_text = raw_content
    except Exception:
        readme_text = ""

    license_info = repo_info.get("license")
    license_spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None

    return {
        "full_name": repo_info.get("full_name", f"{owner}/{repo}"),
        "description": repo_info.get("description", ""),
        "stars": repo_info.get("stargazers_count", 0),
        "forks": repo_info.get("forks_count", 0),
        "watchers": repo_info.get("subscribers_count", repo_info.get("watchers_count", 0)),
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "open_prs": open_prs,
        "closed_prs": closed_prs,
        "default_branch": repo_info.get("default_branch", "main"),
        "size_kb": repo_info.get("size", 0),
        "license": license_spdx,
        "languages": languages_pct,
        "languages_bytes": languages_raw,
        "contributors_count": contributors_count,
        "releases_count": releases_count,
        "commit_activity_52w": commit_activity,
        "readme": {
            "path": readme_path,
            "content": readme_text,
        },
        "truncated": {
            "issues": issues_truncated,
            "prs": False,
        },
    }


async def execute_analysis_pipeline(analysis_id: int, job_id: str, repo_name: str) -> None:
    """Run the end-to-end analysis stages in the background."""
    db: Session = SessionLocal()
    github = get_github_client()
    settings = get_settings()
    work_dir: Optional[str] = None

    try:
        update_job(db, job_id, status="running", progress=10, stage="resolve")

        # Stage 1: Resolve repository metadata
        stage_resolve = StageRun(
            analysis_id=analysis_id,
            stage="resolve",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_resolve)
        db.commit()

        owner, repo = repo_name.split("/", 1)
        repo_info = await github.request("GET", f"https://api.github.com/repos/{owner}/{repo}", db=db)

        # Check repository size limit (ARCHITECTURE 7)
        size_kb = repo_info.get("size", 0)
        if size_kb > settings.MAX_REPO_SIZE_MB * 1024:
            raise AppError(
                "REPO_TOO_LARGE",
                f"Repository size ({size_kb // 1024} MB) exceeds maximum allowed {settings.MAX_REPO_SIZE_MB} MB.",
                status_code=400,
            )

        default_branch = repo_info.get("default_branch", "main")
        branch_info = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}",
            db=db,
        )
        head_sha = branch_info.get("sha", "0000000000000000000000000000000000000000")

        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.head_sha = head_sha
            analysis.default_branch = default_branch
            analysis.status = "running"
            db.commit()

        stage_resolve.status = "completed"
        stage_resolve.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 2: Metadata collection
        update_job(db, job_id, status="running", progress=25, stage="metadata")
        stage_metadata = StageRun(
            analysis_id=analysis_id,
            stage="metadata",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_metadata)
        db.commit()

        metadata_payload = await fetch_repository_metadata(github, owner, repo, db)

        # Helper to upsert module result
        def save_result(mod: str, payload_data: Dict[str, Any]) -> None:
            res_rec = db.query(Result).filter(
                Result.analysis_id == analysis_id,
                Result.module == mod,
            ).first()
            if res_rec:
                res_rec.payload = payload_data
            else:
                res_rec = Result(
                    analysis_id=analysis_id,
                    module=mod,
                    payload=payload_data,
                    model_versions={},
                )
                db.add(res_rec)
            db.commit()

        save_result("repository", metadata_payload)

        stage_metadata.status = "completed"
        stage_metadata.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Setup working directory for sandboxed file operations
        work_dir = create_work_dir(analysis_id)
        git_dir = str(Path(work_dir) / "git")
        src_dir = str(Path(work_dir) / "src")

        # Stage 3: Clone
        update_job(db, job_id, status="running", progress=35, stage="clone")
        stage_clone = StageRun(
            analysis_id=analysis_id,
            stage="clone",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_clone)
        db.commit()

        clone_bare_repo(repo_name, git_dir, token=settings.GITHUB_TOKEN)
        stage_clone.status = "completed"
        stage_clone.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 4: Materialize
        update_job(db, job_id, status="running", progress=45, stage="materialize")
        stage_mat = StageRun(
            analysis_id=analysis_id,
            stage="materialize",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_mat)
        db.commit()

        mat_info = materialize_tree(
            git_dir=git_dir,
            target_src_dir=src_dir,
            head_sha=head_sha,
            max_files=settings.MAX_FILES,
            max_file_kb=settings.MAX_FILE_KB,
        )
        stage_mat.status = "completed"
        stage_mat.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Update repository record if file tree was truncated
        if mat_info.get("truncated"):
            metadata_payload["truncated"] = metadata_payload.get("truncated", {})
            metadata_payload["truncated"]["files"] = True
            metadata_payload["truncated"]["materialized_count"] = mat_info.get("materialized_count", 0)
            save_result("repository", metadata_payload)

        # Stage 5: Metrics (Inventory, Lizard, Radon, Duplication)
        update_job(db, job_id, status="running", progress=60, stage="metrics")
        stage_metrics = StageRun(
            analysis_id=analysis_id,
            stage="metrics",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_metrics)
        db.commit()

        inventory_data = scan_inventory(src_dir)
        source_files = [f["path"] for f in inventory_data.get("files", [])]
        metrics_data = analyze_repository_metrics(Path(src_dir), source_files)
        duplication_data = detect_duplication(Path(src_dir), source_files)

        quality_raw = {
            "inventory": inventory_data,
            "metrics": metrics_data,
            "duplication": duplication_data,
            "materialize": mat_info,
        }
        save_result("quality_raw", quality_raw)

        stage_metrics.status = "completed"
        stage_metrics.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 6: Lint (Pylint and Bandit on sampled Python files)
        update_job(db, job_id, status="running", progress=75, stage="lint")
        stage_lint = StageRun(
            analysis_id=analysis_id,
            stage="lint",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_lint)
        db.commit()

        python_files = [f for f in source_files if f.lower().endswith(".py")]
        lint_data = analyze_python_lint(Path(src_dir), python_files)
        save_result("lint", lint_data)

        stage_lint.status = "completed"
        stage_lint.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Calculate Quality Scores & Tech Debt
        update_job(db, job_id, status="running", progress=80, stage="quality")
        quality_data = calculate_quality_scores(inventory_data, metrics_data, duplication_data, lint_data)
        quality_data["truncated"] = mat_info.get("truncated", False)
        quality_data["materialized_count"] = mat_info.get("materialized_count", len(source_files))
        save_result("quality", quality_data)

        # Stage 7: Security (Secrets scan, Semgrep, OSV dependencies)
        update_job(db, job_id, status="running", progress=90, stage="security")
        stage_sec = StageRun(
            analysis_id=analysis_id,
            stage="security",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_sec)
        db.commit()

        secrets_data = scan_repository_secrets(Path(src_dir), source_files)
        semgrep_data = run_semgrep_analysis(Path(src_dir))
        deps_data = await analyze_dependencies_vulnerabilities(Path(src_dir))

        bandit_findings = lint_data.get("bandit", {}).get("findings", [])
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        code_findings = []

        for b in bandit_findings:
            sev = b.get("severity", "LOW").upper()
            if sev in sev_counts:
                sev_counts[sev] += 1
            code_findings.append({
                "source": "Bandit",
                "file": b.get("file"),
                "line": b.get("line"),
                "rule_id": b.get("test_id"),
                "severity": sev,
                "message": b.get("text"),
            })

        for s in semgrep_data.get("findings", []):
            sev = s.get("severity", "WARNING").upper()
            norm_sev = "HIGH" if sev == "ERROR" else "MEDIUM" if sev == "WARNING" else "LOW"
            sev_counts[norm_sev] += 1
            code_findings.append({
                "source": "Semgrep",
                "file": s.get("file"),
                "line": s.get("line"),
                "rule_id": s.get("check_id"),
                "severity": norm_sev,
                "message": s.get("message"),
            })

        for _ in secrets_data.get("findings", []):
            sev_counts["HIGH"] += 1

        for v in deps_data.get("vulnerabilities", []):
            sev_counts["HIGH"] += len(v.get("advisories", []))

        security_payload = {
            "severity_summary": sev_counts,
            "total_issues": sum(sev_counts.values()),
            "code_findings": code_findings,
            "secrets": secrets_data,
            "dependencies": deps_data,
            "semgrep_status": semgrep_data.get("status", "skipped"),
        }
        save_result("security", security_payload)

        stage_sec.status = "completed"
        stage_sec.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 8: History (git log --numstat per file and repo)
        update_job(db, job_id, status="running", progress=92, stage="history")
        stage_hist = StageRun(
            analysis_id=analysis_id,
            stage="history",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_hist)
        db.commit()

        cutoff_now = datetime.now(timezone.utc)
        history_raw = parse_git_log_history(git_dir, cutoff_date=cutoff_now)
        file_history = compute_file_history_features(history_raw, cutoff_now)
        repo_history = compute_repo_history_features(history_raw, cutoff_now)

        history_payload = {
            "total_commits": history_raw.get("total_commits", 0),
            "past_commits_count": history_raw.get("past_commits_count", 0),
            "file_history": file_history,
            "repo_history": repo_history,
        }
        save_result("history", history_payload)

        stage_hist.status = "completed"
        stage_hist.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 9: Predict (bug_risk, maintenance_effort, repo_health, repo_clusters)
        update_job(db, job_id, status="running", progress=96, stage="predict")
        stage_predict = StageRun(
            analysis_id=analysis_id,
            stage="predict",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_predict)
        db.commit()

        registry = get_model_registry()

        # Build feature rows for analyzed files
        lizard_files = metrics_data.get("files", [])
        file_feature_rows = []
        file_paths = []

        for f in lizard_files:
            rel_path = f.get("filename", "")
            hist = file_history.get(rel_path, {})
            loc_val = f.get("nloc", f.get("loc", 0))
            is_test = 1 if rel_path.lower().startswith("test") or "test" in rel_path.lower() else 0

            row = {
                "loc": loc_val,
                "nloc": f.get("nloc", loc_val),
                "n_functions": len(f.get("functions", [])),
                "ccn_max": f.get("max_ccn", 1.0),
                "ccn_mean": f.get("avg_ccn", 1.0),
                "ccn_p90": f.get("avg_ccn", 1.0) * 1.5,
                "token_count": f.get("token_count", loc_val * 5),
                "params_max": 2,
                "commits_12m": hist.get("commits_12m", 0),
                "authors_12m": hist.get("authors_12m", 0),
                "lines_added_12m": hist.get("lines_added_12m", 0),
                "lines_deleted_12m": hist.get("lines_deleted_12m", 0),
                "churn_ratio": hist.get("churn_ratio", 0.0),
                "days_since_last_change": hist.get("days_since_last_change", 365.0),
                "bugfix_commits_12m": hist.get("bugfix_commits_12m", 0),
                "age_days_capped": hist.get("age_days_capped", 365.0),
                "is_test": is_test,
            }
            file_feature_rows.append(row)
            file_paths.append(rel_path)

        # 1. Bug Risk
        file_bugs_list = []
        bug_counts = {"high": 0, "medium": 0, "low": 0}
        if registry.is_model_trained("bug_risk") and file_feature_rows:
            try:
                bug_preds = registry.predict_bug_risk(file_feature_rows)
                for path, feat, pred in zip(file_paths, file_feature_rows, bug_preds):
                    tier = pred["risk_tier"]
                    bug_counts[tier] = bug_counts.get(tier, 0) + 1

                    drivers = []
                    if feat["ccn_max"] >= 10:
                        drivers.append(f"High CCN ({feat['ccn_max']})")
                    if feat["churn_ratio"] >= 2.0:
                        drivers.append(f"High churn ({feat['churn_ratio']})")
                    if feat["loc"] >= 300:
                        drivers.append(f"Large file ({feat['loc']} LOC)")
                    if feat["bugfix_commits_12m"] >= 1:
                        drivers.append(f"Recent bugfixes ({feat['bugfix_commits_12m']})")
                    if not drivers:
                        drivers.append("Low historical stability")

                    file_bugs_list.append({
                        "file": path,
                        "risk_tier": tier,
                        "probability": pred["probability"],
                        "drivers": drivers[:3],
                        "ccn_max": feat["ccn_max"],
                        "loc": feat["loc"],
                    })
                bugs_payload = {
                    "status": "ready",
                    "model_name": "bug_risk",
                    "model_version": "1.0.0",
                    "files": file_bugs_list,
                    "summary": {
                        "total_files": len(file_bugs_list),
                        "high_risk": bug_counts["high"],
                        "medium_risk": bug_counts["medium"],
                        "low_risk": bug_counts["low"],
                    },
                }
            except Exception as e:
                logger.warning("Bug risk prediction failed: %s", e)
                bugs_payload = {"status": "error", "error": str(e), "files": [], "summary": {}}
        else:
            bugs_payload = {"status": "MODEL_NOT_TRAINED", "files": [], "summary": {}}
        save_result("bugs", bugs_payload)

        # 2. Maintenance Effort
        if registry.is_model_trained("maintenance_effort") and file_feature_rows:
            try:
                maint_preds = registry.predict_maintenance_effort(file_feature_rows)
                total_churn = sum(p["predicted_churn_lines"] for p in maint_preds)
                quality_data["maintenance_effort"] = {
                    "status": "ready",
                    "model_version": "1.0.0",
                    "predicted_total_churn_lines_6m": round(total_churn, 1),
                }
            except Exception as e:
                logger.warning("Maintenance effort prediction failed: %s", e)
                quality_data["maintenance_effort"] = {"status": "error"}
        else:
            quality_data["maintenance_effort"] = {"status": "MODEL_NOT_TRAINED"}

        # 3. Repo Health & 4. Repo Clusters
        repo_health_data = {}
        if registry.is_model_trained("repo_health"):
            try:
                health_input = {
                    **repo_history,
                    "total_files": inventory_data.get("total_files", 0),
                    "total_loc": inventory_data.get("total_loc", 0),
                    "avg_maintainability": metrics_data.get("summary", {}).get("avg_mi", 75.0),
                }
                health_pred = registry.predict_repo_health(health_input)
                repo_health_data["health"] = health_pred
                repo_health_data["status"] = "ready"
            except Exception as e:
                logger.warning("Repo health prediction failed: %s", e)
                repo_health_data["health"] = {"status": "error"}
                repo_health_data["status"] = "error"
        else:
            repo_health_data["health"] = {"status": "MODEL_NOT_TRAINED"}
            repo_health_data["status"] = "MODEL_NOT_TRAINED"

        if registry.is_model_trained("repo_clusters"):
            try:
                cluster_input = {
                    "total_files": inventory_data.get("total_files", 0),
                    "total_loc": inventory_data.get("total_loc", 0),
                    "avg_maintainability": metrics_data.get("summary", {}).get("avg_mi", 75.0),
                    "duplication_pct": duplication_data.get("duplicate_ratio_pct", 0.0),
                    "test_ratio": (inventory_data.get("test_files", 0) / max(1, inventory_data.get("total_files", 1))),
                    "commits_per_month_mean": repo_history.get("commits_per_month_mean", 0.0),
                    "distinct_authors": repo_history.get("distinct_authors", 0),
                    "bus_factor": repo_history.get("bus_factor", 0),
                }
                cluster_pred = registry.predict_repo_clusters(cluster_input)
                repo_health_data["clusters"] = cluster_pred
                quality_data["corpus_percentiles"] = cluster_pred.get("corpus_percentiles", {})
            except Exception as e:
                logger.warning("Repo clusters prediction failed: %s", e)
                repo_health_data["clusters"] = {"status": "error"}
        else:
            repo_health_data["clusters"] = {"status": "MODEL_NOT_TRAINED"}

        repo_health_data["signals"] = repo_history
        save_result("health", repo_health_data)
        save_result("quality", quality_data)

        stage_predict.status = "completed"
        stage_predict.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 10: Docs (README parse, section classifier, score)
        update_job(db, job_id, status="running", progress=98, stage="docs")
        stage_docs = StageRun(
            analysis_id=analysis_id,
            stage="docs",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_docs)
        db.commit()

        docs_data = parse_and_score_readme(Path(src_dir))
        save_result("docs", docs_data)

        stage_docs.status = "completed"
        stage_docs.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 11: Developers (Contributor and activity analytics)
        update_job(db, job_id, status="running", progress=99, stage="developers")
        stage_devs = StageRun(
            analysis_id=analysis_id,
            stage="developers",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_devs)
        db.commit()

        dev_stats = compute_developer_statistics(
            commits=history_raw.get("window_commits", []),
            pull_requests=metadata_payload.get("pull_requests", []),
            issues=metadata_payload.get("issues", []),
        )
        save_result("developers", dev_stats)

        stage_devs.status = "completed"
        stage_devs.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Stage 12: Recommendations (Rule engine over results 5 to 11)
        update_job(db, job_id, status="running", progress=99, stage="recommend")
        stage_recs = StageRun(
            analysis_id=analysis_id,
            stage="recommend",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_recs)
        db.commit()

        results_dict = {
            "quality": quality_data,
            "security": security_payload,
            "bugs": bugs_payload,
            "docs": docs_data,
            "developers": dev_stats,
        }
        recs_list = generate_recommendations(results_dict)
        save_result("recommendations", {"recommendations": recs_list, "total": len(recs_list)})

        stage_recs.status = "completed"
        stage_recs.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Build Assistant Vector Index if enabled (ARCHITECTURE 11)
        if settings.ENABLE_ASSISTANT_INDEX:
            try:
                from backend.app.rag.chunker import chunk_repository
                from backend.app.rag.embedder import get_embedder
                from backend.app.rag.store import save_chunks_to_db

                repo_chunks = chunk_repository(
                    src_dir=Path(src_dir),
                    source_files=source_files,
                    lizard_files=metrics_data.get("files", []),
                )
                if repo_chunks:
                    emb = get_embedder()
                    chunk_texts = [c["text"] for c in repo_chunks]
                    embeddings = emb.embed_texts(chunk_texts)
                    save_chunks_to_db(db, analysis_id, repo_chunks, embeddings)
            except Exception as e:
                logger.warning("Assistant indexing failed for analysis %d: %s", analysis_id, e)

        # Update analysis and job status
        if analysis:
            analysis.status = "completed"
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()

        update_job(
            db,
            job_id,
            status="succeeded",
            progress=100,
            stage="completed",
            payload={"head_sha": head_sha, "default_branch": default_branch},
        )
        logger.info("Analysis %d for %s completed successfully.", analysis_id, repo_name)

    except Exception as exc:
        logger.exception("Analysis pipeline failed for %s: %s", repo_name, exc)
        err_code = getattr(exc, "code", "STAGE_FAILED")
        err_msg = str(getattr(exc, "message", exc))

        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()

        update_job(
            db,
            job_id,
            status="failed",
            error_code=err_code,
            error_message=err_msg,
        )
    finally:
        if work_dir:
            cleanup_work_dir(work_dir)
        db.close()
