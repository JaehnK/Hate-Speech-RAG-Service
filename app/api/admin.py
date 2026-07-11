import hmac
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import AnalysisJob, ApiQuotaEvent, OperationLog
from app.db.repositories import AnalysisJobRepository


RETRYABLE_CODES = {
    "YOUTUBE_QUOTA_EXCEEDED",
    "YOUTUBE_RATE_LIMITED",
    "YOUTUBE_API_ERROR",
    "COMMENT_COLLECTION_INCOMPLETE",
    "CAPTION_COLLECTION_ERROR",
    "EXAMPLE_VECTOR_STORE_UNAVAILABLE",
    "DEFINITION_VECTOR_STORE_UNAVAILABLE",
    "LLM_RATE_LIMITED",
    "LLM_TIMEOUT",
    "LLM_ERROR",
    "NETWORK_BUILD_ERROR",
    "REPORT_BUILD_ERROR",
    "EXPORT_ERROR",
    "UNEXPECTED_ERROR",
}


def build_admin_router(get_session: Callable[[], Iterator[Session]], settings: Settings) -> APIRouter:
    SessionDependency = Annotated[Session, Depends(get_session)]

    def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
        if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
            raise DomainError("ADMIN_UNAUTHORIZED", "관리자 인증이 필요합니다.", status_code=401)

    router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

    @router.get("/jobs")
    def list_jobs(
        session: SessionDependency,
        job_status: str | None = Query(None, alias="status"),
        youtube_video_id: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        cursor: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        statement = select(AnalysisJob).order_by(AnalysisJob.created_at.desc())
        if job_status:
            statement = statement.where(AnalysisJob.status == job_status)
        if youtube_video_id:
            statement = statement.where(AnalysisJob.youtube_video_id == youtube_video_id)
        jobs = list(session.scalars(statement))
        page = jobs[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(jobs) else None
        return {
            "items": [_job_summary(job) for job in page],
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

    @router.get("/jobs/{job_id}")
    def get_job(job_id: UUID, session: SessionDependency) -> dict[str, Any]:
        repository = AnalysisJobRepository(session)
        job = repository.get(job_id)
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "분석 job을 찾을 수 없습니다.", status_code=404)
        failed = [
            {"step_key": step.step_key, "error_code": step.error_code, "retryable": step.error_code in RETRYABLE_CODES}
            for step in repository.list_steps(job.id)
            if step.status == "failed"
        ]
        return {**_job_summary(job), "retryable": any(item["retryable"] for item in failed), "failed_steps": failed}

    @router.post("/jobs/{job_id}/retry", status_code=202)
    def retry_job(job_id: UUID, session: SessionDependency) -> dict[str, Any]:
        repository = AnalysisJobRepository(session)
        job = repository.get(job_id)
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "분석 job을 찾을 수 없습니다.", status_code=404)
        steps = repository.list_steps(job.id)
        failed_index = next(
            (index for index, step in enumerate(steps) if step.status == "failed" and step.error_code in RETRYABLE_CODES),
            None,
        )
        if failed_index is None:
            raise DomainError("JOB_NOT_RETRYABLE", "재시도 가능한 실패 단계가 없습니다.", status_code=409)
        for step in steps[failed_index:]:
            step.status = "pending"
            step.error_code = None
            step.error_message = None
            step.started_at = None
            step.finished_at = None
        job.status = "pending"
        job.error_summary = None
        job.finished_at = None
        session.commit()
        return {"job_id": str(job.id), "status": job.status, "retry_mode": "same_job_failed_step"}

    @router.get("/settings")
    def get_settings() -> dict[str, Any]:
        vector_path = Path(settings.chroma_persist_directory)
        return {
            "youtube_api_key": {"is_configured": bool(settings.youtube_api_key)},
            "llm": {"provider": settings.llm_provider, "model": settings.llm_model, "api_key_configured": bool(settings.llm_api_key)},
            "embedding": {"provider": settings.embedding_provider, "model": settings.embedding_model, "api_key_configured": bool(settings.embedding_api_key)},
            "vector_stores": {
                "provider": "chroma",
                "examples": {"collection": EXAMPLE_COLLECTION_NAME, "is_configured": vector_path.exists()},
                "definitions": {"collection": DEFINITION_COLLECTION_NAME, "corpus_version": DEFAULT_DEFINITION_CORPUS_VERSION, "is_configured": vector_path.exists()},
            },
        }

    @router.get("/logs")
    def get_logs(
        session: SessionDependency,
        job_id: UUID | None = None,
        level: str | None = None,
        event_type: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        statement = select(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit)
        if job_id:
            statement = statement.where(OperationLog.job_id == job_id)
        if level:
            statement = statement.where(OperationLog.level == level)
        if event_type:
            statement = statement.where(OperationLog.event_type == event_type)
        return {
            "items": [
                {"created_at": row.created_at, "level": row.level, "event_type": row.event_type, "message": row.message, "metadata": row.metadata_json}
                for row in session.scalars(statement)
            ]
        }

    @router.get("/quota-events")
    def get_quota_events(
        session: SessionDependency,
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        rows = session.scalars(select(ApiQuotaEvent).order_by(ApiQuotaEvent.created_at.desc()).limit(limit))
        return {
            "items": [
                {
                    "provider": row.provider,
                    "operation": row.operation,
                    "status": row.status,
                    "quota_cost": row.quota_cost,
                    "error_code": row.error_code,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        }

    return router


def _job_summary(job: AnalysisJob) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "youtube_video_id": job.youtube_video_id,
        "status": job.status,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "error_summary": job.error_summary,
    }
