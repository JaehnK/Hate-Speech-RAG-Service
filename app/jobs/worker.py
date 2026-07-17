import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from uuid import UUID

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
        handler_factory: Callable[[UUID], AbstractContextManager[dict[str, StepHandler]]] | None = None,
        poll_interval_seconds: float = 2.0,
        stale_after_seconds: int = 900,
    ) -> None:
        self.session_factory = session_factory
        self.handlers = handlers or build_fake_handlers()
        self.handler_factory = handler_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.stale_after_seconds = stale_after_seconds

    def run_once(self) -> bool:
        with self.session_factory.begin() as session:
            repository = AnalysisJobRepository(session)
            repository.recover_stale_running(utcnow() - timedelta(seconds=self.stale_after_seconds))
            job = repository.claim_pending()
            if job is None:
                return False
            job.status = "running"
            job.started_at = job.started_at or utcnow()
            job_id = job.id

        with self.session_factory() as session:
            with self._handlers_for(job_id) as handlers:
                JobOrchestrator(session, handlers).run_job(job_id)
        return True

    @contextmanager
    def _handlers_for(self, job_id: UUID) -> Iterator[dict[str, StepHandler]]:
        if self.handler_factory is None:
            yield self.handlers
            return
        with self.handler_factory(job_id) as handlers:
            yield handlers

    def run_forever(self, should_stop: Callable[[], bool] | None = None) -> None:
        should_stop = should_stop or (lambda: False)
        while not should_stop():
            if not self.run_once():
                time.sleep(self.poll_interval_seconds)
