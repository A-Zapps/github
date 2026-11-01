"""Repository name normalization and validation (RULES B4)."""

import re

from backend.app.errors import AppError

REPO_NAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


def normalize_and_validate_repo_name(raw_name: str) -> str:
    """Normalize input URL or owner/name string and enforce strict validation.

    Examples accepted:
      'pallets/flask' -> 'pallets/flask'
      'https://github.com/pallets/flask.git' -> 'pallets/flask'
      'http://github.com/pallets/flask/' -> 'pallets/flask'

    Examples rejected:
      '../etc'
      '/root/passwords'
      'flask'
      'pallets/flask/sub'
      'owner;rm -rf /'
    """
    if not raw_name or not isinstance(raw_name, str):
        raise AppError("INVALID_REPO_NAME", "Repository name must be a non-empty string.", status_code=400)

    clean = raw_name.strip()

    # Reject leading slashes or absolute path attempts
    if clean.startswith(("/", "\\")):
        raise AppError("INVALID_REPO_NAME", "Repository name cannot start with a slash.", status_code=400)

    # Strip URL prefixes
    prefixes = ["https://github.com/", "http://github.com/", "git@github.com:", "github.com/"]
    for p in prefixes:
        if clean.startswith(p):
            clean = clean[len(p):]
            break

    # Strip .git suffix and trailing slash only
    if clean.endswith(".git"):
        clean = clean[:-4]
    clean = clean.rstrip("/")

    if not REPO_NAME_REGEX.match(clean) or ".." in clean or "\\" in clean:
        raise AppError(
            "INVALID_REPO_NAME",
            f"Invalid repository name '{raw_name}'. Must match 'owner/repo' format without path traversal.",
            status_code=400,
        )

    return clean
