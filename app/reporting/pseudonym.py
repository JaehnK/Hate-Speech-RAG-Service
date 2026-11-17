"""Stable pseudonyms for YouTube authors and comments in public sample reports.

A pseudonym is a keyed HMAC-SHA256 of the YouTube ID, cut to 80 bits and written in base32
(16 characters). The same channel gets the same pseudonym in every report and every video, so
networks from several videos can later be joined on it, while nobody without the key can map a
pseudonym back to a channel: channel IDs are public and enumerable, so a plain hash would not do.
80 bits keeps the chance of any collision below one in a million up to about a billion channels.

The key must never change once public samples are out, or the same author gets a new pseudonym.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from app.core.config import Settings

_DERIVE_LABEL = b"hsr-author-pseudonym-v1"
_LOCAL_DEV_SECRET = "local-dev-only"


class Pseudonymizer:
    def __init__(self, secret: str) -> None:
        self._key = hmac.new(secret.encode("utf-8"), _DERIVE_LABEL, hashlib.sha256).digest()

    @classmethod
    def from_settings(cls, settings: Settings) -> Pseudonymizer:
        # A dedicated key wins; otherwise derive one from the BYOK encryption key, which already
        # has to stay fixed for stored API keys to keep decrypting.
        return cls(settings.author_pseudonym_key or settings.api_key_encryption_key or _LOCAL_DEV_SECRET)

    def _digest(self, kind: str, value: str) -> str:
        mac = hmac.new(self._key, f"{kind}:{value}".encode("utf-8"), hashlib.sha256).digest()
        return base64.b32encode(mac[:10]).decode("ascii").lower()

    def author(self, channel_id: str | None, snapshot_id: object) -> str:
        """Same value as the author's network node key, so the comment filter takes either."""
        return self.node_key(channel_id or f"anonymous:{snapshot_id}")

    def comment(self, comment_id: str | None) -> str | None:
        return "c" + self._digest("yt-comment", comment_id) if comment_id else None

    def node_key(self, node_key: str) -> str:
        """Network node keys are a channel ID or `anonymous:<snapshot uuid>` (app/reporting/network.py).

        An author without a channel ID gets a pseudonym that only holds within that one comment."""
        if node_key.startswith("anonymous:"):
            return "n" + self._digest("snapshot", node_key)
        return "a" + self._digest("yt-channel", node_key)

    @staticmethod
    def label(pseudonym: str) -> str:
        return f"익명-{pseudonym[1:7].upper()}"

    def report_payload(self, payload: dict) -> dict:
        """Report payload with the representative comments' YouTube IDs replaced."""
        comments = payload.get("representative_comments")
        if not comments:
            return payload
        return {
            **payload,
            "representative_comments": [{**row, "youtube_comment_id": self.comment(row.get("youtube_comment_id"))} for row in comments],
        }
