"""Application configuration loaded from environment variables and .env file."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for GitHub Repository Analyzer."""

    # GitHub API
    GITHUB_TOKEN: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # Paths
    DATA_DIR: str = "./data"
    MODELS_DIR: str = "./models"

    # Analysis & Cache limits
    CACHE_TTL_SECONDS: int = 3600
    MAX_REPO_SIZE_MB: int = 300
    MAX_FILES: int = 3000
    MAX_FILE_KB: int = 500
    HISTORY_MONTHS: int = 12
    MAX_CONCURRENT_ANALYSES: int = 2

    # Feature flags
    ENABLE_SEMGREP: bool = False
    ENABLE_CODEBERT: bool = False
    ENABLE_ASSISTANT_INDEX: bool = True

    # Assistant & RAG
    LLM_PROVIDER: str = "none"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Training
    TRAIN_MAX_REPO_MB: int = 150

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    return Settings()
