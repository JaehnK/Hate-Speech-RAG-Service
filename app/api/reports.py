from collections.abc import Callable, Iterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import ReportSnapshot


def build_reports_router(get_session: Callable[[], Iterator[Session]]) -> APIRouter:
    router = APIRouter(prefix="/api/reports", tags=["reports"])
    SessionDependency = Annotated[Session, Depends(get_session)]

    @router.get("/{report_id}")
    def get_report(report_id: UUID, session: SessionDependency) -> dict[str, Any]:
        report = session.get(ReportSnapshot, report_id)
        if report is None:
            raise DomainError("REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.", status_code=404)
        return {
            "report_id": str(report.id),
            "analysis_run_id": str(report.analysis_run_id),
            "status": report.status,
            "title": report.title,
            "payload": report.payload,
            "source_counts": report.source_counts,
            "failure_summary": report.failure_summary,
            "created_at": report.created_at,
        }

    return router
