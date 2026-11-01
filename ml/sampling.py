"""Stratified repository sampler across languages and activity tiers (RULES D1 & ARCHITECTURE 9.6)."""

import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TARGET_LANGUAGES = ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++"]

# Curated reference seed repositories across languages and activity tiers for offline/deterministic runs
REFERENCE_SAMPLE_REPOS = [
    # Python
    {"repo": "pallets/flask", "language": "Python", "activity_tier": "high"},
    {"repo": "psf/requests", "language": "Python", "activity_tier": "high"},
    {"repo": "bottlepy/bottle", "language": "Python", "activity_tier": "medium"},
    {"repo": "marshmallow-code/marshmallow", "language": "Python", "activity_tier": "medium"},
    {"repo": "kennethreitz/responder", "language": "Python", "activity_tier": "low"},
    # JavaScript / TypeScript
    {"repo": "expressjs/express", "language": "JavaScript", "activity_tier": "high"},
    {"repo": "sindresorhus/got", "language": "JavaScript", "activity_tier": "medium"},
    {"repo": "visionmedia/superagent", "language": "JavaScript", "activity_tier": "medium"},
    {"repo": "fastify/fastify", "language": "TypeScript", "activity_tier": "high"},
    {"repo": "colinhacks/zod", "language": "TypeScript", "activity_tier": "high"},
    # Go
    {"repo": "gin-gonic/gin", "language": "Go", "activity_tier": "high"},
    {"repo": "gorilla/mux", "language": "Go", "activity_tier": "low"},
    {"repo": "spf13/cobra", "language": "Go", "activity_tier": "high"},
    # Rust
    {"repo": "serde-rs/serde", "language": "Rust", "activity_tier": "high"},
    {"repo": "BurntSushi/ripgrep", "language": "Rust", "activity_tier": "high"},
    {"repo": "clap-rs/clap", "language": "Rust", "activity_tier": "high"},
    # Java
    {"repo": "square/retrofit", "language": "Java", "activity_tier": "medium"},
    {"repo": "google/gson", "language": "Java", "activity_tier": "low"},
]


def sample_repositories(
    target_count: int = 20,
    seed: int = 42,
    custom_list: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Return a stratified list of repositories for dataset extraction."""
    if custom_list:
        return [{"repo": r, "language": "Unknown", "activity_tier": "custom"} for r in custom_list]

    # Deterministic sampling based on seed hash
    sorted_candidates = sorted(REFERENCE_SAMPLE_REPOS, key=lambda x: hashlib.sha256(f"{seed}-{x['repo']}".encode()).hexdigest())
    return sorted_candidates[:target_count]
