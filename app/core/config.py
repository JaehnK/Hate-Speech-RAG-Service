from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    chroma_persist_directory: str = ".chroma"
    embedding_provider: str = "upstage"
    embedding_model: str = "solar-embedding-1-large"
    embedding_api_key: str | None = None
    upstage_embedding_base_url: str = "https://api.upstage.ai/v1/solar/embeddings"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_api_key: str | None = None
    llm_max_tokens: int = 1200
    llm_temperature: float = 0.0
    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_capture_io: bool = False


def load_settings() -> Settings:
    return Settings(
        chroma_persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", ".chroma"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "upstage"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "solar-embedding-1-large"),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("UPSTAGE_API_KEY"),
        upstage_embedding_base_url=os.getenv(
            "UPSTAGE_EMBEDDING_BASE_URL",
            "https://api.upstage.ai/v1/solar/embeddings",
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_model=os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"),
        llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1200")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        langfuse_enabled=_env_bool("LANGFUSE_ENABLED", default=False),
        langfuse_host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_capture_io=_env_bool("LANGFUSE_CAPTURE_IO", default=False),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
