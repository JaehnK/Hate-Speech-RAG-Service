from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.errors import DomainError


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    display_name: str | None
    avatar_url: str | None


class GoogleOAuthProvider(Protocol):
    def authorization_url(self, state: str, code_challenge: str) -> str: ...

    def exchange(self, code: str, code_verifier: str) -> GoogleIdentity: ...


class GoogleOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http_client: httpx.Client | None = None,
        token_verifier: Callable[[str, str], dict] | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.http_client = http_client
        self.token_verifier = token_verifier or _verify_token

    def authorization_url(self, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZATION_URL}?{query}"

    def exchange(self, code: str, code_verifier: str) -> GoogleIdentity:
        client = self.http_client or httpx.Client(timeout=15)
        try:
            response = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "code_verifier": code_verifier,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            claims = self.token_verifier(response.json()["id_token"], self.client_id)
            if not claims.get("sub") or not claims.get("email") or not claims.get("email_verified"):
                raise ValueError("required Google identity claim missing")
            return GoogleIdentity(
                sub=str(claims["sub"]),
                email=str(claims["email"]),
                email_verified=True,
                display_name=claims.get("name"),
                avatar_url=claims.get("picture"),
            )
        except Exception as exc:
            raise DomainError("OAUTH_CALLBACK_FAILED", "Google 로그인을 완료할 수 없습니다.") from exc
        finally:
            if self.http_client is None:
                client.close()


def _verify_token(token: str, client_id: str) -> dict:
    return id_token.verify_oauth2_token(token, GoogleRequest(), client_id)
