"""Tests for secret redaction logging and standardized error envelopes."""

import io
import json
import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.app.errors import AppError, register_error_handlers
from backend.app.logging_setup import JSONLogFormatter, SecretRedactionFilter


def test_token_redaction_in_log_lines():
    """Verify secrets and tokens are redacted from log outputs."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    redaction_filter = SecretRedactionFilter(["my_super_secret_token_12345"])
    handler.addFilter(redaction_filter)
    handler.setFormatter(JSONLogFormatter())

    test_logger = logging.getLogger("test_redaction")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    test_logger.info("Connecting using ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 and my_super_secret_token_12345")
    output = stream.getvalue()

    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in output
    assert "my_super_secret_token_12345" not in output
    assert "[REDACTED]" in output

    data = json.loads(output)
    assert "[REDACTED]" in data["message"]


def test_unknown_route_returns_error_envelope():
    """Verify that an unknown route returns 404 with standard error envelope."""
    app = FastAPI()
    register_error_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = "test-req-123"
        return await call_next(request)

    client = TestClient(app)
    response = client.get("/non-existent-route-404")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["error"]["request_id"] == "test-req-123"


def test_app_error_returns_custom_code_and_envelope():
    """Verify AppError returns corresponding status code and envelope."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/trigger-error")
    def trigger():
        raise AppError(code="REPO_NOT_FOUND", message="Repository was not found.", details={"repo": "owner/repo"})

    client = TestClient(app)
    response = client.get("/trigger-error")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "REPO_NOT_FOUND"
    assert data["error"]["message"] == "Repository was not found."
    assert data["error"]["details"] == {"repo": "owner/repo"}
