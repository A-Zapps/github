"""Pydantic schemas for analysis requests and job status."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Payload for submitting a repository analysis request."""
    repo: str = Field(..., description="Repository full name in 'owner/name' format or GitHub URL")


class AnalyzeResponseData(BaseModel):
    """Response payload when an analysis job is enqueued."""
    analysis_id: int
    job_id: str
    repo: str
    cached: bool = False


class JobResponseData(BaseModel):
    """Job status and progress tracking data."""
    id: str
    type: str
    status: str
    progress: int
    stage: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
