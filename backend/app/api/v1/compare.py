"""Repository comparison API endpoint (T6.3, RULES A1-A8)."""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.comparison_service import compare_analyses

router = APIRouter(prefix="/compare", tags=["comparison"])


class CompareRequest(BaseModel):
    analysis_ids: List[int] = Field(..., min_length=2, max_length=4, description="List of 2 to 4 unique analysis IDs")


@router.post("")
def run_comparison(req: CompareRequest, db: Session = Depends(get_db)):
    """Compare 2 to 4 completed repository analyses side-by-side."""
    result = compare_analyses(req.analysis_ids, db)
    return {
        "data": result,
        "meta": {
            "analysis_ids": req.analysis_ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
