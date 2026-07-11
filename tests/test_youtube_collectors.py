import httpx
import pytest
from sqlalchemy import select

from app.collectors.comments import CommentCollector
from app.collectors.metadata import VideoMetadataCollector
from app.core.errors import DomainError
from app.db.base import Base
from app.db.models import CommentSnapshot, VideoMetadataSnapshot
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory
from app.external.youtube import YouTubeApiClient, parse_duration_seconds


def test_metadata_and_all_comment_pages_are_persisted(tmp_path) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/videos"):
            return httpx.Response(200, json={"items": [_video_item()]})
        if request.url.path.endswith("/commentThreads"):
            return httpx.Response(200, json={"items": [_thread_item()]})
        if request.url.path.endswith("/comments"):
            return httpx.Response(200, json={"items": [_comment_item("r2", parent_id="top1")]})
        raise AssertionError(request.url)

    http_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://www.googleapis.com/youtube/v3")
    client = YouTubeApiClient("secret-key", client=http_client)
    engine = build_engine(f"sqlite:///{tmp_path / 'collect.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)

    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        metadata = VideoMetadataCollector(client).collect(session, job)
        comments = CommentCollector(client).collect_all(session, job)
        repeated = CommentCollector(client).collect_all(session, job)
        assert metadata.duration_seconds == 3723
        assert len(comments) == 3
        assert len(repeated) == 3
        assert comments[1].parent_comment_snapshot_id == comments[0].id
        assert comments[2].parent_comment_snapshot_id == comments[0].id

    with factory() as session:
        assert session.scalar(select(VideoMetadataSnapshot)).title == "Video"
        assert len(list(session.scalars(select(CommentSnapshot)))) == 3
    assert all("secret-key" not in str(request.headers) for request in requests)


def test_quota_error_is_mapped_without_secret() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})

    client = YouTubeApiClient(
        "do-not-leak",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://www.googleapis.com/youtube/v3"),
    )
    with pytest.raises(DomainError) as exc_info:
        client.get_video("abcdefghijk")
    assert exc_info.value.code == "YOUTUBE_QUOTA_EXCEEDED"
    assert exc_info.value.retryable
    assert "do-not-leak" not in str(exc_info.value)


def test_parse_duration_seconds() -> None:
    assert parse_duration_seconds("PT1H2M3S") == 3723
    assert parse_duration_seconds("PT45S") == 45
    assert parse_duration_seconds(None) is None


def _video_item() -> dict:
    return {
        "id": "abcdefghijk",
        "snippet": {
            "title": "Video",
            "channelId": "channel1",
            "channelTitle": "Channel",
            "publishedAt": "2026-01-01T00:00:00Z",
            "categoryId": "22",
            "description": "Description",
            "tags": ["tag"],
            "thumbnails": {"high": {"url": "https://example.com/image.jpg"}},
        },
        "contentDetails": {"duration": "PT1H2M3S"},
        "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "3"},
        "status": {"madeForKids": False},
    }


def _thread_item() -> dict:
    return {
        "id": "thread1",
        "snippet": {"topLevelComment": _comment_item("top1"), "totalReplyCount": 2},
        "replies": {"comments": [_comment_item("r1", parent_id="top1")]},
    }


def _comment_item(comment_id: str, parent_id: str | None = None) -> dict:
    snippet = {
        "authorDisplayName": "Author",
        "authorChannelId": {"value": f"author-{comment_id}"},
        "textDisplay": f"comment {comment_id}",
        "textOriginal": f"comment {comment_id}",
        "likeCount": 1,
        "publishedAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    if parent_id:
        snippet["parentId"] = parent_id
    return {"id": comment_id, "snippet": snippet}
