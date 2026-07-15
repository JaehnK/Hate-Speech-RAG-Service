from app.api.jobs import _item_progress
from app.db.base import Base
from app.db.models import JobStep
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory
from app.jobs.progress import DatabaseJobProgressReporter


def test_database_progress_reporter_tracks_item_outcomes(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'progress.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        job_id = job.id

    reporter = DatabaseJobProgressReporter(factory)
    reporter.start(job_id, "analyze_comments", 3)
    reporter.advance(job_id, "analyze_comments", succeeded=True)
    reporter.advance(job_id, "analyze_comments", succeeded=False)

    with factory() as session:
        step = session.query(JobStep).filter_by(job_id=job_id, step_key="analyze_comments").one()
        assert (step.items_total, step.items_completed) == (3, 2)
        assert (step.items_succeeded, step.items_failed) == (1, 1)
        assert step.heartbeat_at is not None
        assert _item_progress(step) == {
            "total": 3,
            "completed": 2,
            "succeeded": 1,
            "failed": 1,
            "percent": 67,
        }
