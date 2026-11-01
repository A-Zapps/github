"""Jobs status and progress polling API endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.models import Job
from backend.app.db.session import get_db
from backend.app.errors import AppError

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Fetch live status, current stage, and progress percentage for a background job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise AppError("NOT_FOUND", f"Job '{job_id}' not found.", status_code=404)

    return {
        "data": {
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "progress": job.progress,
            "stage": job.stage,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "payload": job.payload,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        },
        "meta": {
            "analysis_id": job.payload.get("analysis_id"),
            "head_sha": job.payload.get("head_sha"),
            "analyzer_version": "1.0.0",
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
