"""Application factory and entrypoint for GitHub Repository Analyzer."""

import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.errors import register_error_handlers
from backend.app.logging_setup import setup_logging

ANALYZER_VERSION = "1.0.0"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, known_secrets=[settings.GITHUB_TOKEN] if settings.GITHUB_TOKEN else None)

    app = FastAPI(
        title="GitHub Repository Analyzer",
        version=ANALYZER_VERSION,
        docs_url=None,
        redoc_url=None,
    )

    # Middleware: Request ID and Security Headers
    @app.middleware("http")
    async def app_middleware(request: Request, call_next) -> Response:
        # Assign or preserve unique request ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id

        response: Response = await call_next(request)

        # Enforce Security Headers (RULES B9)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Request-ID"] = req_id

        return response

    # Register standardized error handlers
    register_error_handlers(app)

    # API v1 Health Check
    @app.get("/api/v1/healthz")
    async def healthz():
        return {
            "data": {"status": "ok"},
            "meta": {
                "analysis_id": None,
                "head_sha": None,
                "analyzer_version": ANALYZER_VERSION,
                "model_versions": {},
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # Mount static frontend directory
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))
    if os.path.isdir(frontend_dir):
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
