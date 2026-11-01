"""AI Assistant query endpoint with citation validation and graceful fallback (T7.2, T7.3)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.models import Analysis, Result
from backend.app.db.session import get_db
from backend.app.errors import AppError
from backend.app.rag.embedder import get_embedder
from backend.app.rag.llm import NoneProvider, get_llm_provider, validate_citations
from backend.app.rag.prompts import SYSTEM_PROMPT, build_user_prompt
from backend.app.rag.store import search_chunks

router = APIRouter(prefix="/analyses", tags=["assistant"])

VALID_MODES = {
    "explain_file",
    "find_bugs",
    "summarize_architecture",
    "suggest_improvements",
    "ask",
}


class AssistantQueryRequest(BaseModel):
    mode: str = Field("ask", description="explain_file | find_bugs | summarize_architecture | suggest_improvements | ask")
    question: str = Field("", description="Question or prompt for the assistant")
    file_path: Optional[str] = Field(None, description="Optional target file path")


@router.post("/{analysis_id}/assistant/query")
async def query_assistant(
    analysis_id: int,
    req: AssistantQueryRequest,
    db: Session = Depends(get_db),
):
    """Execute AI Assistant query with vector retrieval and validated citations."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise AppError("NOT_FOUND", f"Analysis {analysis_id} not found.", status_code=404)

    mode = req.mode.lower() if req.mode else "ask"
    if mode not in VALID_MODES:
        raise AppError("INVALID_MODE", f"Invalid mode '{mode}'. Expected one of: {list(VALID_MODES)}", status_code=400)

    # Build search query text
    query_text = f"{req.question} {req.file_path or ''} {mode}".strip()
    embedder = get_embedder()
    query_vec = embedder.embed_query(query_text)

    # Retrieve relevant code chunks
    chunks = search_chunks(
        db=db,
        analysis_id=analysis_id,
        query_vec=query_vec,
        top_k=8,
        file_path=req.file_path,
    )

    # Fetch context: static findings and structure digest
    static_findings: List[Dict[str, Any]] = []
    structure_digest: Dict[str, Any] = {}

    sec_res = db.query(Result).filter(Result.analysis_id == analysis_id, Result.module == "security").first()
    if sec_res and sec_res.payload:
        code_findings = sec_res.payload.get("code_findings", [])
        if req.file_path:
            static_findings = [f for f in code_findings if f.get("file", "").lower() == req.file_path.lower()]
        else:
            static_findings = code_findings[:5]

    repo_res = db.query(Result).filter(Result.analysis_id == analysis_id, Result.module == "repository").first()
    if repo_res and repo_res.payload:
        structure_digest = {
            "languages": repo_res.payload.get("languages", {}),
            "total_files": repo_res.payload.get("size_kb", 0),
        }

    provider = get_llm_provider()

    # If provider is not configured or no key, return chunks with note (T7.2 criterion)
    if isinstance(provider, NoneProvider):
        return {
            "data": {
                "answer": "LLM provider is not configured. Displaying retrieved code context and chunks matching your query.",
                "citations": [],
                "chunks": chunks,
                "mode": mode,
                "warnings": [],
                "flagged": False,
                "note": "LLM_NOT_CONFIGURED",
            },
            "meta": {
                "analysis_id": analysis_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # Generate answer with LLM
    user_prompt = build_user_prompt(
        mode=mode,
        question=req.question,
        chunks=chunks,
        file_path=req.file_path,
        static_findings=static_findings,
        structure_digest=structure_digest,
    )

    try:
        raw_answer = await provider.generate(system=SYSTEM_PROMPT, user_prompt=user_prompt)
    except AppError as ae:
        if ae.code == "LLM_NOT_CONFIGURED":
            return {
                "data": {
                    "answer": "LLM provider is not configured. Displaying retrieved code context.",
                    "citations": [],
                    "chunks": chunks,
                    "mode": mode,
                    "warnings": [],
                    "flagged": False,
                    "note": "LLM_NOT_CONFIGURED",
                },
                "meta": {
                    "analysis_id": analysis_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        raise

    # Validate citations against retrieved chunks (T7.3 criterion)
    cleaned_answer, valid_citations, warnings, flagged = validate_citations(raw_answer, chunks)

    return {
        "data": {
            "answer": cleaned_answer,
            "citations": valid_citations,
            "chunks": chunks,
            "mode": mode,
            "warnings": warnings,
            "flagged": flagged,
            "note": None,
        },
        "meta": {
            "analysis_id": analysis_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
