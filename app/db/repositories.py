from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, JobStep, OperationLog


DEFAULT_JOB_STEPS = (
    ("validate_input", True),
    ("collect_metadata", True),
    ("collect_comments", False),
    ("collect_transcript", False),
    ("create_analysis_run", True),
    ("analyze_comments", False),
    ("analyze_script", False),
    ("build_comment_network", False),
    ("build_report_snapshot", True),
    ("finalize_job", True),
)


class AnalysisJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        input_value: str,
        youtube_video_id: str,
        user_id: UUID | None = None,
        request_options: dict | None = None,
        steps: Iterable[tuple[str, bool]] = DEFAULT_JOB_STEPS,
    ) -> AnalysisJob:
        job = AnalysisJob(
            user_id=user_id,
            input_value=input_value,
            youtube_video_id=youtube_video_id,
            request_options=request_options or {},
        )
        self.session.add(job)
        self.session.flush()
        self.session.add_all(
            JobStep(job_id=job.id, step_key=step_key, is_required=is_required)
            for step_key, is_required in steps
        )
        self.session.flush()
        return job

    def get(self, job_id: UUID) -> AnalysisJob | None:
        return self.session.get(AnalysisJob, job_id)

    def list_steps(self, job_id: UUID) -> list[JobStep]:
        statement: Select[tuple[JobStep]] = select(JobStep).where(JobStep.job_id == job_id)
        steps = list(self.session.scalars(statement))
        order = {step_key: index for index, (step_key, _required) in enumerate(DEFAULT_JOB_STEPS)}
        return sorted(steps, key=lambda step: order[step.step_key])

    def claim_pending(self) -> AnalysisJob | None:
        statement = (
            select(AnalysisJob)
            .where(AnalysisJob.status == "pending")
            .order_by(AnalysisJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return self.session.scalar(statement)

    def recover_stale_running(self, stale_before: datetime) -> AnalysisJob | None:
        statement = (
            select(AnalysisJob)
            .join(JobStep, JobStep.job_id == AnalysisJob.id)
            .where(
                AnalysisJob.status == "running",
                JobStep.status == "running",
                func.coalesce(JobStep.heartbeat_at, JobStep.started_at) < stale_before,
            )
            .order_by(JobStep.started_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = self.session.scalar(statement)
        if job is None:
            return None

        running_step = next(step for step in self.list_steps(job.id) if step.status == "running")
        running_step.status = "pending"
        running_step.error_code = None
        running_step.error_message = None
        running_step.started_at = None
        running_step.finished_at = None
        running_step.heartbeat_at = None
        job.status = "pending"
        job.finished_at = None
        self.session.add(
            OperationLog(
                job_id=job.id,
                job_step_id=running_step.id,
                level="warning",
                event_type="stale_job_recovered",
                message=running_step.step_key,
                metadata_json={"attempt_count": running_step.attempt_count},
            )
        )
        self.session.flush()
        return job
