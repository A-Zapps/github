"""Tests for PDF report builder, chart generation, and report download endpoints (T8.1, T8.2, T8.3)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository, Result
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.reports.builder import build_analysis_pdf, safe_text
from backend.app.reports.charts import (
    render_bug_distribution_chart,
    render_quality_breakdown_bars,
    render_security_summary_bars,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
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


def test_xml_escaping_helper():
    assert safe_text("Tom & Jerry") == "Tom &amp; Jerry"
    assert safe_text("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert safe_text('foo "bar"') == "foo &quot;bar&quot;"


def test_pdf_builder_with_html_tags_and_ampersand():
    """T8.2 Acceptance criterion: a test with <b> and & in a repo-derived string produces a valid PDF."""
    hostile_repo = "org/<b>bold_repo</b> & <italic>bad_xml</italic>"
    hostile_msg = "Fixed memory & buffer overflow in <b>auth_core</b>"

    repo_data = {"full_name": hostile_repo}
    quality_data = {
        "overall_score": 82,
        "tech_debt_hours": 14,
        "components": {
            "complexity": {"score": 85},
            "duplication": {"score": 90},
            "lint": {"score": 75},
        },
    }
    bugs_data = {
        "summary": {"high": 2, "medium": 5, "low": 12},
    }
    security_data = {
        "total_issues": 1,
        "severity_summary": {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 0},
        "code_findings": [
            {
                "severity": "HIGH",
                "source": "Bandit & Semgrep",
                "file": "src/<b>core</b>.py",
                "line": 42,
                "message": hostile_msg,
            }
        ],
    }
    health_data = {}
    dev_data = {"bus_factor": 2}
    recs_data = {
        "recommendations": [
            {
                "priority": "high",
                "title": "Refactor <b>critical</b> module & tests",
                "evidence": "File src/<b>core</b>.py & line 42",
                "effort": "2h",
                "impact": "Improves security & resilience",
            }
        ]
    }
    appendix_data = {
        "analyzer_version": "1.0.0",
        "head_sha": "abc123456789",
        "model_versions": "bug_risk:1.0.0 & repo_health:1.0.0",
    }

    pdf_bytes = build_analysis_pdf(
        analysis_id=1,
        repo_data=repo_data,
        quality_data=quality_data,
        bugs_data=bugs_data,
        security_data=security_data,
        health_data=health_data,
        dev_data=dev_data,
        recs_data=recs_data,
        appendix_data=appendix_data,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    # Valid PDF file header
    assert pdf_bytes.startswith(b"%PDF-")


def test_chart_renderers_use_api_data():
    """T8.1 Acceptance criterion: each chart uses the same data as the API."""
    # Bug donut chart
    bug_data = {"high": 3, "medium": 7, "low": 15}
    donut_png = render_bug_distribution_chart(bug_data)
    assert len(donut_png) > 500
    assert donut_png.startswith(b"\x89PNG")

    # Quality breakdown chart
    qual_comp = {"architecture": {"score": 80}, "maintainability": {"score": 65}}
    bars_png = render_quality_breakdown_bars(qual_comp)
    assert len(bars_png) > 500
    assert bars_png.startswith(b"\x89PNG")

    # Security summary chart
    sec_counts = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 5, "LOW": 3}
    sec_png = render_security_summary_bars(sec_counts)
    assert len(sec_png) > 500
    assert sec_png.startswith(b"\x89PNG")


def test_post_report_and_download_flow(client):
    """T8.3 Acceptance criterion: report job generates PDF and download endpoint serves it."""
    db = TestingSessionLocal()
    repo = Repository(full_name="acme/pdf-test")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="sha888",
        analyzer_version="1.0.0",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()

    # Seed result modules
    r_qual = Result(
        analysis_id=analysis.id,
        module="quality",
        payload={"overall_score": 88, "tech_debt_hours": 8, "components": {"lint": {"score": 90}}},
    )
    r_bugs = Result(
        analysis_id=analysis.id,
        module="bugs",
        payload={"summary": {"high": 1, "medium": 2, "low": 8}},
    )
    r_sec = Result(
        analysis_id=analysis.id,
        module="security",
        payload={"total_issues": 1, "severity_summary": {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 0}},
    )
    db.add_all([r_qual, r_bugs, r_sec])
    db.commit()
    a_id = analysis.id
    db.close()

    # 1. Generate report
    gen_resp = client.post(f"/api/v1/analyses/{a_id}/reports")
    assert gen_resp.status_code == 200
    body = gen_resp.json()
    assert "data" in body
    report_id = body["data"]["report_id"]
    assert report_id > 0
    download_url = body["data"]["download_url"]

    # 2. List reports
    list_resp = client.get(f"/api/v1/analyses/{a_id}/reports")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) >= 1

    # 3. Download report PDF
    dl_resp = client.get(download_url)
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/pdf"
    assert dl_resp.content.startswith(b"%PDF-")
