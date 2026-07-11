import pytest
from sqlalchemy import select

from app.collectors.transcript import TranscriptCollector, TranscriptData, TranscriptItem
from app.core.errors import DomainError
from app.db.base import Base
from app.db.models import TranscriptSegment, TranscriptSnapshot
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory


class FakeProvider:
    def fetch(self, _video_id: str) -> TranscriptData:
        return TranscriptData(
            language_code="ko",
            is_generated=False,
            items=(
                TranscriptItem("첫 문장", 0, 10),
                TranscriptItem("둘째 문장", 10, 10),
                TranscriptItem("셋째 문장", 50, 5),
            ),
        )


class MissingProvider:
    def fetch(self, _video_id: str) -> TranscriptData:
        raise DomainError("CAPTION_NOT_AVAILABLE", "공개 자막이 없습니다.")


def test_transcript_is_normalized_and_segmented(tmp_path) -> None:
    factory = _factory(tmp_path)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        snapshot, segments = TranscriptCollector(FakeProvider(), max_segment_seconds=30).collect(session, job)
        assert snapshot.raw_text == "첫 문장 둘째 문장 셋째 문장"
        assert [segment.text for segment in segments] == ["첫 문장 둘째 문장", "셋째 문장"]


def test_missing_transcript_records_not_available_snapshot(tmp_path) -> None:
    factory = _factory(tmp_path)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        with pytest.raises(DomainError):
            TranscriptCollector(MissingProvider()).collect(session, job)
    with factory() as session:
        snapshot = session.scalar(select(TranscriptSnapshot))
        assert snapshot.status == "not_available"
        assert not list(session.scalars(select(TranscriptSegment)))


def _factory(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'transcript.db'}")
    Base.metadata.create_all(engine)
    return build_session_factory(engine)
