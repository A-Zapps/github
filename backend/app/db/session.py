"""Database engine and session management."""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings


def get_engine():
    """Create SQLAlchemy engine using DATABASE_URL setting."""
    settings = get_settings()
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        # Ensure parent directory exists for SQLite file
        if ":///" in db_url:
            path = db_url.split(":///", 1)[1]
            dirname = os.path.dirname(path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield database session and guarantee closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
