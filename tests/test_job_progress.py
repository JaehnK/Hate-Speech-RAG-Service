import pytest

from app.api.jobs import _item_progress
from app.analysis.models import AnalysisOutcome, StepAttemptContext
from app.analysis.result_store import AnalysisResultStore
from app.db.base import Base
from app.db.models import AnalysisRun, CommentAnalysisResult, CommentSnapshot, JobStep
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory
from app.jobs.exceptions import StaleStepExecution


def test_result_store_tracks_each_item_once(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'progress.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        session.add(CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c1", text_original="x"))
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
        step = session.query(JobStep).filter_by(job_id=job.id, step_key="analyze_comments").one()
        step.status = "running"
        step.attempt_count = 1
        session.flush()
        context = StepAttemptContext(job.id, step.id, step.step_key, run.id, 1)

    store = AnalysisResultStore(factory)
    outcome = AnalysisOutcome(source_id=_comment_id(factory), status="succeeded", result_values={"categories": []})
    store.reconcile(context, "comment", 1)
    assert store.persist(context, "comment", outcome)
    assert not store.persist(context, "comment", outcome)

    with factory() as session:
        step = session.get(JobStep, context.step_id)
        assert step is not None
        assert (step.items_total, step.items_completed) == (1, 1)
        assert (step.items_succeeded, step.items_failed) == (1, 0)
        assert step.heartbeat_at is not None
        assert session.query(CommentAnalysisResult).count() == 1
        assert _item_progress(step) == {
            "total": 1,
            "completed": 1,
            "succeeded": 1,
            "failed": 0,
            "percent": 100,
        }


def _comment_id(factory):
    with factory() as session:
        return session.query(CommentSnapshot.id).scalar()


def test_result_store_rejects_an_old_step_attempt(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'stale-progress.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        comment = CommentSnapshot(
            job_id=job.id,
            youtube_video_id="abcdefghijk",
            youtube_comment_id="c1",
            text_original="x",
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
        session.add_all([comment, run])
        step = session.query(JobStep).filter_by(job_id=job.id, step_key="analyze_comments").one()
        step.status = "running"
        step.attempt_count = 2
        session.flush()
        old_context = StepAttemptContext(job.id, step.id, step.step_key, run.id, 1)
        source_id = comment.id

    outcome = AnalysisOutcome(source_id=source_id, status="succeeded", result_values={"categories": []})
    with pytest.raises(StaleStepExecution):
        AnalysisResultStore(factory).persist(old_context, "comment", outcome)

    with factory() as session:
        assert session.query(CommentAnalysisResult).count() == 0
        step = session.get(JobStep, old_context.step_id)
        assert step is not None
        assert step.items_completed == 0
