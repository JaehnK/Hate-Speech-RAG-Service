import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import delete, select

from app.analysis.models import AnalysisOutcome, StepAttemptContext
from app.analysis.result_store import AnalysisResultStore
from app.db.models import AnalysisJob, AnalysisRun, CommentAnalysisResult, CommentSnapshot, JobStep
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory


POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")


@pytest.mark.skipif(not POSTGRES_TEST_DATABASE_URL, reason="PostgreSQL integration database is not configured")
def test_postgres_result_insert_is_idempotent() -> None:
    factory = build_session_factory(build_engine(POSTGRES_TEST_DATABASE_URL or ""))
    job_id = None
    try:
        with factory.begin() as session:
            job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
            comment = CommentSnapshot(
                job_id=job.id,
                youtube_video_id="abcdefghijk",
                youtube_comment_id="result-store-postgres",
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
            step = session.scalar(
                select(JobStep).where(JobStep.job_id == job.id, JobStep.step_key == "analyze_comments")
            )
            assert step is not None
            step.status = "running"
            step.attempt_count = 1
            session.flush()
            context = StepAttemptContext(job.id, step.id, step.step_key, run.id, 1)
            source_id = comment.id
            job_id = job.id

        store = AnalysisResultStore(factory)
        store.reconcile(context, "comment", 1)
        outcome = AnalysisOutcome(source_id=source_id, status="succeeded", result_values={"categories": []})
        barrier = Barrier(2)

        def persist_once() -> bool:
            barrier.wait()
            return store.persist(context, "comment", outcome)

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(lambda _index: persist_once(), range(2))) == [False, True]

        with factory() as session:
            assert session.scalar(
                select(JobStep.items_completed).where(JobStep.id == context.step_id)
            ) == 1
            assert session.scalar(
                select(CommentAnalysisResult).where(CommentAnalysisResult.analysis_run_id == context.run_id)
            ) is not None
    finally:
        if job_id is not None:
            with factory.begin() as session:
                session.execute(delete(AnalysisJob).where(AnalysisJob.id == job_id))
