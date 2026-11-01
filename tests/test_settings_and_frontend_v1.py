"""Unit tests for Settings API, Rate-Limit API, and Phase 1 frontend integrations."""

import httpx
import pytest

from backend.app.main import create_app


@pytest.mark.asyncio
async def test_settings_endpoint_does_not_leak_secrets():
    """Verify GET /api/v1/settings returns public config without exposing raw tokens (RULES B7)."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert "github_token_configured" in data
        assert isinstance(data["github_token_configured"], bool)
        assert "cache_ttl_seconds" in data
        assert "max_repo_size_mb" in data
        assert "max_files" in data

        # Ensure no token values leaked in response text
        raw_text = resp.text
        assert "ghp_" not in raw_text
        assert "github_pat_" not in raw_text


@pytest.mark.asyncio
async def test_rate_limit_endpoint():
    """Verify GET /api/v1/github/rate-limit returns live limit status."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/github/rate-limit")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["remaining"] in data or isinstance(data["remaining"], int)
        assert "limit" in data
        assert data["limit"] in (60, 5000)


def test_quality_page_implementation():
    """Verify quality.js page implementation conforms to F2 design requirements."""
    import os
    quality_js_path = os.path.join(
        os.path.dirname(__file__), "../frontend/js/pages/quality.js"
    )
    with open(quality_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "renderQualityPage" in content
    assert "getQualityData" in content
    assert "makeChartContainer" in content
    assert "createHorizontalBarChart" in content
    assert "estimate from fixed rules, not measured" in content
    assert "Worst 10" in content
