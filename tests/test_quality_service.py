"""Tests for Quality scoring service and GET /api/v1/analyses/{id}/quality endpoint."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository, Result
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.quality_service import calculate_quality_scores


def test_quality_scoring_calculation():
    """Verify component scores, weighted overall score, and tech debt label."""
    inventory = {
        "files": [
            {"path": "main.py", "language": "Python", "lines": 150, "is_test": False},
            {"path": "test_main.py", "language": "Python", "lines": 50, "is_test": True},
            {"path": "utils.py", "language": "Python", "lines": 100, "is_test": False},
        ],
        "source_files_count": 2,
        "test_files_count": 1,
    }
    metrics = {
        "total_loc": 250,
        "total_functions": 10,
        "functions_ccn_gt_10_count": 1,
        "functions_ccn_gt_10_ratio": 10.0,
        "files_over_1000_loc_count": 0,
        "files_over_1000_loc_ratio": 0.0,
        "avg_maintainability_index": 82.5,
        "files": {
            "main.py": {"loc": 150, "ccn_max": 12, "ccn_mean": 4.5, "maintainability_index": 78.0, "maintainability_index_is_proxy": False},
            "utils.py": {"loc": 100, "ccn_max": 3, "ccn_mean": 2.0, "maintainability_index": 87.0, "maintainability_index_is_proxy": False},
        },
    }
    duplication = {
        "duplication_percentage": 2.5,
        "duplicate_blocks_count": 1,
        "duplicate_lines": 12,
    }
    lint = {
        "pylint": {
            "total": 3,
            "by_type": {"warning": 2, "error": 1},
        },
        "bandit": {
            "total": 0,
            "by_severity": {},
        },
    }

    res = calculate_quality_scores(inventory, metrics, duplication, lint)

    assert "overall_score" in res
    assert 0 <= res["overall_score"] <= 100
    assert res["grade"] in {"A", "B", "C", "D", "F"}
    assert "complexity" in res["components"]
    assert "maintainability" in res["components"]
    assert "duplication" in res["components"]
    assert "lint_density" in res["components"]
    assert "test_ratio" in res["components"]
    assert "file_size_outliers" in res["components"]

    # Tech debt check
    assert res["tech_debt"]["label"] == "estimate from fixed rules, not measured"
    assert res["tech_debt"]["minutes"] > 0
    assert res["tech_debt"]["hours"] > 0

    # Worst files check
    assert len(res["worst_files"]) == 2
    assert res["worst_files"][0]["path"] == "main.py"


def test_quality_endpoint_200():
    """Verify GET /api/v1/analyses/{id}/quality returns 200 with result payload."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    repo = Repository(full_name="testowner/quality-repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="abcdef1234567890",
        default_branch="main",
        analyzer_version="1.0.0",
        status="completed",
    )
    db.add(analysis)
    db.commit()

    quality_payload = {
        "overall_score": 88.5,
        "grade": "B",
        "tech_debt": {
            "minutes": 150,
            "hours": 2.5,
            "days": 0.3,
            "label": "estimate from fixed rules, not measured",
        },
        "components": {},
        "worst_files": [],
    }
    result = Result(
        analysis_id=analysis.id,
        module="quality",
        payload=quality_payload,
        model_versions={},
    )
    db.add(result)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/quality")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["overall_score"] == 88.5
        assert data["grade"] == "B"
        assert data["tech_debt"]["label"] == "estimate from fixed rules, not measured"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
