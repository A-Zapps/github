"""Settings endpoint reporting non-secret configuration parameters."""

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_public_settings():
    """Retrieve non-sensitive runtime configuration parameters (RULES B7)."""
    settings = get_settings()
    return {
        "data": {
            "github_token_configured": bool(settings.GITHUB_TOKEN and len(settings.GITHUB_TOKEN) > 4),
            "cache_ttl_seconds": settings.CACHE_TTL_SECONDS,
            "max_repo_size_mb": settings.MAX_REPO_SIZE_MB,
            "max_files": settings.MAX_FILES,
            "max_file_kb": settings.MAX_FILE_KB,
            "history_months": settings.HISTORY_MONTHS,
            "llm_provider": settings.LLM_PROVIDER,
            "enable_semgrep": settings.ENABLE_SEMGREP,
            "enable_codebert": settings.ENABLE_CODEBERT,
        },
        "meta": {
            "analysis_id": None,
            "head_sha": None,
            "analyzer_version": "1.0.0",
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
