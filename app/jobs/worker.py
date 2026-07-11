import time
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.db.repositories import AnalysisJobRepository
from app.db.models import utcnow
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.orchestrator import JobOrchestrator, StepHandler


class JobWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handlers: dict[str, StepHandler] | None = None,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.session_factory = session_factory
        self.handlers = handlers or build_fake_handlers()
        self.poll_interval_seconds = poll_interval_seconds

    def run_once(self) -> bool:
        with self.session_factory.begin() as session:
            job = AnalysisJobRepository(session).claim_pending()
            if job is None:
                return False
            job.status = "running"
            job.started_at = job.started_at or utcnow()
            job_id = job.id

        with self.session_factory() as session:
            JobOrchestrator(session, self.handlers).run_job(job_id)
        return True

    def run_forever(self, should_stop: Callable[[], bool] | None = None) -> None:
        should_stop = should_stop or (lambda: False)
        while not should_stop():
            if not self.run_once():
                time.sleep(self.poll_interval_seconds)
