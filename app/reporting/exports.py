from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import ReportExport, ReportSnapshot, utcnow
from app.reporting.renderers import ExcelExporter, HtmlReportRenderer


class ExportService:
    def __init__(self) -> None:
        self.html = HtmlReportRenderer()
        self.excel = ExcelExporter()
        # Exports rendered by an older deploy may use outdated templates, so only reuse files from this process.
        self.started_at = utcnow()

    def create(self, session: Session, report: ReportSnapshot, format: str) -> ReportExport:
        if format not in {"html", "xlsx"}:
            raise DomainError("UNSUPPORTED_EXPORT_FORMAT", "지원하지 않는 export 형식입니다.", status_code=400)
        export = ReportExport(report_snapshot_id=report.id, format=format, status="running")
        session.add(export)
        session.flush()
        try:
            content = self.html.render(session, report).encode("utf-8") if format == "html" else self.excel.render(session, report)
            export.status = "succeeded"
            export.file_blob = content
            export.file_size_bytes = len(content)
            export.checksum = hashlib.sha256(content).hexdigest()
        except Exception as exc:
            export.status = "failed"
            export.error_code = "EXPORT_ERROR"
            export.error_message = "보고서 export 생성에 실패했습니다."
            export.finished_at = utcnow()
            session.commit()
            raise DomainError("EXPORT_ERROR", export.error_message, retryable=True) from exc
        export.finished_at = utcnow()
        session.commit()
        return export

    def latest_succeeded(self, session: Session, report: ReportSnapshot, format: str) -> ReportExport | None:
        return session.scalars(
            select(ReportExport)
            .where(
                ReportExport.report_snapshot_id == report.id,
                ReportExport.format == format,
                ReportExport.status == "succeeded",
                ReportExport.created_at >= self.started_at,
            )
            .order_by(ReportExport.created_at.desc())
            .limit(1)
        ).first()
