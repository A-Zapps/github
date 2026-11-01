"""Shared asynchronous GitHub API client with ETag caching, rate-limit management, and host allowlisting."""

import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import GitHubCache
from backend.app.errors import AppError

logger = logging.getLogger(__name__)

# Outbound allowed hosts (RULES B6)
ALLOWED_HOSTS = {
    "api.github.com",
    "github.com",
    "api.osv.dev",
}


def is_host_allowed(url: str) -> bool:
    """Validate that the target URL matches an explicitly allowlisted host."""
    try:
        parsed = urlparse(url)
        return parsed.hostname in ALLOWED_HOSTS
    except Exception:
        return False


class GitHubClient:
    """High-performance async client for GitHub REST API with caching and resilience."""

    def __init__(self, token: Optional[str] = None, timeout: float = 30.0) -> None:
        self.token = token or get_settings().GITHUB_TOKEN
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(5)  # Concurrency limit (ARCHITECTURE 8)
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or initialize the underlying httpx AsyncClient."""
        current_token = self.token or get_settings().GITHUB_TOKEN
        if self._client is None or self._client.is_closed or self.token != current_token:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
            self.token = current_token
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GitHub-Repository-Analyzer/1.0",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
                follow_redirects=False,  # Follow redirects manually with host check
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        use_cache: bool = True,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute an HTTP request with host verification, ETag caching, and retry logic."""
        if not is_host_allowed(url):
            raise AppError("INTERNAL", f"Outbound request to blocked host: {url}", status_code=500)

        client = await self.get_client()
        etag: Optional[str] = None
        cached_entry: Optional[GitHubCache] = None

        # Check DB ETag cache if db session provided
        if use_cache and db and method.upper() == "GET":
            cache_key = url if not params else f"{url}?{httpx.QueryParams(params)}"
            cached_entry = db.query(GitHubCache).filter(GitHubCache.url == cache_key).first()
            if cached_entry and cached_entry.etag:
                etag = cached_entry.etag

        req_headers: Dict[str, str] = {}
        if etag:
            req_headers["If-None-Match"] = etag

        retries = 0
        backoff = 1.0

        async with self.semaphore:
            while retries <= max_retries:
                try:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        headers=req_headers if req_headers else None,
                    )
                except httpx.RequestError as exc:
                    if retries >= max_retries:
                        raise AppError("INTERNAL", f"Network error contacting GitHub API: {exc}", status_code=500)
                    retries += 1
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                # Handle redirects securely (RULES B6)
                if response.status_code in (301, 302, 307, 308):
                    location = response.headers.get("Location")
                    if not location or not is_host_allowed(location):
                        raise AppError("INTERNAL", f"Redirected to disallowed host: {location}", status_code=500)
                    url = location
                    retries += 1
                    continue

                # 304 Not Modified -> return cached payload
                if response.status_code == 304 and cached_entry:
                    return cached_entry.body

                # 202 Accepted (computing stats) -> backoff retry (ARCHITECTURE 8)
                if response.status_code == 202:
                    if retries >= max_retries:
                        return {"available": False}
                    retries += 1
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                # Rate Limit handling
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_time = response.headers.get("X-RateLimit-Reset")
                if remaining and int(remaining) < 10 and response.status_code == 200:
                    logger.warning("GitHub rate limit low: %s remaining (resets %s)", remaining, reset_time)

                if response.status_code in (403, 429):
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retries < max_retries:
                        wait_sec = min(float(retry_after), 10.0)
                        retries += 1
                        await asyncio.sleep(wait_sec)
                        continue

                    reset_str = ""
                    if reset_time and reset_time.isdigit():
                        try:
                            from datetime import datetime
                            reset_dt = datetime.fromtimestamp(int(reset_time))
                            reset_str = f" Resets at {reset_dt.strftime('%H:%M:%S')}."
                        except Exception:
                            pass

                    token_hint = "" if self.token else " Add GITHUB_TOKEN in .env to increase limit to 5,000 req/hr."
                    raise AppError(
                        "GITHUB_RATE_LIMITED",
                        f"GitHub API rate limit reached.{reset_str}{token_hint}",
                        {"remaining": remaining, "reset": reset_time},
                        status_code=429,
                    )

                if response.status_code == 401:
                    raise AppError("GITHUB_AUTH_FAILED", "GitHub API authentication failed. Verify GITHUB_TOKEN.", status_code=401)

                if response.status_code == 404:
                    raise AppError("REPO_NOT_FOUND", "Repository or resource was not found on GitHub.", status_code=404)

                if response.is_error:
                    raise AppError("INTERNAL", f"GitHub API error: HTTP {response.status_code}", status_code=response.status_code)

                # Successful 200 OK
                data = response.json()

                # Save to ETag cache
                new_etag = response.headers.get("ETag")
                if use_cache and db and method.upper() == "GET" and new_etag:
                    cache_key = url if not params else f"{url}?{httpx.QueryParams(params)}"
                    if cached_entry:
                        cached_entry.etag = new_etag
                        cached_entry.body = data
                    else:
                        db.add(GitHubCache(url=cache_key, etag=new_etag, body=data))
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()

                return data

            raise AppError("INTERNAL", "Exceeded maximum retries for GitHub API request.", status_code=500)

    async def get_rate_limit(self) -> Dict[str, Any]:
        """Fetch current rate limit status."""
        url = "https://api.github.com/rate_limit"
        client = await self.get_client()
        response = await client.get(url)
        if response.status_code == 200:
            return response.json()
        return {"resources": {"core": {"limit": 60, "remaining": 0, "reset": 0}}}


# Singleton instance
_github_client_instance: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Return singleton GitHubClient instance."""
    global _github_client_instance
    if _github_client_instance is None:
        _github_client_instance = GitHubClient()
    return _github_client_instance
