import secrets
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.crypto import KeyEncryptionService
from app.auth.google_oauth import GoogleOAuthClient, GoogleOAuthProvider
from app.auth.http import OAUTH_STATE_COOKIE, AuthResolver, delete_session_cookie, require_csrf, set_session_cookie
from app.auth.services import (
    ApiKeyValidator,
    OAuthStateCodec,
    ProviderApiKeyValidator,
    SessionService,
    UserApiKeyService,
    UserService,
    pkce_challenge,
)
from app.core.config import Settings
from app.core.errors import DomainError


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)


def build_auth_router(
    get_session: Callable[[], Iterator[Session]],
    settings: Settings,
    oauth_provider: GoogleOAuthProvider | None = None,
    api_key_validator: ApiKeyValidator | None = None,
) -> APIRouter:
    router = APIRouter(tags=["auth"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    resolver = AuthResolver(settings)

    def oauth() -> GoogleOAuthProvider:
        if oauth_provider is not None:
            return oauth_provider
        if not settings.google_client_id or not settings.google_client_secret:
            raise DomainError("OAUTH_NOT_CONFIGURED", "Google 로그인이 아직 설정되지 않았습니다.", status_code=503)
        return GoogleOAuthClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_oauth_redirect_uri,
        )

    def key_service(session: Session) -> UserApiKeyService:
        if not settings.api_key_encryption_key:
            raise DomainError("API_KEY_ENCRYPTION_NOT_CONFIGURED", "API 키 암호화가 설정되지 않았습니다.", status_code=503)
        validator = api_key_validator or ProviderApiKeyValidator(settings.upstage_embedding_base_url)
        return UserApiKeyService(session, KeyEncryptionService(settings.api_key_encryption_key), validator)

    @router.get("/api/auth/google/login")
    def google_login(
        request: Request,
        session: SessionDependency,
        return_to: str = Query("/analyze"),
    ) -> Response:
        return_to = _safe_return_to(return_to)
        probe = Response()
        if settings.auth_configured and resolver.optional(request, probe, session) is not None:
            return RedirectResponse(return_to, status_code=status.HTTP_302_FOUND)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        secret = settings.google_client_secret or "test-oauth-state-secret"
        encoded = OAuthStateCodec(secret).encode(state, verifier, return_to)
        response = RedirectResponse(oauth().authorization_url(state, pkce_challenge(verifier)), status_code=302)
        response.set_cookie(
            OAUTH_STATE_COOKIE,
            encoded,
            max_age=600,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @router.get("/api/auth/google/callback")
    def google_callback(
        request: Request,
        session: SessionDependency,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Response:
        if error or not code or not state:
            raise DomainError("OAUTH_CALLBACK_FAILED", "Google 로그인이 취소되었거나 완료되지 않았습니다.")
        cookie = request.cookies.get(OAUTH_STATE_COOKIE)
        if not cookie:
            raise DomainError("OAUTH_STATE_MISMATCH", "로그인 요청 상태가 일치하지 않습니다.")
        secret = settings.google_client_secret or "test-oauth-state-secret"
        saved = OAuthStateCodec(secret).decode(cookie)
        if not secrets.compare_digest(saved["state"], state):
            raise DomainError("OAUTH_STATE_MISMATCH", "로그인 요청 상태가 일치하지 않습니다.")
        identity = oauth().exchange(code, saved["verifier"])
        user = UserService(session).upsert_google_user(identity)
        token = SessionService(session, settings.session_ttl_seconds).issue(
            user.id,
            request.headers.get("User-Agent"),
            request.client.host if request.client else None,
        )
        response = RedirectResponse(saved["return_to"], status_code=302)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        set_session_cookie(response, settings, token)
        return response

    @router.get("/api/auth/session")
    def auth_session(request: Request, response: Response, session: SessionDependency) -> dict:
        user = resolver.required(request, response, session)
        keys = {row.provider: row.is_valid for row in key_service(session).list(user.id)} if settings.api_key_encryption_key else {}
        return {
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "api_keys_registered": {provider: bool(keys.get(provider)) for provider in ("anthropic", "upstage")},
        }

    @router.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response, session: SessionDependency) -> None:
        require_csrf(request, settings)
        SessionService(session, settings.session_ttl_seconds).revoke(request.cookies.get(settings.session_cookie_name))
        delete_session_cookie(response, settings)

    @router.get("/api/me/api-keys")
    def list_api_keys(request: Request, response: Response, session: SessionDependency) -> dict:
        user = resolver.required(request, response, session)
        return {"items": [_key_payload(row) for row in key_service(session).list(user.id)]}

    @router.put("/api/me/api-keys/{provider}")
    def put_api_key(
        provider: str,
        body: ApiKeyRequest,
        request: Request,
        response: Response,
        session: SessionDependency,
    ) -> dict:
        require_csrf(request, settings)
        user = resolver.required(request, response, session)
        return _key_payload(key_service(session).put(user.id, provider, body.api_key))

    @router.delete("/api/me/api-keys/{provider}", status_code=204)
    def delete_api_key(
        provider: str,
        request: Request,
        response: Response,
        session: SessionDependency,
    ) -> None:
        require_csrf(request, settings)
        user = resolver.required(request, response, session)
        key_service(session).delete(user.id, provider)

    return router


def _key_payload(row) -> dict:
    return {
        "provider": row.provider,
        "key_fingerprint": row.key_fingerprint,
        "is_valid": row.is_valid,
        "last_validated_at": row.last_validated_at,
    }


def _safe_return_to(value: str) -> str:
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/analyze"
    return value
