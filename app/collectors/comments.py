from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, CommentSnapshot
from app.external.youtube import YouTubeApiClient


class CommentCollector:
    def __init__(self, client: YouTubeApiClient) -> None:
        self.client = client

    def collect_all(self, session: Session, job: AnalysisJob) -> list[CommentSnapshot]:
        snapshots: list[CommentSnapshot] = []
        existing = {
            snapshot.youtube_comment_id: snapshot
            for snapshot in session.scalars(select(CommentSnapshot).where(CommentSnapshot.job_id == job.id))
        }
        parent_ids = {youtube_id: snapshot.id for youtube_id, snapshot in existing.items()}
        for record in self.client.iter_comments(job.youtube_video_id):
            snapshot = existing.get(record.youtube_comment_id)
            if snapshot is None:
                snapshot = CommentSnapshot(
                    job_id=job.id,
                    youtube_video_id=job.youtube_video_id,
                    youtube_comment_id=record.youtube_comment_id,
                )
                session.add(snapshot)
                existing[record.youtube_comment_id] = snapshot
            snapshot.parent_youtube_comment_id = record.parent_youtube_comment_id
            snapshot.parent_comment_snapshot_id = parent_ids.get(record.parent_youtube_comment_id)
            snapshot.is_reply = record.is_reply
            snapshot.reply_depth = 1 if record.is_reply else 0
            snapshot.author_display_name = record.author_display_name
            snapshot.author_channel_id = record.author_channel_id
            snapshot.text_display = record.text_display
            snapshot.text_original = record.text_original
            snapshot.like_count = record.like_count
            snapshot.reply_count = record.reply_count
            snapshot.published_at = record.published_at
            snapshot.updated_at = record.updated_at
            snapshot.raw_payload = record.raw_payload
            session.flush()
            parent_ids[record.youtube_comment_id] = snapshot.id
            snapshots.append(snapshot)
        return snapshots
