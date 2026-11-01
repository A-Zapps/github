"""Vector chunk storage and brute-force numpy cosine search in SQLite (T7.1, ARCHITECTURE 11)."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.db.models import RAGChunk
from backend.app.rag.embedder import blob_to_vector, vector_to_blob

logger = logging.getLogger(__name__)


def save_chunks_to_db(
    db: Session,
    analysis_id: int,
    chunks: List[Dict[str, Any]],
    embeddings: np.ndarray,
) -> int:
    """Store code chunks and their embeddings in the rag_chunks table."""
    if not chunks:
        return 0

    # Clean existing chunks for this analysis
    db.query(RAGChunk).filter(RAGChunk.analysis_id == analysis_id).delete()
    db.commit()

    records = []
    for i, c in enumerate(chunks):
        emb_blob = vector_to_blob(embeddings[i])
        record = RAGChunk(
            analysis_id=analysis_id,
            path=c["path"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            text=c["text"],
            embedding=emb_blob,
        )
        records.append(record)

    db.bulk_save_objects(records)
    db.commit()
    logger.info("Saved %d RAG chunks for analysis %d", len(records), analysis_id)
    return len(records)


def search_chunks(
    db: Session,
    analysis_id: int,
    query_vec: np.ndarray,
    top_k: int = 8,
    file_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Brute-force cosine similarity search with numpy over an analysis's code chunks."""
    records = db.query(RAGChunk).filter(RAGChunk.analysis_id == analysis_id).all()
    if not records:
        return []

    # Unpack stored embeddings into a 2D matrix
    matrix = np.vstack([blob_to_vector(r.embedding) for r in records])

    # Ensure query vector is unit normalized
    q_norm = np.linalg.norm(query_vec)
    if q_norm > 0:
        query_vec = query_vec / q_norm

    # Cosine dot product (since matrix rows and query vector are unit-normalized)
    scores = np.dot(matrix, query_vec)

    results: List[Dict[str, Any]] = []
    for i, rec in enumerate(records):
        score = float(scores[i])

        # If a specific file is targeted, give relevance boost for chunks in that file
        if file_path and rec.path.lower() == file_path.lower():
            score += 0.25

        results.append({
            "id": rec.id,
            "path": rec.path,
            "start_line": rec.start_line,
            "end_line": rec.end_line,
            "text": rec.text,
            "score": round(score, 4),
        })

    # Sort descending by score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
