from collections.abc import Callable, Iterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.http import AuthResolver, require_csrf
from app.auth.services import require_valid_api_keys
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import AnalysisJob, JobStep
from app.jobs.service import AnalysisJobService


class CreateJobRequest(BaseModel):
    input_value: str = Field(min_length=1, max_length=2048)


def build_jobs_router(get_session: Callable[[], Iterator[Session]], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/analysis-jobs", tags=["analysis-jobs"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    resolver = AuthResolver(settings)

    @router.post("", status_code=status.HTTP_202_ACCEPTED)
    def create_job(body: CreateJobRequest, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        user = None
        if settings.auth_configured:
            require_csrf(request, settings)
            user = resolver.required(request, response, session)
            require_valid_api_keys(session, user.id)
        job = AnalysisJobService(session).create_job(body.input_value, user_id=user.id if user else None)
        return {
            "job_id": str(job.id),
            "user_id": str(job.user_id) if job.user_id else None,
            "youtube_video_id": job.youtube_video_id,
            "status": job.status,
            "status_url": f"/api/analysis-jobs/{job.id}",
            "created_at": job.created_at,
        }

    @router.get("/{job_id}")
    def get_job(job_id: UUID, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        service = AnalysisJobService(session)
        job = service.get_job(job_id)
        _authorize_job(job, request, response, session, settings, resolver)
        steps = service.get_steps(job_id)
        report = service.get_report(job_id)
        return _job_payload(job, steps, str(report.id) if report else None)

    @router.get("/{job_id}/steps")
    def get_steps(job_id: UUID, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        service = AnalysisJobService(session)
        job = service.get_job(job_id)
        _authorize_job(job, request, response, session, settings, resolver)
        return {"items": [_step_payload(step) for step in service.get_steps(job_id)]}

    return router


def _authorize_job(
    job: AnalysisJob,
    request: Request,
    response: Response,
    session: Session,
    settings: Settings,
    resolver: AuthResolver,
) -> None:
    if not settings.auth_configured:
        return
    user = resolver.required(request, response, session)
    if job.user_id != user.id:
        raise DomainError("JOB_FORBIDDEN", "이 분석 job을 조회할 권한이 없습니다.", status_code=403)


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
