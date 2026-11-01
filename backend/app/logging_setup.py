"""JSON-line structured logging with automated secret and token redaction."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

# Patterns to redact from log messages
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{36,255}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{50,255}"),
    re.compile(r"gho_[A-Za-z0-9_]{36,255}"),
    re.compile(r"ghu_[A-Za-z0-9_]{36,255}"),
    re.compile(r"ghs_[A-Za-z0-9_]{36,255}"),
    re.compile(r"ghr_[A-Za-z0-9_]{36,255}"),
    re.compile(r"Bearer\s+([A-Za-z0-9\-\._~\+\/]+=*)", re.IGNORECASE),
    re.compile(r"token\s+([A-Za-z0-9\-\._~\+\/]+=*)", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,255}"),
    re.compile(r"(api[_-]?key|secret|password|access[_-]?token)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.]{8,})[\"']?", re.IGNORECASE),
]


class SecretRedactionFilter(logging.Filter):
    """Filter that scrubs secrets and tokens from log messages."""

    def __init__(self, additional_secrets: list[str] | None = None) -> None:
        super().__init__()
        self.additional_secrets = [s for s in (additional_secrets or []) if s and len(s) >= 4]

    def redact(self, text: str) -> str:
        """Replace all recognized secret patterns with [REDACTED]."""
        if not text:
            return text

        result = text
        for secret in self.additional_secrets:
            result = result.replace(secret, "[REDACTED]")

        for pattern in TOKEN_PATTERNS:
            result = pattern.sub("[REDACTED]", result)

        return result

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact record msg and args."""
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(a) if isinstance(a, str) else a for a in record.args)
        return True


class JSONLogFormatter(logging.Formatter):
    """Format logs as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", ""),
            "analysis_id": getattr(record, "analysis_id", None),
            "stage": getattr(record, "stage", None),
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", known_secrets: list[str] | None = None) -> SecretRedactionFilter:
    """Configure root logger with JSON formatting and redaction filter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    redaction_filter = SecretRedactionFilter(known_secrets)
    stream_handler.addFilter(redaction_filter)
    stream_handler.setFormatter(JSONLogFormatter())

    root_logger.addHandler(stream_handler)
    return redaction_filter
