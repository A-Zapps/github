"""Pipeline service orchestrating end-to-end repository analysis stages."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.core.github_client import get_github_client
from backend.app.core.jobs import update_job
from backend.app.db.models import Analysis, StageRun
from backend.app.db.session import SessionLocal

logger = logging.getLogger(__name__)
ANALYZER_VERSION = "1.0.0"


async def execute_analysis_pipeline(analysis_id: int, job_id: str, repo_name: str) -> None:
    """Run the end-to-end analysis stages in the background."""
    db: Session = SessionLocal()
    github = get_github_client()

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

        default_branch = repo_info.get("default_branch", "main")
        branch_info = await github.request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}",
            db=db,
        )
        head_sha = branch_info.get("sha", "0000000000000000000000000000000000000000")

        # Update Analysis record with resolved commit and branch
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.head_sha = head_sha
            analysis.default_branch = default_branch
            analysis.status = "running"
            db.commit()

        stage_resolve.status = "completed"
        stage_resolve.finished_at = datetime.now(timezone.utc)
        db.commit()

        update_job(db, job_id, status="running", progress=30, stage="metadata")

        # Additional stages (metadata, clone, metrics, etc.) will be added in T1.3, T1.4
        # Complete job
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
        logger.info("Analysis %d for %s succeeded.", analysis_id, repo_name)

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
