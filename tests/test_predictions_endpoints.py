"""Tests for prediction endpoints and model metadata (T4.1 & T4.2, RULES D5-D6)."""

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


def test_models_list_and_detail(client):
    res = client.get("/api/v1/models")
    assert res.status_code == 200
    body = res.json()
    assert "data" in body
    models = body["data"]
    assert len(models) == 5
    names = [m["name"] for m in models]
    assert "bug_risk" in names
    assert "repo_health" in names

    # Detail endpoint
    detail_res = client.get("/api/v1/models/bug_risk")
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert detail["name"] == "bug_risk"
    assert "metrics" in detail
    assert "model_card" in detail

    # Unknown model 404
    err_res = client.get("/api/v1/models/nonexistent_model")
    assert err_res.status_code == 404


def test_bugs_endpoint_not_found_and_not_ready(client):
    # 404 when analysis does not exist
    res = client.get("/api/v1/analyses/999/bugs")
    assert res.status_code == 404

    # 409 when result not yet computed
    db = TestingSessionLocal()
    repo = Repository(full_name="org/repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="abcdef123456",
        status="running",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    a_id = analysis.id
    db.close()

    res = client.get(f"/api/v1/analyses/{a_id}/bugs")
    assert res.status_code == 409


def test_bugs_and_health_endpoints_ready(client):
    db = TestingSessionLocal()
    repo = Repository(full_name="test/repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        status="completed",
        head_sha="abcdef123456",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Add bugs result
    bugs_res = Result(
        analysis_id=analysis.id,
        module="bugs",
        payload={
            "status": "ready",
            "model_name": "bug_risk",
            "model_version": "1.0.0",
            "files": [
                {
                    "file": "main.py",
                    "risk_tier": "high",
                    "probability": 0.88,
                    "drivers": ["High CCN (15.0)", "High churn (3.5)"],
                    "ccn_max": 15.0,
                    "loc": 320,
                }
            ],
            "summary": {"total_files": 1, "high_risk": 1, "medium_risk": 0, "low_risk": 0},
        },
        model_versions={"bug_risk": "1.0.0"},
        created_at=datetime.now(timezone.utc),
    )
    # Add health result
    health_res = Result(
        analysis_id=analysis.id,
        module="health",
        payload={
            "status": "ready",
            "health": {
                "health_class": "Healthy",
                "probabilities": {"Healthy": 0.92, "Moderately Active": 0.05, "Declining": 0.02, "Inactive": 0.01},
                "model_version": "1.0.0",
            },
            "clusters": {
                "cluster_id": 2,
                "pca_coordinates": [1.4, -0.8],
                "corpus_percentiles": {"total_loc": 75.0},
            },
            "signals": {"commits_per_month_mean": 24.5, "distinct_authors": 8},
        },
        model_versions={"repo_health": "1.0.0"},
        created_at=datetime.now(timezone.utc),
    )
    db.add(bugs_res)
    db.add(health_res)
    db.commit()
    a_id = analysis.id
    db.close()

    # Query bugs endpoint
    b_res = client.get(f"/api/v1/analyses/{a_id}/bugs")
    assert b_res.status_code == 200
    b_data = b_res.json()["data"]
    assert b_data["status"] == "ready"
    assert len(b_data["files"]) == 1
    assert b_data["files"][0]["risk_tier"] == "high"
    assert b_data["files"][0]["probability"] == 0.88

    # Query health endpoint
    h_res = client.get(f"/api/v1/analyses/{a_id}/health")
    assert h_res.status_code == 200
    h_data = h_res.json()["data"]
    assert h_data["health"]["health_class"] == "Healthy"
    assert h_data["health"]["probabilities"]["Healthy"] == 0.92
    assert h_data["clusters"]["cluster_id"] == 2


def test_bugs_endpoint_model_not_trained_503(client):
    db = TestingSessionLocal()
    repo = Repository(full_name="test/repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        status="completed",
        head_sha="abcdef123456",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    bugs_res = Result(
        analysis_id=analysis.id,
        module="bugs",
        payload={"status": "MODEL_NOT_TRAINED", "files": []},
        created_at=datetime.now(timezone.utc),
    )
    db.add(bugs_res)
    db.commit()
    a_id = analysis.id
    db.close()

    res = client.get(f"/api/v1/analyses/{a_id}/bugs")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "MODEL_NOT_TRAINED"
