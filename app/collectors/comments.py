from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, CommentSnapshot
from app.external.youtube import YouTubeApiClient


class CommentCollector:
    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def collect_all(self, session: Session, job: AnalysisJob) -> list[CommentSnapshot]:
        snapshots: list[CommentSnapshot] = []
        parent_ids = {}
        for record in self.client.iter_comments(job.youtube_video_id):
            snapshot = CommentSnapshot(
                job_id=job.id,
                youtube_video_id=job.youtube_video_id,
                youtube_comment_id=record.youtube_comment_id,
                parent_youtube_comment_id=record.parent_youtube_comment_id,
                parent_comment_snapshot_id=parent_ids.get(record.parent_youtube_comment_id),
                is_reply=record.is_reply,
                reply_depth=1 if record.is_reply else 0,
                author_display_name=record.author_display_name,
                author_channel_id=record.author_channel_id,
                text_display=record.text_display,
                text_original=record.text_original,
                like_count=record.like_count,
                reply_count=record.reply_count,
                published_at=record.published_at,
                updated_at=record.updated_at,
                raw_payload=record.raw_payload,
            )
            session.add(snapshot)
            session.flush()
            parent_ids[record.youtube_comment_id] = snapshot.id
            snapshots.append(snapshot)
        return snapshots
