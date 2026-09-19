"""Application configuration loaded from environment variables / ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Source checkout root (editable install) or the working directory (container image)."""
    here = Path(__file__).resolve().parents[2]
    return here if (here / "pyproject.toml").exists() else Path.cwd()


PROJECT_ROOT = _find_project_root()


class Settings(BaseSettings):
    """Runtime settings. Every field can be overridden with an environment variable."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- general -------------------------------------------------------------------------------
    app_name: str = "LLM Eval Platform"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- database ------------------------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./evalplatform.db"
    database_echo: bool = False
    auto_create_tables: bool = True
    """Create tables on startup (handy for SQLite/local). Docker uses Alembic instead."""

    # --- providers -----------------------------------------------------------------------------
    default_provider: str = "mock"
    anthropic_api_key: str | None = None
    anthropic_default_model: str = "claude-sonnet-5"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_default_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.1"
    provider_timeout_s: float = 60.0
    mock_latency_scale: float = 1.0
    """Multiplier for simulated mock latency (0 disables sleeping; used in tests)."""

    # --- judge ---------------------------------------------------------------------------------
    judge_provider: str = "mock"
    judge_model: str = "mock-judge"

    # --- embeddings (semantic similarity) --------------------------------------------------------
    embedding_provider: Literal["lexical", "openai"] = "lexical"
    embedding_model: str = "text-embedding-3-small"

    # --- experiments ---------------------------------------------------------------------------
    default_concurrency: int = 8
    max_concurrency: int = 64

    # --- monitoring ----------------------------------------------------------------------------
    monitoring_metrics: list[str] = Field(
        default_factory=lambda: [
            "answer_relevancy",
            "faithfulness",
            "toxicity",
            "pii_leakage",
            "prompt_injection",
            "latency_ms",
            "cost_usd",
        ]
    )
    monitoring_workers: int = 2

    # --- tracing -------------------------------------------------------------------------------
    otel_enabled: bool = True
    otel_service_name: str = "llm-eval-platform"
    otel_exporter: Literal["none", "console", "otlp"] = "none"
    otel_exporter_otlp_endpoint: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- pricing -------------------------------------------------------------------------------
    pricing_file: Path | None = None
    """Optional YAML/JSON file overriding the built-in per-model pricing table."""

    # --- frontend ------------------------------------------------------------------------------
    serve_frontend: bool = True
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Accept the URLs most hosting providers hand out and upgrade them to async drivers.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        if v.startswith("sqlite:///"):
            v = "sqlite+aiosqlite:///" + v.removeprefix("sqlite:///")
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
