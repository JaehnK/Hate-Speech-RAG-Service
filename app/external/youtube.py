from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Iterator

import httpx

from app.core.errors import DomainError


YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


@dataclass(frozen=True)
class CommentRecord:
    youtube_comment_id: str
    parent_youtube_comment_id: str | None
    author_display_name: str | None
    author_channel_id: str | None
    text_display: str
    text_original: str
    like_count: int
    reply_count: int
    published_at: datetime | None
    updated_at: datetime | None
    raw_payload: dict[str, Any]

    @property
    def is_reply(self) -> bool:
        return self.parent_youtube_comment_id is not None


class YouTubeApiClient:
    def __init__(self, api_key: str | None, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required")
        self.api_key = api_key
        self.client = client or httpx.Client(base_url=YOUTUBE_API_BASE_URL, timeout=30)

    def get_video(self, video_id: str) -> dict[str, Any]:
        payload = self._get("/videos", {"part": "snippet,contentDetails,statistics,status", "id": video_id})
        items = payload.get("items", [])
        if not items:
            raise DomainError("VIDEO_NOT_FOUND", "YouTube 영상을 찾을 수 없습니다.", status_code=404)
        return items[0]

    def iter_comments(self, video_id: str) -> Iterator[CommentRecord]:
        page_token = None
        while True:
            params = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": 100,
                "textFormat": "plainText",
                "order": "time",
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._get("/commentThreads", params)
            for thread in payload.get("items", []):
                top_level = thread["snippet"]["topLevelComment"]
                top_record = _comment_record(top_level, reply_count=int(thread["snippet"].get("totalReplyCount", 0)))
                yield top_record
                embedded = thread.get("replies", {}).get("comments", [])
                seen = set()
                for reply in embedded:
                    seen.add(reply["id"])
                    yield _comment_record(reply)
                if top_record.reply_count > len(embedded):
                    yield from self._iter_replies(top_record.youtube_comment_id, seen)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

    def _iter_replies(self, parent_id: str, seen: set[str]) -> Iterator[CommentRecord]:
        page_token = None
        while True:
            params = {"part": "snippet", "parentId": parent_id, "maxResults": 100, "textFormat": "plainText"}
            if page_token:
                params["pageToken"] = page_token
            payload = self._get("/comments", params)
            for reply in payload.get("items", []):
                if reply["id"] not in seen:
                    yield _comment_record(reply)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.get(path, params={**params, "key": self.api_key})
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise DomainError("YOUTUBE_API_ERROR", "YouTube API 요청 시간이 초과되었습니다.", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            raise _youtube_error(exc.response) from exc
        except httpx.RequestError as exc:
            raise DomainError("YOUTUBE_API_ERROR", "YouTube API에 연결할 수 없습니다.", retryable=True) from exc
        return response.json()


def parse_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _comment_record(item: dict[str, Any], reply_count: int = 0) -> CommentRecord:
    snippet = item["snippet"]
    author_channel = snippet.get("authorChannelId") or {}
    return CommentRecord(
        youtube_comment_id=item["id"],
        parent_youtube_comment_id=snippet.get("parentId"),
        author_display_name=snippet.get("authorDisplayName"),
        author_channel_id=author_channel.get("value"),
        text_display=snippet.get("textDisplay", ""),
        text_original=snippet.get("textOriginal", snippet.get("textDisplay", "")),
        like_count=int(snippet.get("likeCount", 0)),
        reply_count=reply_count,
        published_at=_parse_datetime(snippet.get("publishedAt")),
        updated_at=_parse_datetime(snippet.get("updatedAt")),
        raw_payload=item,
    )


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _youtube_error(response: httpx.Response) -> DomainError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    errors = payload.get("error", {}).get("errors", [])
    reason = errors[0].get("reason") if errors else None
    if reason in {"quotaExceeded", "dailyLimitExceeded"}:
        return DomainError("YOUTUBE_QUOTA_EXCEEDED", "YouTube API quota를 초과했습니다.", retryable=True)
    if reason in {"rateLimitExceeded", "userRateLimitExceeded"}:
        return DomainError("YOUTUBE_RATE_LIMITED", "YouTube API 요청 한도를 초과했습니다.", retryable=True)
    if reason in {"commentsDisabled", "disabledComments"}:
        return DomainError("COMMENTS_DISABLED", "영상의 댓글이 비활성화되어 있습니다.")
    return DomainError("YOUTUBE_API_ERROR", "YouTube API 요청에 실패했습니다.", retryable=response.status_code >= 500)
