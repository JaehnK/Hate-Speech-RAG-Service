from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.auth.services import SessionService
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import User


OAUTH_STATE_COOKIE = "hsr_oauth_state"


class AuthResolver:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def required(self, request: Request, response: Response, session: Session) -> User:
        user, refresh = SessionService(session, self.settings.session_ttl_seconds).resolve(
            request.cookies.get(self.settings.session_cookie_name)
        )
        if refresh:
            set_session_cookie(response, self.settings, request.cookies[self.settings.session_cookie_name])
        return user

    def optional(self, request: Request, response: Response, session: Session) -> User | None:
        try:
            return self.required(request, response, session)
        except DomainError as exc:
            if exc.status_code == 401:
                return None
            raise


def require_csrf(request: Request, settings: Settings) -> None:
    if request.headers.get("X-Requested-With") != "hatespeechraw":
        raise DomainError("CSRF_REJECTED", "요청 출처를 확인할 수 없습니다.", status_code=403)
    if request.headers.get("Origin") != settings.frontend_origin:
        raise DomainError("CSRF_REJECTED", "허용되지 않은 요청 출처입니다.", status_code=403)


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.session_cookie_domain,
    )


def delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.session_cookie_domain,
    )
