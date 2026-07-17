from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.crypto import KeyEncryptionService
from app.auth.google_oauth import GoogleIdentity
from app.core.errors import DomainError
from app.db.models import User, UserApiKey, UserSession, utcnow


SUPPORTED_KEY_PROVIDERS = {"anthropic", "upstage"}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


class OAuthStateCodec:
    def __init__(self, secret: str) -> None:
        self.secret = secret.encode()

    def encode(self, state: str, verifier: str, return_to: str) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps({"state": state, "verifier": verifier, "return_to": return_to}, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        signature = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def decode(self, value: str) -> dict[str, str]:
        try:
            payload, signature = value.rsplit(".", 1)
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("invalid signature")
            padded = payload + "=" * (-len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded))
            return {key: str(decoded[key]) for key in ("state", "verifier", "return_to")}
        except Exception as exc:
            raise DomainError("OAUTH_STATE_MISMATCH", "로그인 요청 상태가 일치하지 않습니다.") from exc


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_google_user(self, identity: GoogleIdentity) -> User:
        user = self.session.scalar(select(User).where(User.google_sub == identity.sub))
        if user is None:
            user = User(google_sub=identity.sub, email=identity.email)
            self.session.add(user)
        user.email = identity.email
        user.email_verified = identity.email_verified
        user.display_name = identity.display_name
        user.avatar_url = identity.avatar_url
        user.last_login_at = utcnow()
        self.session.flush()
        return user


class SessionService:
    def __init__(self, session: Session, ttl_seconds: int) -> None:
        self.session = session
        self.ttl_seconds = ttl_seconds

    def issue(self, user_id: UUID, user_agent: str | None, ip_address: str | None) -> str:
        token = secrets.token_urlsafe(32)
        now = utcnow()
        self.session.add(
            UserSession(
                user_id=user_id,
                session_token_hash=token_hash(token),
                user_agent=user_agent,
                ip_address=ip_address,
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(seconds=self.ttl_seconds),
            )
        )
        self.session.flush()
        return token

    def resolve(self, token: str | None) -> tuple[User, bool]:
        if not token:
            raise DomainError("SESSION_INVALID", "로그인이 필요합니다.", status_code=401)
        row = self.session.scalar(select(UserSession).where(UserSession.session_token_hash == token_hash(token)))
        if row is None:
            raise DomainError("SESSION_INVALID", "유효하지 않은 세션입니다.", status_code=401)
        now = utcnow()
        expires_at = _aware(row.expires_at)
        if row.revoked_at is not None or expires_at <= now:
            raise DomainError("SESSION_EXPIRED", "세션이 만료되었습니다.", status_code=401)
        user = self.session.get(User, row.user_id)
        if user is None:
            raise DomainError("SESSION_INVALID", "유효하지 않은 세션입니다.", status_code=401)
        if user.status == "suspended":
            raise DomainError("ACCOUNT_SUSPENDED", "정지된 계정입니다.", status_code=403)
        refresh = expires_at - now < timedelta(seconds=self.ttl_seconds / 2)
        row.last_seen_at = now
        if refresh:
            row.expires_at = now + timedelta(seconds=self.ttl_seconds)
        self.session.flush()
        return user, refresh

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        row = self.session.scalar(select(UserSession).where(UserSession.session_token_hash == token_hash(token)))
        if row is not None:
            row.revoked_at = utcnow()
            self.session.flush()


class ApiKeyValidator(Protocol):
    def validate(self, provider: str, api_key: str) -> None: ...


class ProviderApiKeyValidator:
    def __init__(self, upstage_url: str, http_client: httpx.Client | None = None) -> None:
        self.upstage_url = upstage_url
        self.http_client = http_client

    def validate(self, provider: str, api_key: str) -> None:
        client = self.http_client or httpx.Client(timeout=15)
        try:
            if provider == "anthropic":
                response = client.get(
                    "https://api.anthropic.com/v1/models?limit=1",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
            elif provider == "upstage":
                response = client.post(
                    self.upstage_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "embedding-query", "input": "key validation"},
                )
            else:
                raise DomainError("API_KEY_PROVIDER_UNSUPPORTED", "지원하지 않는 API 키 제공자입니다.", status_code=400)
            if response.status_code in {401, 403}:
                raise DomainError("API_KEY_INVALID", "유효하지 않은 API 키입니다.", status_code=422)
            response.raise_for_status()
        except DomainError:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise DomainError(
                "API_KEY_VALIDATION_FAILED",
                "API 키 검증 서비스에 연결할 수 없습니다.",
                status_code=503,
                retryable=True,
            ) from exc
        finally:
            if self.http_client is None:
                client.close()


class UserApiKeyService:
    def __init__(self, session: Session, encryption: KeyEncryptionService, validator: ApiKeyValidator) -> None:
        self.session = session
        self.encryption = encryption
        self.validator = validator

    def list(self, user_id: UUID) -> list[UserApiKey]:
        return list(self.session.scalars(select(UserApiKey).where(UserApiKey.user_id == user_id).order_by(UserApiKey.provider)))

    def put(self, user_id: UUID, provider: str, api_key: str) -> UserApiKey:
        _validate_provider(provider)
        self.validator.validate(provider, api_key)
        row = self.session.scalar(
            select(UserApiKey).where(UserApiKey.user_id == user_id, UserApiKey.provider == provider)
        )
        if row is None:
            row = UserApiKey(user_id=user_id, provider=provider, encrypted_key=b"", key_fingerprint="")
            self.session.add(row)
        row.encrypted_key = self.encryption.encrypt(api_key)
        row.key_fingerprint = _fingerprint(api_key)
        row.is_valid = True
        row.last_validated_at = utcnow()
        row.last_validation_error = None
        self.session.flush()
        return row

    def delete(self, user_id: UUID, provider: str) -> None:
        _validate_provider(provider)
        row = self.session.scalar(
            select(UserApiKey).where(UserApiKey.user_id == user_id, UserApiKey.provider == provider)
        )
        if row is not None:
            self.session.delete(row)
            self.session.flush()


def _validate_provider(provider: str) -> None:
    if provider not in SUPPORTED_KEY_PROVIDERS:
        raise DomainError("API_KEY_PROVIDER_UNSUPPORTED", "지원하지 않는 API 키 제공자입니다.", status_code=400)


def require_valid_api_keys(session: Session, user_id: UUID) -> None:
    rows = {
        row.provider: row
        for row in session.scalars(select(UserApiKey).where(UserApiKey.user_id == user_id))
    }
    missing = [provider for provider in sorted(SUPPORTED_KEY_PROVIDERS) if provider not in rows]
    if missing:
        raise DomainError("API_KEY_NOT_CONFIGURED", "Anthropic과 Upstage API 키를 모두 등록해주세요.", status_code=422)
    if any(not rows[provider].is_valid for provider in SUPPORTED_KEY_PROVIDERS):
        raise DomainError("API_KEY_INVALID", "등록된 API 키를 다시 확인해주세요.", status_code=422)


def decrypt_api_keys_for_job(
    session: Session,
    user_id: UUID,
    encryption: KeyEncryptionService,
) -> dict[str, str]:
    require_valid_api_keys(session, user_id)
    rows = session.scalars(select(UserApiKey).where(UserApiKey.user_id == user_id))
    return {row.provider: encryption.decrypt(row.encrypted_key) for row in rows}


def _fingerprint(api_key: str) -> str:
    return f"••••{api_key[-4:]}"


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    refresh_cookie: bool
