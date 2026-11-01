"""Application error definitions and FastAPI error envelope handlers."""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Standard error codes from ARCHITECTURE.md section 6
CODE_STATUS_MAP: Dict[str, int] = {
    "INVALID_REPO_NAME": 400,
    "VALIDATION_ERROR": 400,
    "GITHUB_AUTH_FAILED": 401,
    "REPO_NOT_FOUND": 404,
    "NOT_FOUND": 404,
    "ANALYSIS_NOT_READY": 409,
    "UNSUPPORTED_LANGUAGE": 422,
    "GITHUB_RATE_LIMITED": 429,
    "STAGE_FAILED": 500,
    "INTERNAL": 500,
    "MODEL_NOT_TRAINED": 503,
    "LLM_NOT_CONFIGURED": 503,
}


class AppError(Exception):
    """Application-level exception rendered via the standard error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code or CODE_STATUS_MAP.get(code, 400)


def format_error_envelope(code: str, message: str, details: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Build the standard error envelope structure."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    """Attach standard exception handlers to the FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_envelope(exc.code, exc.message, exc.details, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=400,
            content=format_error_envelope(
                "VALIDATION_ERROR",
                "The request body or parameters failed validation.",
                {"errors": exc.errors()},
                request_id,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        code = "NOT_FOUND" if exc.status_code == 404 else "INTERNAL"
        message = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_envelope(code, message, {}, request_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        logger.exception("Unhandled server exception: %s", str(exc), extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content=format_error_envelope(
                "INTERNAL",
                "An unexpected internal error occurred.",
                {},
                request_id,
            ),
        )
