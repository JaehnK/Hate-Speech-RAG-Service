from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, VideoMetadataSnapshot
from app.external.youtube import YouTubeApiClient, parse_duration_seconds


class VideoMetadataCollector:
    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def collect(self, session: Session, job: AnalysisJob) -> VideoMetadataSnapshot:
        item = self.client.get_video(job.youtube_video_id)
        snippet = item.get("snippet", {})
        details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        status = item.get("status", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("default") or {}
        snapshot = VideoMetadataSnapshot(
            job_id=job.id,
            youtube_video_id=job.youtube_video_id,
            youtube_channel_id=snippet.get("channelId"),
            title=snippet.get("title"),
            channel_title=snippet.get("channelTitle"),
            published_at=_datetime(snippet.get("publishedAt")),
            category_id=snippet.get("categoryId"),
            duration_seconds=parse_duration_seconds(details.get("duration")),
            view_count=_int(statistics.get("viewCount")),
            like_count=_int(statistics.get("likeCount")),
            comment_count=_int(statistics.get("commentCount")),
            made_for_kids=status.get("madeForKids"),
            tags=snippet.get("tags"),
            description=snippet.get("description"),
            thumbnail_url=thumbnail.get("url"),
            raw_payload=item,
        )
        session.add(snapshot)
        session.flush()
        return snapshot


def _int(value) -> int | None:
    return int(value) if value is not None else None


def _datetime(value):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
