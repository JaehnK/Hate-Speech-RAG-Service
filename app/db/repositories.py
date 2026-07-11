from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, JobStep


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
        request_options: dict | None = None,
        steps: Iterable[tuple[str, bool]] = DEFAULT_JOB_STEPS,
    ) -> AnalysisJob:
        job = AnalysisJob(
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
