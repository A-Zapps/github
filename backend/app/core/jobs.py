"""Job tracking and asynchronous execution manager."""

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import Job

logger = logging.getLogger(__name__)


def generate_job_id() -> str:
    """Generate a unique job identifier."""
    return str(uuid.uuid4())


def create_job(
    db: Session,
    job_type: str,
    payload: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Job:
    """Create a new job record in queued status."""
    jid = job_id or generate_job_id()
    job = Job(
        id=jid,
        type=job_type,
        status="queued",
        progress=0,
        stage="queued",
        payload=payload or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(
    db: Session,
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Job]:
    """Update progress and status of an existing job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None

    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if stage is not None:
        job.stage = stage
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    if payload is not None:
        merged = dict(job.payload)
        merged.update(payload)
        job.payload = merged

    db.commit()
    db.refresh(job)
    return job


def cleanup_stale_jobs_on_startup(db: Session) -> int:
    """Mark any leftover 'running' or 'queued' jobs as failed after server restart (ARCHITECTURE 13)."""
    running_jobs = db.query(Job).filter(Job.status.in_(["running", "queued"])).all()
    count = len(running_jobs)
    for job in running_jobs:
        job.status = "failed"
        job.error_code = "SERVER_RESTARTED"
        job.error_message = "Job failed because the application server was restarted."
    if count > 0:
        db.commit()
        logger.info("Marked %d stale jobs as failed on startup.", count)
    return count
