from types import SimpleNamespace

from sqlalchemy import select

from app.analysis.rag_classifier import ClassificationError
from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.db.base import Base
from app.db.models import AnalysisRun, CommentAnalysisResult, CommentSnapshot, ScriptAnalysisResult, TranscriptSegment, TranscriptSnapshot
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory


class FakeClassifier:
    def classify_text(self, text, _source_type):
        if text == "fail":
            raise ClassificationError("fake failure")
        return SimpleNamespace(
            payload={
                "input_text": text,
                "is_hate_speech": False,
                "categories": ["unclassified"],
                "target_group": None,
                "hate_type": None,
                "reasoning": "clean",
                "similar_cases_used": [],
                "definition_docs_used": [],
            },
            rag_context_status="complete",
            prompt_version="test-v1",
            model="fake",
        )


def test_comment_and_script_analyzers_record_every_item(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'analysis.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        session.add_all(
            [
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c1", text_original="ok"),
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c2", text_original="fail"),
            ]
        )
        transcript = TranscriptSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", source_type="public_caption", status="succeeded")
        session.add(transcript)
        session.flush()
        session.add_all(
            [
                TranscriptSegment(transcript_snapshot_id=transcript.id, segment_index=0, text="ok"),
                TranscriptSegment(transcript_snapshot_id=transcript.id, segment_index=1, text="fail"),
            ]
        )
        run = AnalysisRun(
            job_id=job.id,
            youtube_video_id="abcdefghijk",
            status="running",
            llm_provider="fake",
            llm_model="fake",
            embedding_provider="hash",
            embedding_model="hash",
            example_vector_collection="examples",
            definition_vector_collection="definitions",
        )
        session.add(run)
        session.flush()
        assert CommentAnalyzer(FakeClassifier()).analyze(session, run) == {"comments_analyzed": 2, "succeeded": 1, "failed": 1}
        assert ScriptAnalyzer(FakeClassifier()).analyze(session, run) == {"script_segments_analyzed": 2, "succeeded": 1, "failed": 1}

    with factory() as session:
        assert [row.status for row in session.scalars(select(CommentAnalysisResult).order_by(CommentAnalysisResult.created_at))] == ["succeeded", "failed"]
        assert [row.status for row in session.scalars(select(ScriptAnalysisResult).order_by(ScriptAnalysisResult.created_at))] == ["succeeded", "failed"]
