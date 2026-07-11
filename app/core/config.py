from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(default="sqlite:///./hatespeech.db", repr=False)
    admin_token: str = Field(default="change-me", repr=False)
    report_storage_dir: str = "data/reports"
    youtube_api_key: str | None = Field(default=None, repr=False)
    worker_poll_interval_seconds: float = 2.0
    worker_stale_after_seconds: int = 900
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


def load_settings() -> Settings:
    return Settings()
