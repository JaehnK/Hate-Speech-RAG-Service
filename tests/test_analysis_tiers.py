import httpx
import pytest

from app.analysis.analysis_tiers import DEFAULT_TIER, TIERS, available_tiers, resolve_tier
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import Base
from app.main import create_app
from app.worker_main import _analysis_run_values


def _settings(tmp_path=None, **overrides) -> Settings:
    values = {"_env_file": None, **overrides}
    if tmp_path is not None:
        values["database_url"] = f"sqlite:///{tmp_path / 'jobs.db'}"
    return Settings(**values)


def test_economy_tier_needs_jev_enabled() -> None:
    off = _settings()
    on = _settings(jev_prefilter_enabled=True, typesafe_api_key="k")

    assert "economy" not in [tier.key for tier in available_tiers(off)]
    assert [tier.key for tier in available_tiers(on)] == list(TIERS)
    with pytest.raises(DomainError):
        resolve_tier("economy", off)
    assert resolve_tier("economy", on).jev_prefilter is True


def test_missing_tier_defaults_and_unknown_tier_is_rejected() -> None:
    settings = _settings()
    assert resolve_tier(None, settings).key == DEFAULT_TIER
    with pytest.raises(DomainError) as error:
        resolve_tier("turbo", settings)
    assert error.value.status_code == 422


def test_run_values_record_tier_model() -> None:
    values = _analysis_run_values(_settings(), TIERS["max"])

    assert values["llm_model"] == TIERS["max"].model
    assert values["retriever_config"]["analysis_tier"] == "max"
    assert values["retriever_config"]["jev_prefilter"]["enabled"] is False


@pytest.mark.asyncio
async def test_job_api_lists_tiers_and_stores_selection(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    Base.metadata.create_all(app.state.engine)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tiers = await client.get("/api/analysis-jobs/tiers")
        created = await client.post(
            "/api/analysis-jobs", json={"input_value": "abcdefghijk", "analysis_tier": "precise"}
        )
        unavailable = await client.post(
            "/api/analysis-jobs", json={"input_value": "abcdefghijk", "analysis_tier": "economy"}
        )
        status = await client.get(created.json()["status_url"])

    assert tiers.status_code == 200
    assert tiers.json()["default"] == DEFAULT_TIER
    assert "economy" not in [item["key"] for item in tiers.json()["items"]]
    assert created.status_code == 202
    assert status.json()["analysis_tier"] == "precise"
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "ANALYSIS_TIER_UNAVAILABLE"
