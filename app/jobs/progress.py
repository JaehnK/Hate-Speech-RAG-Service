from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import case, func, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import JobStep


class JobProgressReporter(Protocol):
    def start(self, job_id: UUID, step_key: str, total: int) -> None: ...

    def advance(self, job_id: UUID, step_key: str, succeeded: bool) -> None: ...


class DatabaseJobProgressReporter:
    """Persist atomic counters independently from the long-running analysis transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def start(self, job_id: UUID, step_key: str, total: int) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                update(JobStep)
                .where(JobStep.job_id == job_id, JobStep.step_key == step_key)
                .values(items_total=total, items_completed=0, items_succeeded=0, items_failed=0)
            )

    def advance(self, job_id: UUID, step_key: str, succeeded: bool) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                update(JobStep)
                .where(JobStep.job_id == job_id, JobStep.step_key == step_key)
                .values(
                    items_completed=func.coalesce(JobStep.items_completed, 0) + 1,
                    items_succeeded=func.coalesce(JobStep.items_succeeded, 0) + case((succeeded, 1), else_=0),
                    items_failed=func.coalesce(JobStep.items_failed, 0) + case((succeeded, 0), else_=1),
                )
            )
