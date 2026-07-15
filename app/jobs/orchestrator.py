from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import AnalysisJob, JobStep, OperationLog, utcnow
from app.db.repositories import AnalysisJobRepository
from app.jobs.exceptions import StaleStepExecution, WorkerShutdownRequested


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StepResult:
    status: str = "succeeded"
    metrics: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


StepHandler = Callable[[Session, AnalysisJob], StepResult]


class JobOrchestrator:
    def __init__(self, session: Session, handlers: dict[str, StepHandler]) -> None:
        self.session = session
        self.repository = AnalysisJobRepository(session)
        self.handlers = handlers

    def run_job(self, job_id: UUID) -> None:
        job = self.repository.get(job_id)
        if job is None:
            raise ValueError(f"unknown job: {job_id}")
        job.status = "running"
        job.started_at = job.started_at or utcnow()
        self.session.commit()

        for step in self.repository.list_steps(job.id):
            if step.status != "pending" or step.step_key == "finalize_job":
                continue
            handler = self.handlers.get(step.step_key)
            if handler is None:
                self._finish_step(step, StepResult(status="skipped", error_code="STEP_NOT_CONFIGURED"))
                continue
            succeeded = self._run_step(job, step, handler)
            if succeeded is None:
                return
            if not succeeded and step.is_required:
                break

        self._finalize(job)
        self.session.commit()

    def _run_step(self, job: AnalysisJob, step: JobStep, handler: StepHandler) -> bool | None:
        step.status = "running"
        step.attempt_count += 1
        step.started_at = utcnow()
        step.heartbeat_at = step.started_at
        self._log(job.id, step.id, "info", "step_started", step.step_key)
        self.session.commit()
        expected_attempt = step.attempt_count
        step_id = step.id
        step_key = step.step_key
        try:
            result = handler(self.session, job)
        except WorkerShutdownRequested:
            self.session.rollback()
            self._release_step(job.id, step_id, expected_attempt)
            self._log(job.id, step_id, "warning", "step_released_on_shutdown", step_key)
            self.session.commit()
            return None
        except StaleStepExecution:
            self.session.rollback()
            self._log(job.id, step_id, "warning", "stale_step_result_discarded", step_key)
            self.session.commit()
            return None
        except DomainError as exc:
            self.session.rollback()
            result = StepResult("failed", error_code=exc.code, error_message=exc.message)
        except Exception:
            logger.exception("unexpected job step failure", extra={"job_id": str(job.id), "step_key": step.step_key})
            self.session.rollback()
            result = StepResult("failed", error_code="UNEXPECTED_ERROR", error_message="단계 실행 중 오류가 발생했습니다.")
        if not self._finish_step_if_current(step_id, expected_attempt, result):
            self.session.rollback()
            self._log(job.id, step_id, "warning", "stale_step_result_discarded", step_key)
            self.session.commit()
            return None
        self._log(job.id, step_id, "info" if result.status == "succeeded" else "warning", "step_finished", step_key)
        self.session.commit()
        return result.status == "succeeded"

    def _finish_step_if_current(self, step_id: UUID, expected_attempt: int, result: StepResult) -> bool:
        finished_at = utcnow()
        statement = (
            update(JobStep)
            .where(
                JobStep.id == step_id,
                JobStep.status == "running",
                JobStep.attempt_count == expected_attempt,
            )
            .values(
                status=result.status,
                metrics=result.metrics,
                error_code=result.error_code,
                error_message=result.error_message,
                finished_at=finished_at,
                heartbeat_at=finished_at,
            )
            .returning(JobStep.id)
        )
        return self.session.scalar(statement) is not None

    def _release_step(self, job_id: UUID, step_id: UUID, expected_attempt: int) -> None:
        statement = (
            update(JobStep)
            .where(
                JobStep.id == step_id,
                JobStep.status == "running",
                JobStep.attempt_count == expected_attempt,
            )
            .values(
                status="pending",
                error_code=None,
                error_message=None,
                started_at=None,
                finished_at=None,
                heartbeat_at=None,
            )
            .returning(JobStep.id)
        )
        if self.session.scalar(statement) is not None:
            self.session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id, AnalysisJob.status == "running")
                .values(status="pending", finished_at=None)
            )

    def _finish_step(self, step: JobStep, result: StepResult) -> None:
        step.status = result.status
        step.metrics = result.metrics
        step.error_code = result.error_code
        step.error_message = result.error_message
        step.finished_at = utcnow()
        step.heartbeat_at = step.finished_at

    def _finalize(self, job: AnalysisJob) -> None:
        steps = self.repository.list_steps(job.id)
        finalize = next(step for step in steps if step.step_key == "finalize_job")
        required_failed = any(step.is_required and step.status == "failed" for step in steps if step is not finalize)
        optional_incomplete = any(
            not step.is_required and step.status in {"failed", "skipped"} for step in steps
        )
        job.status = "failed" if required_failed else "partial_success" if optional_incomplete else "succeeded"
        job.finished_at = utcnow()
        finalize.status = "succeeded"
        finalize.attempt_count += 1
        finalize.started_at = finalize.finished_at = job.finished_at
        finalize.heartbeat_at = job.finished_at
        finalize.metrics = {"final_status": job.status}

        if required_failed:
            for step in steps:
                if step.status == "pending" and step is not finalize:
                    step.status = "skipped"
                    step.error_code = "UPSTREAM_REQUIRED_STEP_FAILED"
                    step.finished_at = job.finished_at
                    step.heartbeat_at = job.finished_at

    def _log(self, job_id: UUID, step_id: UUID, level: str, event_type: str, message: str) -> None:
        self.session.add(
            OperationLog(job_id=job_id, job_step_id=step_id, level=level, event_type=event_type, message=message)
        )
