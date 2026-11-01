"""Unit tests for GitHubClient using respx mocks."""

import httpx
import pytest
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.github_client import GitHubClient
from backend.app.db.models import Base, GitHubCache
from backend.app.errors import AppError


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.asyncio
@respx.mock
async def test_etag_304_returns_cached_data(in_memory_db):
    """Verify that a 304 response returns cached body from DB without failure."""
    url = "https://api.github.com/repos/pallets/flask"
    # Seed cache
    in_memory_db.add(GitHubCache(url=url, etag="etag123", body={"name": "flask", "stars": 60000}))
    in_memory_db.commit()

    # Mock 304
    respx.get(url).mock(return_value=httpx.Response(304, headers={"ETag": "etag123"}))

    client = GitHubClient(token="fake_token")
    data = await client.request("GET", url, db=in_memory_db)
    assert data["name"] == "flask"
    assert data["stars"] == 60000
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_403_rate_limit_with_retry_after():
    """Verify 403 rate limit with Retry-After header raises GITHUB_RATE_LIMITED."""
    url = "https://api.github.com/repos/pallets/flask"
    respx.get(url).mock(return_value=httpx.Response(
        403,
        headers={"Retry-After": "1", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"}
    ))

    client = GitHubClient(token="fake_token")
    with pytest.raises(AppError) as exc_info:
        await client.request("GET", url, max_retries=1)

    assert exc_info.value.code == "GITHUB_RATE_LIMITED"
    assert exc_info.value.status_code == 429
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_202_accepted_then_200():
    """Verify that 202 (stats computing) retries until 200 OK is returned."""
    url = "https://api.github.com/repos/pallets/flask/stats/commit_activity"
    route = respx.get(url)
    route.side_effect = [
        httpx.Response(202),
        httpx.Response(200, json=[{"total": 5, "week": 1700000000}]),
    ]

    client = GitHubClient(token="fake_token")
    data = await client.request("GET", url, max_retries=2)
    assert isinstance(data, list)
    assert data[0]["total"] == 5
    await client.close()


@pytest.mark.asyncio
async def test_blocked_host_rejected():
    """Verify that requests to disallowed outbound hosts are blocked (RULES B6)."""
    disallowed_url = "https://evil-attacker.com/malicious"
    client = GitHubClient(token="fake_token")

    with pytest.raises(AppError) as exc_info:
        await client.request("GET", disallowed_url)

    assert "Outbound request to blocked host" in exc_info.value.message
    await client.close()
