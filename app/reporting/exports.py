from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import ReportExport, ReportSnapshot, utcnow
from app.reporting.renderers import ExcelExporter, FileStorage, HtmlReportRenderer


class ExportService:
    def __init__(self, storage: FileStorage) -> None:
        self.storage = storage
        self.html = HtmlReportRenderer()
        self.excel = ExcelExporter()

    def create(self, session: Session, report: ReportSnapshot, format: str) -> ReportExport:
        if format not in {"html", "xlsx"}:
            raise DomainError("UNSUPPORTED_EXPORT_FORMAT", "지원하지 않는 export 형식입니다.", status_code=400)
        export = ReportExport(report_snapshot_id=report.id, format=format, status="running")
        session.add(export)
        session.flush()
        try:
            content = self.html.render(report).encode("utf-8") if format == "html" else self.excel.render(session, report)
            uri, size, checksum = self.storage.write(f"{report.id}/{export.id}.{format}", content)
            export.status = "succeeded"
            export.file_uri = uri
            export.file_size_bytes = size
            export.checksum = checksum
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
