from types import SimpleNamespace

from sqlalchemy import select

from app.analysis.rag_classifier import ClassificationError
from app.analysis.executor import RagRuntime
from app.analysis.models import StepAttemptContext
from app.analysis.result_store import AnalysisResultStore
from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.db.base import Base
from app.db.models import AnalysisRun, CommentAnalysisResult, CommentSnapshot, JobStep, ScriptAnalysisResult, TranscriptSegment, TranscriptSnapshot
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory


class FakeClassifier:
    def __init__(self) -> None:
        self.calls = []

    def classify_text(self, text, _source_type):
        self.calls.append(text)
        if text == "fail":
            raise ClassificationError("fake failure")
        return SimpleNamespace(
            payload={
                "input_text": text,
                "is_hate_speech": False,
                "categories": ["unclassified"],
                "target_group": None,
                "hate_type": "장문 유형 설명 " * 10 if text == "long" else None,
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
        comment_context = _context(session, job.id, run.id, "analyze_comments")
        script_context = _context(session, job.id, run.id, "analyze_script")

    store = AnalysisResultStore(factory)
    runtime = RagRuntime([FakeClassifier()])
    assert CommentAnalyzer(runtime, store).analyze(comment_context) == {
        "comments_analyzed": 2,
        "succeeded": 1,
        "failed": 1,
    }
    assert ScriptAnalyzer(runtime, store).analyze(script_context) == {
        "script_segments_analyzed": 2,
        "succeeded": 1,
        "failed": 1,
    }

    with factory() as session:
        assert [row.status for row in session.scalars(select(CommentAnalysisResult).order_by(CommentAnalysisResult.created_at))] == ["succeeded", "failed"]
        assert [row.status for row in session.scalars(select(ScriptAnalysisResult).order_by(ScriptAnalysisResult.created_at))] == ["succeeded", "failed"]


def test_comment_analyzer_persists_long_hate_type(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'long-hate-type.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        session.add(
            CommentSnapshot(
                job_id=job.id,
                youtube_video_id="abcdefghijk",
                youtube_comment_id="c-long",
                text_original="long",
            )
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
        context = _context(session, job.id, run.id, "analyze_comments")

    CommentAnalyzer(RagRuntime([FakeClassifier()]), AnalysisResultStore(factory)).analyze(context)

    with factory() as session:
        result = session.scalar(select(CommentAnalysisResult))
        assert result is not None
        assert result.hate_type is not None
        assert len(result.hate_type) > 64


def test_comment_analyzer_resumes_only_missing_items(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'resume.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        session.add_all(
            [
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c1", text_original="one"),
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c2", text_original="two"),
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
        context = _context(session, job.id, run.id, "analyze_comments")

    classifier = FakeClassifier()
    analyzer = CommentAnalyzer(RagRuntime([classifier]), AnalysisResultStore(factory))
    assert analyzer.analyze(context)["succeeded"] == 2
    assert analyzer.analyze(context)["succeeded"] == 2
    assert classifier.calls == ["one", "two"]


def _context(session, job_id, run_id, step_key) -> StepAttemptContext:
    step = session.scalar(select(JobStep).where(JobStep.job_id == job_id, JobStep.step_key == step_key))
    assert step is not None
    step.status = "running"
    step.attempt_count = 1
    session.flush()
    return StepAttemptContext(
        job_id=job_id,
        step_id=step.id,
        step_key=step_key,
        run_id=run_id,
        expected_attempt=1,
    )
