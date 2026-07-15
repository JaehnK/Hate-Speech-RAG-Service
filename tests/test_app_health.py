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
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        docs = await client.get("/docs")
        redoc = await client.get("/redoc")

    assert docs.status_code == 200
    assert "https://cdn.jsdelivr.net/npm/swagger-ui-dist" in docs.text
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in redoc.headers["content-security-policy"]
