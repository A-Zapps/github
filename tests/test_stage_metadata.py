"""Unit tests for Stage 1 (resolve) and Stage 2 (metadata) analysis pipeline."""

import asyncio
import base64

import httpx
import pytest
import respx

from backend.app.main import create_app


@pytest.mark.asyncio
@respx.mock
async def test_stage_metadata_returns_repository_data():
    """Verify Stage 2 stores metadata and GET /analyses/{id}/repository returns accurate repository info."""
    # Mock all GitHub API endpoints invoked in Stages 1 & 2
    respx.get("https://api.github.com/repos/pallets/flask").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "pallets/flask",
                "description": "The Python micro framework for building web applications.",
                "stargazers_count": 68500,
                "forks_count": 16200,
                "watchers_count": 68500,
                "default_branch": "main",
                "size": 18500,
                "license": {"spdx_id": "BSD-3-Clause"},
            },
        )
    )

    respx.get("https://api.github.com/repos/pallets/flask/commits/main").mock(
        return_value=httpx.Response(200, json={"sha": "4e1a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a"})
    )

    respx.get("https://api.github.com/repos/pallets/flask/languages").mock(
        return_value=httpx.Response(200, json={"Python": 92000, "HTML": 8000})
    )

    respx.get("https://api.github.com/repos/pallets/flask/contributors").mock(
        return_value=httpx.Response(200, json=[{"id": 1}, {"id": 2}, {"id": 3}])
    )

    respx.get("https://api.github.com/repos/pallets/flask/releases").mock(
        return_value=httpx.Response(200, json=[{"id": 101}, {"id": 102}])
    )

    respx.get("https://api.github.com/repos/pallets/flask/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "state": "open"},
                {"id": 2, "state": "closed"},
                {"id": 3, "state": "open", "pull_request": {}},
            ],
        )
    )

    respx.get("https://api.github.com/repos/pallets/flask/stats/commit_activity").mock(
        return_value=httpx.Response(200, json=[{"total": 12, "week": 1700000000}])
    )

    readme_bytes = b"# Flask\nFlask is a lightweight WSGI web application framework."
    respx.get("https://api.github.com/repos/pallets/flask/readme").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "README.md",
                "encoding": "base64",
                "content": base64.b64encode(readme_bytes).decode("ascii"),
            },
        )
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Enqueue analysis
        post_resp = await client.post("/api/v1/analyses", json={"repo": "pallets/flask"})
        assert post_resp.status_code == 202
        analysis_id = post_resp.json()["data"]["analysis_id"]

        # Allow background pipeline to execute Stages 1 & 2
        await asyncio.sleep(0.6)

        # Fetch repository result
        resp = await client.get(f"/api/v1/analyses/{analysis_id}/repository")
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert data["full_name"] == "pallets/flask"
        assert data["stars"] == 68500
        assert data["forks"] == 16200
        assert data["license"] == "BSD-3-Clause"
        assert data["languages"]["Python"] == 92.0
        assert data["languages"]["HTML"] == 8.0
        assert data["contributors_count"] == 3
        assert data["releases_count"] == 2
        assert data["open_issues"] == 1
        assert data["closed_issues"] == 1
        assert data["open_prs"] == 1
        assert "Flask is a lightweight" in data["readme"]["content"]
