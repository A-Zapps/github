"""Tests verifying database schema creation and table integrity."""

from sqlalchemy import inspect

from backend.app.db.session import engine


def test_all_models_have_tables():
    """Verify all declarative models exist in SQLite database."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    expected_tables = {
        "repositories",
        "analyses",
        "stage_runs",
        "results",
        "jobs",
        "github_cache",
        "rag_chunks",
        "reports",
        "comparisons",
        "settings",
    }

    assert expected_tables.issubset(existing_tables), f"Missing tables: {expected_tables - existing_tables}"
