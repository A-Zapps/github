"""SQLAlchemy 2.0 ORM models for all database entities."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


class Repository(Base):
    """Tracked GitHub repository."""
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    analyses: Mapped[List["Analysis"]] = relationship("Analysis", back_populates="repository", cascade="all, delete-orphan")


class Analysis(Base):
    """Analysis record for a specific commit of a repository."""
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    analyzer_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="analyses")
    stage_runs: Mapped[List["StageRun"]] = relationship("StageRun", back_populates="analysis", cascade="all, delete-orphan")
    results: Mapped[List["Result"]] = relationship("Result", back_populates="analysis", cascade="all, delete-orphan")
    rag_chunks: Mapped[List["RAGChunk"]] = relationship("RAGChunk", back_populates="analysis", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="analysis", cascade="all, delete-orphan")


class StageRun(Base):
    """Execution status and timing for each pipeline stage."""
    __tablename__ = "stage_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, running, completed, failed, skipped
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="stage_runs")


class Result(Base):
    """Analysis output payload partitioned by module."""
    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint("analysis_id", "module", name="uq_analysis_module"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False)  # repository, quality_raw, quality, etc.
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    model_versions: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="results")


class Job(Base):
    """Asynchronous background job status and progress tracking."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # analysis, report
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")  # queued, running, succeeded, failed, cancelled
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class GitHubCache(Base):
    """Cache for GitHub API ETag responses."""
    __tablename__ = "github_cache"

    url: Mapped[str] = mapped_column(String(500), primary_key=True)
    etag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    body: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class RAGChunk(Base):
    """Code chunks with vector embeddings for AI code assistant retrieval."""
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="rag_chunks")


class Report(Base):
    """Generated PDF reports for an analysis."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="reports")


class Comparison(Base):
    """Saved multi-repository comparison evaluations."""
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class Setting(Base):
    """Key-value settings store."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
