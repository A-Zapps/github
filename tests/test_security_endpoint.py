"""Tests for Security analysis endpoint and Security frontend page."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository, Result
from backend.app.db.session import get_db
from backend.app.main import app


def test_security_endpoint_200():
    """Verify GET /api/v1/analyses/{id}/security returns security findings."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    repo = Repository(full_name="testowner/security-repo")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="1234567890abcdef",
        default_branch="main",
        analyzer_version="1.0.0",
        status="completed",
    )
    db.add(analysis)
    db.commit()

    security_payload = {
        "severity_summary": {"CRITICAL": 0, "HIGH": 2, "MEDIUM": 1, "LOW": 3},
        "total_issues": 6,
        "code_findings": [
            {
                "source": "Bandit",
                "file": "app.py",
                "line": 42,
                "rule_id": "B101",
                "severity": "LOW",
                "message": "Use of assert detected.",
            }
        ],
        "secrets": {
            "total_secrets": 1,
            "findings": [
                {
                    "file": ".env",
                    "line": 2,
                    "type": "aws_access_key",
                    "masked": "AKIA****",
                    "severity": "HIGH",
                }
            ],
        },
        "dependencies": {
            "total_dependencies": 1,
            "vulnerable_packages_count": 1,
            "vulnerabilities": [
                {
                    "name": "requests",
                    "version": "2.20.0",
                    "ecosystem": "PyPI",
                    "advisories": [
                        {
                            "id": "GHSA-j8r2-6x86-q33q",
                            "summary": "Header leak in requests",
                        }
                    ],
                }
            ],
        },
    }

    result = Result(
        analysis_id=analysis.id,
        module="security",
        payload=security_payload,
        model_versions={},
    )
    db.add(result)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/analyses/{analysis.id}/security")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_issues"] == 6
        assert data["severity_summary"]["HIGH"] == 2
        assert len(data["code_findings"]) == 1
        assert data["secrets"]["findings"][0]["masked"] == "AKIA****"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_security_frontend_contract():
    """Verify frontend/js/pages/security.js has severity bar, tabs, and RULES B7 masking."""
    js_path = Path(__file__).resolve().parent.parent / "frontend" / "js" / "pages" / "security.js"
    assert js_path.is_file()
    content = js_path.read_text(encoding="utf-8")

    assert "renderSecurityPage" in content
    assert "getSecurityData" in content
    assert "Severity Summary" in content or "severityGrid" in content
    assert "codeTabBtn" in content
    assert "secretsTabBtn" in content
    assert "depsTabBtn" in content
    assert "RULES B7" in content
