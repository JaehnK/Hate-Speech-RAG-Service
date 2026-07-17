import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_health_and_readiness(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.json() == {"status": "ok"}
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert "cdn.jsdelivr.net" not in health.headers["content-security-policy"]
        readiness = (await client.get("/api/health/readiness")).json()
        assert readiness["status"] == "ok"
        assert readiness["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_docs_csp_allows_swagger_assets_only_on_docs(tmp_path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}", api_docs_enabled=True)
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        docs = await client.get("/docs")
        redoc = await client.get("/redoc")

    assert docs.status_code == 200
    assert "https://cdn.jsdelivr.net/npm/swagger-ui-dist" in docs.text
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in redoc.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_developer_api_surfaces_are_disabled_by_default(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.get("/docs"),
            await client.get("/redoc"),
            await client.get("/openapi.json"),
            await client.get("/docs/oauth2-redirect"),
        ]

    assert all(response.status_code == 404 for response in responses)


@pytest.mark.asyncio
async def test_production_cannot_enable_developer_api_surfaces() -> None:
    settings = Settings(
        app_env="production",
        api_docs_enabled=True,
        database_url="postgresql+psycopg://user:pass@localhost/db",
        admin_token="production-admin-token",
        pipeline_mode="production",
        youtube_api_key="youtube-key",
        llm_api_key="llm-key",
        embedding_api_key="embedding-key",
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        api_key_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=True,
        frontend_origin="https://example.test",
        google_oauth_redirect_uri="https://example.test/api/auth/google/callback",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.get("/docs"),
            await client.get("/redoc"),
            await client.get("/openapi.json"),
        ]

    assert all(response.status_code == 404 for response in responses)
