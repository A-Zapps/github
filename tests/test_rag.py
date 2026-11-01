"""Tests for RAG chunker, local embedder, and vector search store (T7.1)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Analysis, Base, Repository
from backend.app.rag.chunker import chunk_file_content
from backend.app.rag.embedder import LocalEmbedder, blob_to_vector, vector_to_blob
from backend.app.rag.store import save_chunks_to_db, search_chunks

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


def test_chunk_file_content_with_functions():
    code = """import os

def authenticate_user(username, password):
    if not username or not password:
        return False
    # verify password hash
    return check_password(username, password)

def calculate_monthly_revenue(orders):
    total = 0
    for o in orders:
        total += o.amount
    return total
"""
    functions = [
        {"name": "authenticate_user", "start_line": 3, "end_line": 8},
        {"name": "calculate_monthly_revenue", "start_line": 9, "end_line": 14},
    ]

    chunks = chunk_file_content("app/services.py", code, functions)
    assert len(chunks) >= 2
    func_names = [c["function_name"] for c in chunks if c["function_name"]]
    assert "authenticate_user" in func_names
    assert "calculate_monthly_revenue" in func_names


def test_local_embedder_and_serialization():
    embedder = LocalEmbedder()
    texts = ["authenticate user password check", "calculate monthly revenue total orders"]
    matrix = embedder.embed_texts(texts)
    assert matrix.shape == (2, 384)

    # Test serialization round-trip
    blob = vector_to_blob(matrix[0])
    unpacked = blob_to_vector(blob)
    assert unpacked.shape == (384,)
    assert abs(unpacked[0] - matrix[0][0]) < 1e-5


def test_asking_for_known_function_returns_its_chunk_first():
    """T7.1 Acceptance criterion: asking for a known function returns its chunk first."""
    db = TestingSessionLocal()
    repo = Repository(full_name="org/proj")
    db.add(repo)
    db.commit()

    analysis = Analysis(repository_id=repo.id, head_sha="abc123", status="completed")
    db.add(analysis)
    db.commit()

    code_auth = """def authenticate_user(username, password):
    # Validates credentials against hashed store
    if not username or not password:
        return None
    token = generate_jwt_token(username)
    return token
"""
    code_revenue = """def calculate_monthly_revenue(orders):
    # Aggregates invoice lines for monthly reporting
    total = sum(order.price * order.qty for order in orders)
    return round(total, 2)
"""
    code_logging = """def configure_logging(log_level):
    import logging
    logging.basicConfig(level=log_level)
"""

    chunks = [
        {"path": "src/auth.py", "start_line": 1, "end_line": 8, "text": code_auth, "function_name": "authenticate_user"},
        {"path": "src/billing.py", "start_line": 1, "end_line": 6, "text": code_revenue, "function_name": "calculate_monthly_revenue"},
        {"path": "src/logger.py", "start_line": 1, "end_line": 5, "text": code_logging, "function_name": "configure_logging"},
    ]

    embedder = LocalEmbedder()
    embeddings = embedder.embed_texts([c["text"] for c in chunks])
    count = save_chunks_to_db(db, analysis.id, chunks, embeddings)
    assert count == 3

    # Query 1: Asking for authentication
    q_auth = embedder.embed_query("authenticate_user login password")
    results_auth = search_chunks(db, analysis.id, q_auth, top_k=3)
    assert len(results_auth) > 0
    assert results_auth[0]["path"] == "src/auth.py"
    assert "authenticate_user" in results_auth[0]["text"]

    # Query 2: Asking for revenue calculation
    q_rev = embedder.embed_query("calculate_monthly_revenue orders total revenue")
    results_rev = search_chunks(db, analysis.id, q_rev, top_k=3)
    assert len(results_rev) > 0
    assert results_rev[0]["path"] == "src/billing.py"
    assert "calculate_monthly_revenue" in results_rev[0]["text"]

    db.close()
