from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.auth.google_oauth import GoogleIdentity
from app.auth.services import token_hash
from app.core.config import Settings
from app.db.base import Base
from app.db.models import UserApiKey, UserSession
from app.jobs.worker import JobWorker
from app.main import create_app


class FakeOAuthProvider:
    def authorization_url(self, state: str, code_challenge: str) -> str:
        return f"https://accounts.example/authorize?state={state}&challenge={code_challenge}"

    def exchange(self, code: str, code_verifier: str) -> GoogleIdentity:
        assert code == "test-code"
        assert code_verifier
        return GoogleIdentity("google-123", "tester@example.com", True, "테스터", None)


class FakeKeyValidator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def validate(self, provider: str, api_key: str) -> None:
        self.calls.append((provider, api_key))


def _settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        frontend_origin="http://test",
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        api_key_encryption_key=Fernet.generate_key().decode(),
    )


async def _login(client: httpx.AsyncClient) -> None:
    login = await client.get("/api/auth/google/login", follow_redirects=False)
    assert login.status_code == 302
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    callback = await client.get(
        "/api/auth/google/callback",
        params={"code": "test-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"


@pytest.mark.asyncio
async def test_google_session_and_encrypted_byok_lifecycle(tmp_path) -> None:
    validator = FakeKeyValidator()
    app = create_app(_settings(tmp_path), FakeOAuthProvider(), validator)
    Base.metadata.create_all(app.state.engine)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await _login(client)
        session_token = client.cookies.get("hsr_session")
        assert session_token

        current = await client.get("/api/auth/session")
        assert current.status_code == 200
        assert current.json()["email"] == "tester@example.com"
        assert current.json()["api_keys_registered"] == {"anthropic": False, "upstage": False}

        rejected = await client.put("/api/me/api-keys/anthropic", json={"api_key": "anthropic-secret"})
        assert rejected.status_code == 403

        headers = {"Origin": "http://test", "X-Requested-With": "hatespeechraw"}
        for provider, key in (("anthropic", "anthropic-secret"), ("upstage", "upstage-secret")):
            saved = await client.put(f"/api/me/api-keys/{provider}", json={"api_key": key}, headers=headers)
            assert saved.status_code == 200
            assert key not in saved.text
        listed = await client.get("/api/me/api-keys")
        assert {item["provider"] for item in listed.json()["items"]} == {"anthropic", "upstage"}

        created = await client.post(
            "/api/analysis-jobs",
            json={"input_value": "abcdefghijk"},
            headers=headers,
        )
        assert created.status_code == 202

        logged_out = await client.post("/api/auth/logout", headers=headers)
        assert logged_out.status_code == 204
        assert (await client.get("/api/auth/session")).status_code == 401

    with app.state.session_factory() as session:
        stored_session = session.scalar(select(UserSession))
        assert stored_session is not None
        assert stored_session.session_token_hash == token_hash(session_token)
        assert session_token not in stored_session.session_token_hash
        rows = list(session.scalars(select(UserApiKey)))
        assert len(rows) == 2
        assert all(row.encrypted_key not in {b"anthropic-secret", b"upstage-secret"} for row in rows)
        assert stored_session.revoked_at is not None
    assert validator.calls == [("anthropic", "anthropic-secret"), ("upstage", "upstage-secret")]


@pytest.mark.asyncio
async def test_google_callback_denial_uses_stable_error_contract(tmp_path) -> None:
    app = create_app(_settings(tmp_path), FakeOAuthProvider(), FakeKeyValidator())
    Base.metadata.create_all(app.state.engine)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/auth/google/callback", params={"error": "access_denied"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OAUTH_CALLBACK_FAILED"


@pytest.mark.asyncio
async def test_private_report_is_owner_only_until_admin_publishes_sample(tmp_path) -> None:
    app = create_app(_settings(tmp_path), FakeOAuthProvider(), FakeKeyValidator())
    Base.metadata.create_all(app.state.engine)
    transport = httpx.ASGITransport(app=app)
    headers = {"Origin": "http://test", "X-Requested-With": "hatespeechraw"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as owner:
        await _login(owner)
        for provider in ("anthropic", "upstage"):
            await owner.put(f"/api/me/api-keys/{provider}", json={"api_key": f"{provider}-secret"}, headers=headers)
        created = await owner.post("/api/analysis-jobs", json={"input_value": "abcdefghijk"}, headers=headers)
        assert JobWorker(app.state.session_factory).run_once()
        job = await owner.get(created.json()["status_url"])
        report_path = job.json()["links"]["report_api"]
        assert (await owner.get(report_path)).status_code == 200

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as visitor:
        assert (await visitor.get(report_path)).status_code == 401
        assert (await visitor.get("/api/reports/public")).json()["items"] == []
        report_id = report_path.rsplit("/", 1)[-1]
        published = await visitor.put(
            f"/api/admin/reports/{report_id}/public-sample",
            headers={"X-Admin-Token": "change-me"},
        )
        assert published.status_code == 200
        assert (await visitor.get(report_path)).status_code == 200
        assert (await visitor.get("/api/reports/public")).json()["total"] == 1
        export = await visitor.post(
            f"{report_path}/exports",
            json={"format": "html"},
            headers=headers,
        )
        assert export.status_code == 401
