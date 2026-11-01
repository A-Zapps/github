"""Tests for AI Assistant query endpoint, citation validation, and fallback handling (T7.2, T7.3)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.rag.embedder import LocalEmbedder
from backend.app.rag.llm import MockProvider, validate_citations
from backend.app.rag.store import save_chunks_to_db

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


def seed_analysis_with_chunks(db):
    repo = Repository(full_name="acme/web-app")
    db.add(repo)
    db.commit()

    analysis = Analysis(
        repository_id=repo.id,
        head_sha="sha999",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()

    chunks = [
        {
            "path": "backend/auth.py",
            "start_line": 10,
            "end_line": 30,
            "text": "def verify_credentials(user, pwd):\n    return check_pwd(user, pwd)",
        },
        {
            "path": "backend/orders.py",
            "start_line": 1,
            "end_line": 25,
            "text": "def calculate_cart_total(items):\n    return sum(item.price for item in items)",
        },
    ]

    embedder = LocalEmbedder()
    embeddings = embedder.embed_texts([c["text"] for c in chunks])
    save_chunks_to_db(db, analysis.id, chunks, embeddings)

    return analysis.id


def test_no_key_set_returns_retrieved_chunks_and_llm_not_configured_note(client):
    """T7.2 Acceptance criterion: with no key set, returns retrieved chunks and LLM_NOT_CONFIGURED in note."""
    db = TestingSessionLocal()
    a_id = seed_analysis_with_chunks(db)
    db.close()

    with patch("backend.app.rag.llm.get_settings") as mock_settings:
        mock_settings.return_value.LLM_PROVIDER = "none"
        mock_settings.return_value.LLM_API_KEY = ""

        resp = client.post(
            f"/api/v1/analyses/{a_id}/assistant/query",
            json={"mode": "ask", "question": "How does credential verification work?"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Note must be LLM_NOT_CONFIGURED
        assert data["note"] == "LLM_NOT_CONFIGURED"
        # Chunks must be retrieved and non-empty
        assert len(data["chunks"]) > 0
        assert data["chunks"][0]["path"] in ("backend/auth.py", "backend/orders.py")
        assert not data["flagged"]


def test_invalid_citation_removed_and_answer_flagged(client):
    """T7.3 Acceptance criterion: fake provider citing non-existent file gets citation removed and answer flagged."""
    db = TestingSessionLocal()
    a_id = seed_analysis_with_chunks(db)
    db.close()

    # Canned response contains 1 valid citation [backend/auth.py:12-25] and 1 fake citation [nonexistent/ghost.py:99-105]
    canned_answer = (
        "Here is the analysis: [backend/auth.py:12-25] handles authentication securely. "
        "Also see [nonexistent/ghost.py:99-105] which does not exist."
    )

    fake_provider = MockProvider(canned_response=canned_answer)

    with patch("backend.app.api.v1.assistant.get_llm_provider", return_value=fake_provider):
        resp = client.post(
            f"/api/v1/analyses/{a_id}/assistant/query",
            json={"mode": "explain_file", "file_path": "backend/auth.py", "question": "Explain this file."},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Answer must be flagged because of the non-existent citation
        assert data["flagged"] is True

        # Valid citation must be preserved in citations list
        assert len(data["citations"]) == 1
        assert data["citations"][0]["path"] == "backend/auth.py"

        # Fake citation must be removed from the text
        assert "[nonexistent/ghost.py:99-105]" not in data["answer"]

        # Warnings must explain removal
        assert len(data["warnings"]) >= 1
        assert "ghost.py" in data["warnings"][0]


def test_citation_validator_standalone():
    """Unit test for citation validation function directly."""
    chunks = [{"path": "app/models.py", "start_line": 1, "end_line": 50}]

    text = "Review [app/models.py:10-20] and also [app/fake.py:5-15]."
    cleaned, valid, warnings, flagged = validate_citations(text, chunks)

    assert flagged is True
    assert len(valid) == 1
    assert valid[0]["path"] == "app/models.py"
    assert "[app/fake.py:5-15]" not in cleaned
    assert "[app/models.py:10-20]" in cleaned


def test_malicious_xss_content_is_retained_as_plain_text(client):
    """T7.4 Acceptance criterion: output renders as text only (tested with <img onerror>)."""
    db = TestingSessionLocal()
    a_id = seed_analysis_with_chunks(db)
    db.close()

    hostile_text = 'Look at <img src=x onerror="alert(1)"> in [backend/auth.py:10-20]!'
    fake_provider = MockProvider(canned_response=hostile_text)

    with patch("backend.app.api.v1.assistant.get_llm_provider", return_value=fake_provider):
        resp = client.post(
            f"/api/v1/analyses/{a_id}/assistant/query",
            json={"mode": "ask", "question": "Check for injection vulnerabilities."},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Text must contain the exact raw string, not stripped or converted to HTML
        assert '<img src=x onerror="alert(1)">' in data["answer"]
        assert len(data["citations"]) == 1

