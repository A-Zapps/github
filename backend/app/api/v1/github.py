"""GitHub rate limit and utility API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.core.github_client import get_github_client

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/rate-limit")
async def get_rate_limit():
    """Retrieve remaining rate limits and reset timestamp from GitHub."""
    client = get_github_client()
    raw = await client.get_rate_limit()
    core = raw.get("resources", {}).get("core", {})
    return {
        "data": {
            "limit": core.get("limit", 60),
            "remaining": core.get("remaining", 60),
            "reset": core.get("reset", 0),
            "used": core.get("used", 0),
        },
        "meta": {
            "analysis_id": None,
            "head_sha": None,
            "analyzer_version": "1.0.0",
            "model_versions": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
