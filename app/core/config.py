from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = Field(default="sqlite:///./hatespeech.db", repr=False)
    admin_token: str = Field(default="change-me", repr=False)
    report_storage_dir: str = "data/reports"
    youtube_api_key: str | None = Field(default=None, repr=False)
    worker_poll_interval_seconds: float = 2.0
    worker_stale_after_seconds: int = 900
    rag_execution_mode: Literal["sequential", "parallel"] = "sequential"
    rag_item_concurrency: int = Field(default=2, ge=1, le=16)
    rag_embedding_concurrency: int = Field(default=2, ge=1, le=16)
    rag_llm_concurrency: int = Field(default=2, ge=1, le=16)
    rag_item_max_attempts: int = Field(default=3, ge=1, le=5)
    rag_heartbeat_interval_seconds: int = Field(default=30, ge=5)
    rag_shutdown_grace_seconds: int = Field(default=30, ge=5)
    rag_request_timeout_seconds: int = Field(default=30, ge=5)
    pipeline_mode: Literal["fake", "production"] = "fake"
    chroma_persist_directory: str = ".chroma"
    embedding_provider: str = "upstage"
    embedding_model: str = "solar-embedding-1-large"
    embedding_api_key: str | None = Field(default=None, repr=False)
    upstage_embedding_base_url: str = "https://api.upstage.ai/v1/solar/embeddings"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_max_tokens: int = 1200
    llm_temperature: float = 0.0
    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_capture_io: bool = False

    def model_post_init(self, __context: object) -> None:
        if self.embedding_api_key is None:
            object.__setattr__(self, "embedding_api_key", self.upstage_api_key)
        if self.llm_api_key is None:
            object.__setattr__(self, "llm_api_key", self.anthropic_api_key)

    upstage_api_key: str | None = Field(default=None, repr=False)
    anthropic_api_key: str | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.rag_embedding_concurrency > self.rag_item_concurrency:
            raise ValueError("RAG_EMBEDDING_CONCURRENCY cannot exceed RAG_ITEM_CONCURRENCY")
        if self.rag_llm_concurrency > self.rag_item_concurrency:
            raise ValueError("RAG_LLM_CONCURRENCY cannot exceed RAG_ITEM_CONCURRENCY")
        if self.app_env == "production":
            if self.admin_token == "change-me":
                raise ValueError("ADMIN_TOKEN must be changed in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("PostgreSQL DATABASE_URL is required in production")
            if self.pipeline_mode != "production":
                raise ValueError("PIPELINE_MODE=production is required in production")
        if self.pipeline_mode == "production":
            missing = []
            if not self.youtube_api_key:
                missing.append("YOUTUBE_API_KEY")
            if not self.llm_api_key:
                missing.append("LLM_API_KEY or ANTHROPIC_API_KEY")
            if self.embedding_provider != "hash" and not self.embedding_api_key:
                missing.append("EMBEDDING_API_KEY or UPSTAGE_API_KEY")
            if missing:
                raise ValueError(f"Missing production pipeline settings: {', '.join(missing)}")
        return self


def load_settings() -> Settings:
    return Settings()
