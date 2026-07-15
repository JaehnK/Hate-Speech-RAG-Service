from collections.abc import Callable, Iterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, JobStep
from app.jobs.service import AnalysisJobService


class CreateJobRequest(BaseModel):
    input_value: str = Field(min_length=1, max_length=2048)


def build_jobs_router(get_session: Callable[[], Iterator[Session]]) -> APIRouter:
    router = APIRouter(prefix="/api/analysis-jobs", tags=["analysis-jobs"])
    SessionDependency = Annotated[Session, Depends(get_session)]

    @router.post("", status_code=status.HTTP_202_ACCEPTED)
    def create_job(request: CreateJobRequest, session: SessionDependency) -> dict[str, Any]:
        job = AnalysisJobService(session).create_job(request.input_value)
        return {
            "job_id": str(job.id),
            "youtube_video_id": job.youtube_video_id,
            "status": job.status,
            "status_url": f"/api/analysis-jobs/{job.id}",
            "created_at": job.created_at,
        }

    @router.get("/{job_id}")
    def get_job(job_id: UUID, session: SessionDependency) -> dict[str, Any]:
        service = AnalysisJobService(session)
        job = service.get_job(job_id)
        steps = service.get_steps(job_id)
        report = service.get_report(job_id)
        return _job_payload(job, steps, str(report.id) if report else None)

    @router.get("/{job_id}/steps")
    def get_steps(job_id: UUID, session: SessionDependency) -> dict[str, Any]:
        return {"items": [_step_payload(step) for step in AnalysisJobService(session).get_steps(job_id)]}

    return router


def _job_payload(job: AnalysisJob, steps: list[JobStep], report_id: str | None) -> dict[str, Any]:
    completed = sum(step.status in {"succeeded", "failed", "skipped"} for step in steps)
    current = next((step.step_key for step in steps if step.status == "running"), None)
    if current is None:
        current = next((step.step_key for step in steps if step.status == "pending"), None)
    summary: dict[str, int] = {}
    for step in steps:
        for key, value in step.metrics.items():
            if isinstance(value, int) and key.endswith(("collected", "analyzed", "items")):
                summary[key] = summary.get(key, 0) + value
    return {
        "job_id": str(job.id),
        "youtube_video_id": job.youtube_video_id,
        "status": job.status,
        "progress": {"percent": round(completed / len(steps) * 100), "current_step": current},
        "steps": [_step_payload(step) for step in steps],
        "summary": summary,
        "links": {
            "report_api": f"/api/reports/{report_id}" if report_id else None,
            "report_page": f"/reports/{report_id}" if report_id else None,
        },
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def _step_payload(step: JobStep) -> dict[str, Any]:
    return {
        "step_key": step.step_key,
        "status": step.status,
        "attempt_count": step.attempt_count,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
        "metrics": step.metrics,
        "item_progress": _item_progress(step),
        "error": (
            {"code": step.error_code, "message": step.error_message}
            if step.error_code or step.error_message
            else None
        ),
    }


def _item_progress(step: JobStep) -> dict[str, int] | None:
    if step.items_total is None:
        return None
    total = step.items_total
    completed = min(step.items_completed, total) if total else step.items_completed
    return {
        "total": total,
        "completed": completed,
        "succeeded": step.items_succeeded,
        "failed": step.items_failed,
        "percent": round(completed / total * 100) if total else 100,
    }
