import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_health_and_readiness(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
        assert (await client.get("/api/health/readiness")).json() == {"status": "ready"}
