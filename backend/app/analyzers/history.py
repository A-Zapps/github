"""History analyzer exposing git log parser and history features."""

from backend.app.ml.features import (
    compute_file_history_features,
    compute_repo_history_features,
    is_bugfix_message,
    parse_git_log_history,
)

__all__ = [
    "parse_git_log_history",
    "compute_file_history_features",
    "compute_repo_history_features",
    "is_bugfix_message",
]
