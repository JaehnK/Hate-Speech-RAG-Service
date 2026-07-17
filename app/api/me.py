from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.jobs import _job_payload
from app.api.reports import _report_list_payload
from app.auth.http import AuthResolver
from app.core.config import Settings
from app.db.models import AnalysisJob, ReportSnapshot
from app.jobs.service import AnalysisJobService


def build_me_router(get_session: Callable[[], Iterator[Session]], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/me", tags=["me"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    resolver = AuthResolver(settings)

    @router.get("/jobs")
    def list_jobs(
        request: Request,
        response: Response,
        session: SessionDependency,
        job_status: str | None = Query(None, alias="status"),
        limit: int = Query(50, ge=1, le=200),
        cursor: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        user = resolver.required(request, response, session)
        statement = select(AnalysisJob).where(AnalysisJob.user_id == user.id)
        if job_status:
            statement = statement.where(AnalysisJob.status == job_status)
        rows = list(session.scalars(statement.order_by(AnalysisJob.created_at.desc(), AnalysisJob.id)))
        page = rows[cursor : cursor + limit]
        service = AnalysisJobService(session)
        items = []
        for job in page:
            report = service.get_report(job.id)
            items.append(_job_payload(job, service.get_steps(job.id), str(report.id) if report else None))
        return _page(items, cursor, limit, len(rows))

    @router.get("/reports")
    def list_reports(
        request: Request,
        response: Response,
        session: SessionDependency,
        limit: int = Query(50, ge=1, le=200),
        cursor: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        user = resolver.required(request, response, session)
        rows = list(
            session.scalars(
                select(ReportSnapshot)
                .where(ReportSnapshot.owner_user_id == user.id)
                .order_by(ReportSnapshot.created_at.desc(), ReportSnapshot.id)
            )
        )
        return _page([_report_list_payload(row) for row in rows[cursor : cursor + limit]], cursor, limit, len(rows))

    return router


def _page(items: list, cursor: int, limit: int, total: int) -> dict[str, Any]:
    next_cursor = cursor + limit if cursor + limit < total else None
    return {"items": items, "total": total, "next_cursor": next_cursor, "has_more": next_cursor is not None}
