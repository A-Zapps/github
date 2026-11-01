"""API endpoints for model performance, metadata, and status (T4.2, RULES D5-D6)."""

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.errors import AppError
from backend.app.ml.registry import get_model_registry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_models():
    """List all models with current version, training status, and headline metrics next to baselines."""
    registry = get_model_registry()
    models = registry.list_models()
    return {
        "data": models,
        "meta": {
            "total_models": len(models),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/{model_name}")
def get_model_detail(model_name: str):
    """Retrieve full metrics.json, model card markdown, and training manifest for a model."""
    registry = get_model_registry()
    known = ["bug_risk", "repo_health", "maintenance_effort", "doc_sections", "repo_clusters"]
    if model_name not in known:
        raise AppError("NOT_FOUND", f"Model '{model_name}' is not recognized.", status_code=404)

    meta = registry.get_model_metadata(model_name)
    if not meta.get("trained"):
        raise AppError("MODEL_NOT_TRAINED", f"Model '{model_name}' has not been trained.", status_code=503)

    return {
        "data": meta,
        "meta": {
            "model_name": model_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
