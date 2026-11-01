"""Unit tests for repository name validation, analysis enqueuing, and job progress tracking."""

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.jobs import cleanup_stale_jobs_on_startup, create_job
from backend.app.core.repo_validation import normalize_and_validate_repo_name
from backend.app.db.models import Base
from backend.app.errors import AppError
from backend.app.main import create_app


def test_repo_name_validation():
    """Verify repo name normalization and rejection of invalid/hostile patterns (RULES B4)."""
    assert normalize_and_validate_repo_name("pallets/flask") == "pallets/flask"
    assert normalize_and_validate_repo_name("https://github.com/pallets/flask.git") == "pallets/flask"
    assert normalize_and_validate_repo_name("http://github.com/facebook/react/") == "facebook/react"

    # Hostile / Invalid inputs
    invalid_inputs = ["../etc", "/root/passwords", "flask", "pallets/flask/sub", "owner;rm", "a" * 105 + "/b"]
    for inv in invalid_inputs:
        with pytest.raises(AppError) as exc_info:
            normalize_and_validate_repo_name(inv)
        assert exc_info.value.code == "INVALID_REPO_NAME"


def test_startup_stale_jobs_cleanup():
    """Verify jobs left in running state on restart are marked failed."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    job1 = create_job(db, "analysis")
    job1.status = "running"
    db.commit()

    count = cleanup_stale_jobs_on_startup(db)
    assert count >= 1

    db.refresh(job1)
    assert job1.status == "failed"
    assert job1.error_code == "SERVER_RESTARTED"
    db.close()


@pytest.mark.asyncio
@respx.mock
async def test_post_analysis_and_poll_job():
    """Verify POST /analyses returns 202 and job moves to succeeded."""
    # Mock GitHub calls for resolve and metadata stages
    respx.get("https://api.github.com/repos/pallets/flask").mock(
        return_value=httpx.Response(200, json={"default_branch": "main", "size": 15000})
    )
    respx.get("https://api.github.com/repos/pallets/flask/commits/main").mock(
        return_value=httpx.Response(200, json={"sha": "1234567890abcdef1234567890abcdef12345678"})
    )
    respx.get("https://api.github.com/repos/pallets/flask/languages").mock(
        return_value=httpx.Response(200, json={"Python": 1000})
    )
    respx.get("https://api.github.com/repos/pallets/flask/contributors").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/pallets/flask/releases").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/pallets/flask/issues").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/pallets/flask/stats/commit_activity").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/pallets/flask/readme").mock(
        return_value=httpx.Response(200, json={"content": "", "encoding": "base64"})
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    with patch("backend.app.services.analysis_pipeline.clone_bare_repo"), \
         patch("backend.app.services.analysis_pipeline.materialize_tree", return_value={"total_files": 0, "extracted_files": 0, "skipped_files": 0}), \
         patch("backend.app.services.analysis_pipeline.scan_inventory", return_value={"total_files": 0, "total_lines": 0, "languages": {}, "test_files_count": 0, "source_files_count": 0, "test_to_source_ratio": 0.0, "files": []}):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Invalid repo returns 400 INVALID_REPO_NAME
            bad_resp = await client.post("/api/v1/analyses", json={"repo": "../etc"})
            assert bad_resp.status_code == 400
            assert bad_resp.json()["error"]["code"] == "INVALID_REPO_NAME"

            # Valid repo returns 202 Accepted
            resp = await client.post("/api/v1/analyses", json={"repo": "pallets/flask"})
            assert resp.status_code == 202
            body = resp.json()
            assert "data" in body
            assert body["data"]["repo"] == "pallets/flask"
            job_id = body["data"]["job_id"]

            # Give background task a moment to complete
            await asyncio.sleep(0.5)

            # Poll job status
            job_resp = await client.get(f"/api/v1/jobs/{job_id}")
            assert job_resp.status_code == 200
            job_data = job_resp.json()["data"]
            assert job_data["id"] == job_id
            assert job_data["status"] == "succeeded"
            assert job_data["progress"] == 100
