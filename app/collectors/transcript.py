from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, YouTubeTranscriptApi

from app.core.errors import DomainError
from app.db.models import AnalysisJob, TranscriptSegment, TranscriptSnapshot


SENTENCE_END_PATTERN = re.compile(r"[.!?…。！？](?:[\"'”’」』)]*)$")


@dataclass(frozen=True)
class TranscriptItem:
    text: str
    start: float
    duration: float


@dataclass(frozen=True)
class TranscriptData:
    language_code: str
    is_generated: bool
    items: tuple[TranscriptItem, ...]


class TranscriptProvider(Protocol):
    def fetch(self, video_id: str) -> TranscriptData: ...


class PublicTranscriptProvider:
    def __init__(self, api: YouTubeTranscriptApi | None = None, languages: tuple[str, ...] = ("ko", "en")) -> None:
        self.api = api or YouTubeTranscriptApi()
        self.languages = languages

    def fetch(self, video_id: str) -> TranscriptData:
        try:
            transcript = self.api.list(video_id).find_transcript(list(self.languages))
            fetched = transcript.fetch()
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
            raise DomainError("CAPTION_NOT_AVAILABLE", "사용 가능한 공개 자막이 없습니다.") from exc
        except Exception as exc:
            raise DomainError("CAPTION_COLLECTION_ERROR", "공개 자막 수집에 실패했습니다.", retryable=True) from exc
        return TranscriptData(
            language_code=transcript.language_code,
            is_generated=transcript.is_generated,
            items=tuple(TranscriptItem(item.text, item.start, item.duration) for item in fetched),
        )


class TranscriptCollector:
    def __init__(self, provider: TranscriptProvider, max_segment_chars: int = 800, max_segment_seconds: float = 45) -> None:
        self.provider = provider
        self.max_segment_chars = max_segment_chars
        self.max_segment_seconds = max_segment_seconds

    def collect(self, session: Session, job: AnalysisJob) -> tuple[TranscriptSnapshot, list[TranscriptSegment]]:
        try:
            data = self.provider.fetch(job.youtube_video_id)
        except DomainError as exc:
            snapshot = TranscriptSnapshot(
                job_id=job.id,
                youtube_video_id=job.youtube_video_id,
                source_type="public_caption",
                status="not_available" if exc.code == "CAPTION_NOT_AVAILABLE" else "failed",
                error_code=exc.code,
            )
            session.add(snapshot)
            session.flush()
            raise

        raw_text = " ".join(item.text.strip() for item in data.items if item.text.strip())
        snapshot = TranscriptSnapshot(
            job_id=job.id,
            youtube_video_id=job.youtube_video_id,
            language_code=data.language_code,
            is_auto_generated=data.is_generated,
            source_type="public_caption",
            raw_text=raw_text,
            raw_payload={
                "item_count": len(data.items),
                "segmentation": "sentence_boundary_with_duration_char_fallback_v1",
            },
            status="succeeded",
        )
        session.add(snapshot)
        session.flush()
        segments = [
            TranscriptSegment(
                transcript_snapshot_id=snapshot.id,
                segment_index=index,
                start_seconds=Decimal(str(start)),
                end_seconds=Decimal(str(end)),
                text=text,
                token_count=len(text.split()),
            )
            for index, (start, end, text) in enumerate(self._segments(data.items))
        ]
        session.add_all(segments)
        session.flush()
        return snapshot, segments

    def _segments(self, items: tuple[TranscriptItem, ...]):
        current: list[TranscriptItem] = []
        for item in items:
            candidate_text = " ".join(entry.text.strip() for entry in [*current, item])
            duration = item.start + item.duration - (current[0].start if current else item.start)
            if current and (len(candidate_text) > self.max_segment_chars or duration > self.max_segment_seconds):
                yield _segment(current)
                current = []
            current.append(item)
            if SENTENCE_END_PATTERN.search(item.text.strip()):
                yield _segment(current)
                current = []
        if current:
            yield _segment(current)


def _segment(items: list[TranscriptItem]) -> tuple[float, float, str]:
    return items[0].start, items[-1].start + items[-1].duration, " ".join(item.text.strip() for item in items)
