"""Tests for repository comparison service and POST /compare endpoint (T6.3)."""

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


def test_compare_duplicate_id_rejected(client):
    """Verify comparing the same analysis twice is rejected (T6.3 acceptance criterion)."""
    res = client.post("/api/v1/compare", json={"analysis_ids": [1, 1]})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DUPLICATE_ANALYSIS_ID"


def test_compare_count_validation(client):
    # Less than 2
    res1 = client.post("/api/v1/compare", json={"analysis_ids": [1]})
    assert res1.status_code == 422 or res1.status_code == 400

    # More than 4
    res2 = client.post("/api/v1/compare", json={"analysis_ids": [1, 2, 3, 4, 5]})
    assert res2.status_code == 422 or res2.status_code == 400


def test_compare_nonexistent_and_pending(client):
    # Nonexistent
    res = client.post("/api/v1/compare", json={"analysis_ids": [998, 999]})
    assert res.status_code == 404

    # Pending
    db = TestingSessionLocal()
    r1 = Repository(full_name="org/r1")
    r2 = Repository(full_name="org/r2")
    db.add_all([r1, r2])
    db.commit()

    a1 = Analysis(repository_id=r1.id, head_sha="111111", status="running", created_at=datetime.now(timezone.utc))
    a2 = Analysis(repository_id=r2.id, head_sha="222222", status="completed", created_at=datetime.now(timezone.utc))
    db.add_all([a1, a2])
    db.commit()
    id1, id2 = a1.id, a2.id
    db.close()

    res_pending = client.post("/api/v1/compare", json={"analysis_ids": [id1, id2]})
    assert res_pending.status_code == 409


def test_compare_success_and_best_per_metric(client):
    db = TestingSessionLocal()
    r1 = Repository(full_name="org/fast")
    r2 = Repository(full_name="org/slow")
    db.add_all([r1, r2])
    db.commit()

    a1 = Analysis(repository_id=r1.id, head_sha="aaaaaa", status="completed", created_at=datetime.now(timezone.utc))
    a2 = Analysis(repository_id=r2.id, head_sha="bbbbbb", status="completed", created_at=datetime.now(timezone.utc))
    db.add_all([a1, a2])
    db.commit()

    # Results for a1 (High quality, low duplication, 0 bugs)
    db.add(Result(
        analysis_id=a1.id,
        module="quality",
        payload={
            "overall_score": 90.0,
            "grade": "A",
            "tech_debt": {"hours": 2.0},
            "components": {"duplication": {"metric_value": "2.0%"}},
        },
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Result(
        analysis_id=a1.id,
        module="bugs",
        payload={"summary": {"high_risk": 0}},
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Result(
        analysis_id=a1.id,
        module="security",
        payload={"total_issues": 0},
        created_at=datetime.now(timezone.utc),
    ))

    # Results for a2 (Lower quality, higher duplication, 5 bugs)
    db.add(Result(
        analysis_id=a2.id,
        module="quality",
        payload={
            "overall_score": 60.0,
            "grade": "C",
            "tech_debt": {"hours": 15.0},
            "components": {"duplication": {"metric_value": "12.0%"}},
        },
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Result(
        analysis_id=a2.id,
        module="bugs",
        payload={"summary": {"high_risk": 5}},
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Result(
        analysis_id=a2.id,
        module="security",
        payload={"total_issues": 3},
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    id1, id2 = a1.id, a2.id
    db.close()

    res = client.post("/api/v1/compare", json={"analysis_ids": [id1, id2]})
    assert res.status_code == 200
    data = res.json()["data"]

    assert len(data["analyses"]) == 2
    assert "metrics_table" in data
    assert "radar_data" in data
    assert "cluster_points" in data

    # Verify best-per-metric logic
    # Quality Score: a1 is 90 > a2 60 -> a1 is best
    qual_row = next(r for r in data["metrics_table"] if r["key"] == "quality_score")
    a1_qual = next(v for v in qual_row["values"] if v["analysis_id"] == id1)
    a2_qual = next(v for v in qual_row["values"] if v["analysis_id"] == id2)
    assert a1_qual["is_best"] is True
    assert a2_qual["is_best"] is False

    # Duplication %: a1 is 2.0% < a2 12.0% -> a1 is best
    dup_row = next(r for r in data["metrics_table"] if r["key"] == "duplication_pct")
    a1_dup = next(v for v in dup_row["values"] if v["analysis_id"] == id1)
    a2_dup = next(v for v in dup_row["values"] if v["analysis_id"] == id2)
    assert a1_dup["is_best"] is True
    assert a2_dup["is_best"] is False
