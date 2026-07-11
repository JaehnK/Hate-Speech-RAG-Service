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
        readiness = (await client.get("/api/health/readiness")).json()
        assert readiness["status"] == "ok"
        assert readiness["checks"]["database"] == "ok"
