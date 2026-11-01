"""Report generation and download endpoints (T8.3, ARCHITECTURE 12)."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import Analysis, Report, Result
from backend.app.db.session import get_db
from backend.app.errors import AppError
from backend.app.reports.builder import build_analysis_pdf

router = APIRouter(tags=["reports"])


def get_reports_dir() -> Path:
    """Ensure data/reports directory exists."""
    settings = get_settings()
    rep_dir = Path(settings.DATA_DIR) / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    return rep_dir


@router.post("/analyses/{analysis_id}/reports")
def generate_report(analysis_id: int, db: Session = Depends(get_db)):
    """Generate executive PDF report for a completed analysis."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)
    if analysis.status != "completed":
        raise AppError("ANALYSIS_NOT_READY", f"Analysis is not completed (status: {analysis.status}).", status_code=409)

    # Load all module results
    results = db.query(Result).filter(Result.analysis_id == analysis_id).all()
    res_map: Dict[str, Any] = {r.module: r.payload for r in results}

    repo_data = res_map.get("repository", {})
    quality_data = res_map.get("quality", {})
    bugs_data = res_map.get("bugs", {})
    security_data = res_map.get("security", {})
    health_data = res_map.get("health", {})
    dev_data = res_map.get("developers", {})
    recs_data = res_map.get("recommendations", {})

    settings = get_settings()
    appendix_data = {
        "analyzer_version": analysis.analyzer_version,
        "head_sha": analysis.head_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_versions": "bug_risk:1.0.0, repo_health:1.0.0, repo_clusters:1.0.0",
        "max_files": settings.MAX_FILES,
        "max_file_kb": settings.MAX_FILE_KB,
    }

    reports_dir = get_reports_dir()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_repo_name = (repo_data.get("full_name") or f"repo_{analysis_id}").replace("/", "_")
    filename = f"report_{safe_repo_name}_{analysis_id}_{timestamp_str}.pdf"
    pdf_path = reports_dir / filename

    try:
        build_analysis_pdf(
            analysis_id=analysis_id,
            repo_data=repo_data,
            quality_data=quality_data,
            bugs_data=bugs_data,
            security_data=security_data,
            health_data=health_data,
            dev_data=dev_data,
            recs_data=recs_data,
            appendix_data=appendix_data,
            output_path=str(pdf_path),
        )
    except Exception as e:
        raise AppError("REPORT_BUILD_FAILED", f"Failed to build PDF report: {e}", status_code=500)

    # Record report in DB
    report_record = Report(
        analysis_id=analysis_id,
        file_path=str(pdf_path),
    )
    db.add(report_record)
    db.commit()
    db.refresh(report_record)

    return {
        "data": {
            "report_id": report_record.id,
            "analysis_id": analysis_id,
            "filename": filename,
            "download_url": f"/api/v1/reports/{report_record.id}/download",
            "created_at": report_record.created_at.isoformat() if report_record.created_at else None,
        },
        "meta": {
            "analysis_id": analysis_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/analyses/{analysis_id}/reports")
def list_reports(analysis_id: int, db: Session = Depends(get_db)):
    """List all generated PDF reports for an analysis."""
    reports = db.query(Report).filter(Report.analysis_id == analysis_id).order_by(Report.created_at.desc()).all()
    data = []
    for r in reports:
        data.append({
            "report_id": r.id,
            "analysis_id": r.analysis_id,
            "filename": os.path.basename(r.file_path),
            "download_url": f"/api/v1/reports/{r.id}/download",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {
        "data": data,
        "meta": {
            "analysis_id": analysis_id,
            "count": len(data),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Download a generated PDF report file."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise AppError("NOT_FOUND", f"Report {report_id} not found.", status_code=404)

    if not os.path.isfile(report.file_path):
        raise AppError("FILE_NOT_FOUND", "Report PDF file does not exist on disk.", status_code=404)

    filename = os.path.basename(report.file_path)
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=filename,
    )
