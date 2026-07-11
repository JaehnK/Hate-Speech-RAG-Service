from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import AnalysisJob, JobStep, ReportSnapshot, AnalysisRun, utcnow
from app.db.repositories import AnalysisJobRepository
from app.jobs.video_id import extract_video_id


class AnalysisJobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AnalysisJobRepository(session)

    def create_job(self, input_value: str) -> AnalysisJob:
        video_id = extract_video_id(input_value)
        job = self.repository.create(input_value, video_id)
        validate_step = next(step for step in self.repository.list_steps(job.id) if step.step_key == "validate_input")
        validate_step.status = "succeeded"
        validate_step.attempt_count = 1
        validate_step.started_at = validate_step.finished_at = utcnow()
        validate_step.metrics = {"youtube_video_id": video_id}
        self.session.commit()
        return job

    def get_job(self, job_id: UUID) -> AnalysisJob:
        job = self.repository.get(job_id)
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "분석 job을 찾을 수 없습니다.", status_code=404)
        return job

    def get_steps(self, job_id: UUID) -> list[JobStep]:
        self.get_job(job_id)
        return self.repository.list_steps(job_id)

    def get_report(self, job_id: UUID) -> ReportSnapshot | None:
        statement = (
            select(ReportSnapshot)
            .join(AnalysisRun, ReportSnapshot.analysis_run_id == AnalysisRun.id)
            .where(AnalysisRun.job_id == job_id)
            .order_by(ReportSnapshot.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)
