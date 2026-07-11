from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import ReportExport


def build_exports_router(get_session: Callable[[], Iterator[Session]], storage_dir: str) -> APIRouter:
    router = APIRouter(prefix="/api/exports", tags=["exports"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    storage_root = Path(storage_dir).resolve()

    @router.get("/{export_id}")
    def get_export(export_id: UUID, session: SessionDependency) -> dict[str, Any]:
        export = _export(session, export_id)
        return {
            "export_id": str(export.id),
            "report_id": str(export.report_snapshot_id),
            "format": export.format,
            "status": export.status,
            "file_size_bytes": export.file_size_bytes,
            "download_url": f"/api/exports/{export.id}/download" if export.status == "succeeded" else None,
            "created_at": export.created_at,
            "finished_at": export.finished_at,
        }

    @router.get("/{export_id}/download")
    def download_export(export_id: UUID, session: SessionDependency) -> FileResponse:
        export = _export(session, export_id)
        if export.status != "succeeded" or not export.file_uri:
            raise DomainError("EXPORT_NOT_READY", "Export 파일이 준비되지 않았습니다.", status_code=409)
        path = Path(export.file_uri).resolve()
        if storage_root not in path.parents or not path.is_file():
            raise DomainError("EXPORT_FILE_NOT_FOUND", "Export 파일을 찾을 수 없습니다.", status_code=404)
        media_type = "text/html" if export.format == "html" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return FileResponse(path, media_type=media_type, filename=path.name)

    return router


def _export(session: Session, export_id: UUID) -> ReportExport:
    export = session.get(ReportExport, export_id)
    if export is None:
        raise DomainError("EXPORT_NOT_FOUND", "Export 작업을 찾을 수 없습니다.", status_code=404)
    return export
