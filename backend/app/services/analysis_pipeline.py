"""Pipeline service orchestrating end-to-end repository analysis stages."""

import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.core.github_client import get_github_client
from backend.app.core.jobs import update_job
from backend.app.db.models import Analysis, Result, StageRun
from backend.app.db.session import SessionLocal
from backend.app.errors import AppError

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

        # Store in results[repository]
        result_repo = db.query(Result).filter(
            Result.analysis_id == analysis_id,
            Result.module == "repository",
        ).first()

        if result_repo:
            result_repo.payload = metadata_payload
        else:
            result_repo = Result(
                analysis_id=analysis_id,
                module="repository",
                payload=metadata_payload,
                model_versions={},
            )
            db.add(result_repo)

        stage_metadata.status = "completed"
        stage_metadata.finished_at = datetime.now(timezone.utc)
        db.commit()

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
        db.close()
