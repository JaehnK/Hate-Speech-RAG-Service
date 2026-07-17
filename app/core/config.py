from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
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
    api_docs_enabled: bool = False
    log_level: str = "INFO"
    database_url: str = Field(default="sqlite:///./hatespeech.db", repr=False)
    admin_token: str = Field(default="change-me", repr=False)
    frontend_origin: str = "http://localhost:3000"
    google_client_id: str | None = Field(default=None, repr=False)
    google_client_secret: str | None = Field(default=None, repr=False)
    google_oauth_redirect_uri: str = "http://localhost:3000/api/auth/google/callback"
    session_cookie_name: str = "hsr_session"
    session_cookie_domain: str | None = None
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=1209600, ge=300)
    api_key_encryption_key: str | None = Field(default=None, repr=False)
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
    embedding_model: str = "embedding"
    embedding_api_key: str | None = Field(default=None, repr=False)
    upstage_embedding_base_url: str = "https://api.upstage.ai/v1/embeddings"
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
        if self.session_cookie_domain == "":
            object.__setattr__(self, "session_cookie_domain", None)
        if self.embedding_api_key is None:
            object.__setattr__(self, "embedding_api_key", self.upstage_api_key)
        if self.llm_api_key is None:
            object.__setattr__(self, "llm_api_key", self.anthropic_api_key)

    upstage_api_key: str | None = Field(default=None, repr=False)
    anthropic_api_key: str | None = Field(default=None, repr=False)

    @property
    def auth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.api_key_encryption_key)

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.api_key_encryption_key:
            try:
                Fernet(self.api_key_encryption_key.encode())
            except (TypeError, ValueError) as exc:
                raise ValueError("API_KEY_ENCRYPTION_KEY must be a valid Fernet key") from exc
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
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE=true is required in production")
            frontend = urlsplit(self.frontend_origin)
            redirect = urlsplit(self.google_oauth_redirect_uri)
            if frontend.scheme != "https" or redirect.scheme != "https":
                raise ValueError("HTTPS frontend and Google OAuth redirect URIs are required in production")
            if (frontend.scheme, frontend.netloc) != (redirect.scheme, redirect.netloc):
                raise ValueError("GOOGLE_OAUTH_REDIRECT_URI must use FRONTEND_ORIGIN in production")
            auth_missing = [
                name
                for name, value in (
                    ("GOOGLE_CLIENT_ID", self.google_client_id),
                    ("GOOGLE_CLIENT_SECRET", self.google_client_secret),
                    ("API_KEY_ENCRYPTION_KEY", self.api_key_encryption_key),
                )
                if not value
            ]
            if auth_missing:
                raise ValueError(f"Missing production auth settings: {', '.join(auth_missing)}")
        if self.pipeline_mode == "production":
            missing = []
            if not self.youtube_api_key:
                missing.append("YOUTUBE_API_KEY")
            if not self.auth_configured and not self.llm_api_key:
                missing.append("LLM_API_KEY or ANTHROPIC_API_KEY")
            if not self.auth_configured and self.embedding_provider != "hash" and not self.embedding_api_key:
                missing.append("EMBEDDING_API_KEY or UPSTAGE_API_KEY")
            if missing:
                raise ValueError(f"Missing production pipeline settings: {', '.join(missing)}")
        return self


def load_settings() -> Settings:
    return Settings()
