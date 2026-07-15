from app.core.config import load_settings
from app.core.config import Settings
import pytest


def test_settings_default_to_upstage_haiku_and_langfuse_disabled(monkeypatch) -> None:
    for name in [
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LANGFUSE_ENABLED",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.embedding_provider == "upstage"
    assert settings.embedding_model == "solar-embedding-1-large"
    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-haiku-4-5-20251001"
    assert not settings.langfuse_enabled


def test_settings_reads_optional_langfuse(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_CAPTURE_IO", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")

    settings = load_settings()

    assert settings.langfuse_enabled
    assert settings.langfuse_capture_io
    assert settings.langfuse_public_key == "pk"
    assert settings.langfuse_secret_key == "sk"


def test_rag_provider_concurrency_cannot_exceed_item_concurrency() -> None:
    with pytest.raises(ValueError, match="RAG_EMBEDDING_CONCURRENCY"):
        Settings(rag_item_concurrency=2, rag_embedding_concurrency=3)
    with pytest.raises(ValueError, match="RAG_LLM_CONCURRENCY"):
        Settings(rag_item_concurrency=2, rag_llm_concurrency=3)


def test_settings_repr_masks_secrets(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/app")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("YOUTUBE_API_KEY", "youtube-secret")

    rendered = repr(load_settings())

    assert "password" not in rendered
    assert "admin-secret" not in rendered
    assert "youtube-secret" not in rendered


def test_production_settings_reject_unsafe_defaults() -> None:
    with pytest.raises(ValueError):
        Settings(app_env="production")


def test_production_settings_accept_complete_runtime_config() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg://user:password@db/app",
        admin_token="strong-admin-token",
        pipeline_mode="production",
        youtube_api_key="youtube",
        anthropic_api_key="llm",
        upstage_api_key="embedding",
    )
    assert settings.pipeline_mode == "production"
