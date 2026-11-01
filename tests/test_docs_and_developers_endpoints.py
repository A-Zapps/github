"""Tests for Documentation and Developer Analytics API endpoints (T5.2 & T5.4)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository, Result
from backend.app.db.session import get_db
from backend.app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_docs_and_developers_not_found_and_not_ready(client):
    # 404 when analysis not found
    assert client.get("/api/v1/analyses/999/docs").status_code == 404
    assert client.get("/api/v1/analyses/999/developers").status_code == 404

    # 409 when results are pending
    db = TestingSessionLocal()
    repo = Repository(full_name="test/repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="sha123456",
        status="running",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    a_id = analysis.id
    db.close()

    assert client.get(f"/api/v1/analyses/{a_id}/docs").status_code == 409
    assert client.get(f"/api/v1/analyses/{a_id}/developers").status_code == 409


def test_docs_and_developers_success(client):
    db = TestingSessionLocal()
    repo = Repository(full_name="test/repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="sha123456",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()

    # Add docs result
    docs_res = Result(
        analysis_id=analysis.id,
        module="docs",
        payload={
            "has_readme": True,
            "filename": "README.md",
            "overall_score": 85,
            "grade": "B",
            "checklist": {
                "installation": {"status": "found", "earned": 30, "weight": 30},
                "usage": {"status": "found", "earned": 30, "weight": 30},
                "contributing": {"status": "weak", "earned": 10, "weight": 20},
                "license": {"status": "weak", "earned": 10, "weight": 20},
            },
            "suggestions": ["Expand Contributing section"],
            "sections": [{"category": "installation", "length": 150, "preview": "pip install ..."}],
        },
        created_at=datetime.now(timezone.utc),
    )
    # Add developers result
    devs_res = Result(
        analysis_id=analysis.id,
        module="developers",
        payload={
            "total_commits": 50,
            "distinct_contributors": 4,
            "bus_factor": 2,
            "bus_factor_label": "Moderate Risk",
            "contributors": [
                {"author": "Alice", "commits": 30, "percentage": 60.0, "lines_added": 300, "lines_deleted": 50}
            ],
            "commit_rhythm_heatmap": [[0] * 24 for _ in range(7)],
            "pr_merge_time": {"available": True, "median_hours": 12.0, "p90_hours": 24.0, "count": 10},
            "issue_close_time": {"available": False, "reason": "Insufficient closed issue history"},
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(docs_res)
    db.add(devs_res)
    db.commit()
    a_id = analysis.id
    db.close()

    # 1. Test docs endpoint
    doc_resp = client.get(f"/api/v1/analyses/{a_id}/docs")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()["data"]
    assert doc_data["overall_score"] == 85
    assert doc_data["grade"] == "B"
    assert doc_data["checklist"]["installation"]["status"] == "found"
    assert len(doc_data["suggestions"]) == 1

    # 2. Test developers endpoint
    dev_resp = client.get(f"/api/v1/analyses/{a_id}/developers")
    assert dev_resp.status_code == 200
    dev_data = dev_resp.json()["data"]
    assert dev_data["total_commits"] == 50
    assert dev_data["bus_factor"] == 2
    assert dev_data["pr_merge_time"]["available"] is True
    assert dev_data["issue_close_time"]["available"] is False
