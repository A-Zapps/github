"""Pipeline service orchestrating end-to-end repository analysis stages."""

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.analyzers.duplication import detect_duplication
from backend.app.analyzers.inventory import scan_inventory
from backend.app.analyzers.lint_python import analyze_python_lint
from backend.app.analyzers.metrics import analyze_repository_metrics
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
        update_job(db, job_id, status="running", progress=85, stage="quality")
        quality_data = calculate_quality_scores(inventory_data, metrics_data, duplication_data, lint_data)
        save_result("quality", quality_data)

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
