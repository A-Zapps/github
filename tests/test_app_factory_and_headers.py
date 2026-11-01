"""Tests for app factory, health check, static mounting, and security headers."""

import pytest
import httpx
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_healthz_endpoint_and_security_headers():
    """Verify healthz returns expected envelope and all 4 security headers."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")
        assert response.status_code == 200

        # Check payload envelope
        body = response.json()
        assert "data" in body
        assert body["data"]["status"] == "ok"
        assert "meta" in body
        assert body["meta"]["analyzer_version"] == "1.0.0"

        # Check 4 mandatory security headers from RULES B9
        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_serves_frontend_shell_and_security_headers():
    """Verify root GET serves the frontend index.html with security headers."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "GitHub Repository Analyzer" in response.text

        # Verify headers also present on static shell response
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Content-Security-Policy" in response.headers
