"""Analysis endpoints for enqueuing and inspecting repository analyses."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from backend.app.core.jobs import create_job
from backend.app.core.repo_validation import normalize_and_validate_repo_name
from backend.app.db.models import Analysis, Repository, Result
from backend.app.db.session import get_db
from backend.app.errors import AppError
from backend.app.schemas.analyses import AnalyzeRequest
from backend.app.services.analysis_pipeline import ANALYZER_VERSION, execute_analysis_pipeline

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(payload: AnalyzeRequest, response: Response, db: Session = Depends(get_db)):
    """Validate repository name and launch an asynchronous analysis pipeline."""
    repo_name = normalize_and_validate_repo_name(payload.repo)

    # Get or create repository record
    repository = db.query(Repository).filter(Repository.full_name == repo_name).first()
    if not repository:
        repository = Repository(full_name=repo_name)
        db.add(repository)
        db.commit()
        db.refresh(repository)

    # Create new analysis entry
    analysis = Analysis(
        repository_id=repository.id,
        head_sha="pending",
        default_branch="main",
        analyzer_version=ANALYZER_VERSION,
        status="pending",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Create background tracking job
    job = create_job(db, job_type="analysis", payload={"analysis_id": analysis.id, "repo": repo_name})

    # Trigger async execution
    asyncio.create_task(execute_analysis_pipeline(analysis.id, job.id, repo_name))

    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "data": {
            "analysis_id": analysis.id,
            "job_id": job.id,
            "repo": repo_name,
            "cached": False,
        },
        "meta": {
            "analysis_id": analysis.id,
            "head_sha": None,
            "analyzer_version": ANALYZER_VERSION,
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("")
def list_analyses(limit: int = 10, db: Session = Depends(get_db)):
    """List recent repository analyses."""
    analyses = (
        db.query(Analysis)
        .order_by(Analysis.created_at.desc())
        .limit(limit)
        .all()
    )
    data = []
    for a in analyses:
        data.append({
            "id": a.id,
            "repo": a.repository.full_name if a.repository else "unknown",
            "head_sha": a.head_sha,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "finished_at": a.finished_at.isoformat() if a.finished_at else None,
        })
    return {
        "data": data,
        "meta": {
            "analysis_id": None,
            "head_sha": None,
            "analyzer_version": ANALYZER_VERSION,
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/{analysis_id}/repository")
def get_repository_data(analysis_id: int, db: Session = Depends(get_db)):
    """Fetch F1 repository details and metadata from results[repository]."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)

    result = db.query(Result).filter(
        Result.analysis_id == analysis_id,
        Result.module == "repository",
    ).first()

    if not result:
        raise AppError("ANALYSIS_NOT_READY", "Repository metadata is still processing.", status_code=409)

    return {
        "data": result.payload,
        "meta": {
            "analysis_id": analysis.id,
            "head_sha": analysis.head_sha,
            "analyzer_version": analysis.analyzer_version,
            "model_versions": result.model_versions or {},
            "generated_at": result.created_at.isoformat() if result.created_at else datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/{analysis_id}")
def get_analysis_summary(analysis_id: int, db: Session = Depends(get_db)):
    """Get high-level summary of a specific analysis."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)

    stages = [
        {"stage": s.stage, "status": s.status, "error": s.error_code}
        for s in analysis.stage_runs
    ]

    return {
        "data": {
            "id": analysis.id,
            "repo": analysis.repository.full_name if analysis.repository else "unknown",
            "head_sha": analysis.head_sha,
            "default_branch": analysis.default_branch,
            "status": analysis.status,
            "stages": stages,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "finished_at": analysis.finished_at.isoformat() if analysis.finished_at else None,
        },
        "meta": {
            "analysis_id": analysis.id,
            "head_sha": analysis.head_sha,
            "analyzer_version": analysis.analyzer_version,
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/{analysis_id}/quality")
def get_quality_data(analysis_id: int, db: Session = Depends(get_db)):
    """Fetch F2 Code Quality metrics, components, tech debt, and worst files."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)

    result = db.query(Result).filter(
        Result.analysis_id == analysis_id,
        Result.module == "quality",
    ).first()

    if not result:
        raise AppError("ANALYSIS_NOT_READY", "Code quality data is still processing.", status_code=409)

    return {
        "data": result.payload,
        "meta": {
            "analysis_id": analysis.id,
            "head_sha": analysis.head_sha,
            "analyzer_version": analysis.analyzer_version,
            "model_versions": result.model_versions or {},
            "generated_at": result.created_at.isoformat() if result.created_at else datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/{analysis_id}/security")
def get_security_data(analysis_id: int, db: Session = Depends(get_db)):
    """Fetch F3 Security analysis findings (Bandit, Semgrep, secrets, dependency CVEs)."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)

    result = db.query(Result).filter(
        Result.analysis_id == analysis_id,
        Result.module == "security",
    ).first()

    if not result:
        raise AppError("ANALYSIS_NOT_READY", "Security analysis data is still processing.", status_code=409)

    return {
        "data": result.payload,
        "meta": {
            "analysis_id": analysis.id,
            "head_sha": analysis.head_sha,
            "analyzer_version": analysis.analyzer_version,
            "model_versions": result.model_versions or {},
            "generated_at": result.created_at.isoformat() if result.created_at else datetime.now(timezone.utc).isoformat(),
        },
    }

