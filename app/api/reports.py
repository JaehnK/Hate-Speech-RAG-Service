from collections.abc import Callable, Iterator
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.http import AuthResolver, require_csrf
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import (
    CommentAnalysisResult,
    CommentNetwork,
    CommentNetworkEdge,
    CommentNetworkNode,
    CommentSnapshot,
    ReportSnapshot,
    ScriptAnalysisResult,
    TranscriptSegment,
)
from app.reporting.exports import ExportService
from app.reporting.renderers import FileStorage, HtmlReportRenderer


class ExportRequest(BaseModel):
    format: str


def build_reports_router(get_session: Callable[[], Iterator[Session]], storage_dir: str, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/reports", tags=["reports"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    export_service = ExportService(FileStorage(storage_dir))
    resolver = AuthResolver(settings)

    @router.get("/public")
    def get_public_reports(session: SessionDependency, limit: int = Query(12, ge=1, le=50), cursor: int = Query(0, ge=0)) -> dict[str, Any]:
        rows = list(
            session.scalars(
                select(ReportSnapshot)
                .where(ReportSnapshot.is_public_sample.is_(True))
                .order_by(ReportSnapshot.created_at.desc(), ReportSnapshot.id)
            )
        )
        page = rows[cursor : cursor + limit]
        return _page([_report_list_payload(report) for report in page], cursor, limit, len(rows))

    @router.get("/{report_id}")
    def get_report(report_id: UUID, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        report = _authorized_report(session, report_id, request, response, settings, resolver)
        return {
            "report_id": str(report.id),
            "analysis_run_id": str(report.analysis_run_id),
            "status": report.status,
            "title": report.title,
            "created_at": report.created_at,
            **report.payload,
            "links": {
                "comments": f"/api/reports/{report.id}/comments",
                "script_segments": f"/api/reports/{report.id}/script-segments",
                "network": f"/api/reports/{report.id}/network",
                "page": f"/reports/{report.id}",
            },
        }

    @router.get("/{report_id}/comments")
    def get_comments(
        report_id: UUID,
        request: Request,
        response: Response,
        session: SessionDependency,
        limit: int = Query(50, ge=1, le=200),
        cursor: int = Query(0, ge=0),
        is_hate_speech: bool | None = None,
        result_status: str | None = Query(None, alias="status"),
        category: str | None = None,
        author_channel_id: str | None = None,
        sort: Literal["collected_at", "like_count"] = "collected_at",
    ) -> dict[str, Any]:
        report = _authorized_report(session, report_id, request, response, settings, resolver)
        statement = (
            select(CommentSnapshot, CommentAnalysisResult)
            .join(CommentAnalysisResult, CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id)
            .where(CommentAnalysisResult.analysis_run_id == report.analysis_run_id)
        )
        if sort == "like_count":
            statement = statement.order_by(
                func.coalesce(CommentSnapshot.like_count, 0).desc(),
                CommentSnapshot.collected_at.desc(),
                CommentSnapshot.id,
            )
        else:
            statement = statement.order_by(CommentSnapshot.collected_at, CommentSnapshot.id)
        rows = session.execute(statement).all()
        filtered = [
            (comment, result)
            for comment, result in rows
            if (is_hate_speech is None or result.is_hate_speech == is_hate_speech)
            and (result_status is None or result.status == result_status)
            and (category is None or category in (result.categories or []))
            and (author_channel_id is None or comment.author_channel_id == author_channel_id)
        ]
        page = filtered[cursor : cursor + limit]
        return _page([_comment_payload(*row) for row in page], cursor, limit, len(filtered))

    @router.get("/{report_id}/script-segments")
    def get_script_segments(
        report_id: UUID,
        request: Request,
        response: Response,
        session: SessionDependency,
        limit: int = Query(50, ge=1, le=200),
        cursor: int = Query(0, ge=0),
        is_hate_speech: bool | None = None,
        result_status: str | None = Query(None, alias="status"),
    ) -> dict[str, Any]:
        report = _authorized_report(session, report_id, request, response, settings, resolver)
        rows = session.execute(
            select(TranscriptSegment, ScriptAnalysisResult)
            .join(ScriptAnalysisResult, ScriptAnalysisResult.transcript_segment_id == TranscriptSegment.id)
            .where(ScriptAnalysisResult.analysis_run_id == report.analysis_run_id)
            .order_by(TranscriptSegment.segment_index)
        ).all()
        filtered = [
            (segment, result)
            for segment, result in rows
            if (is_hate_speech is None or result.is_hate_speech == is_hate_speech)
            and (result_status is None or result.status == result_status)
        ]
        page = filtered[cursor : cursor + limit]
        return _page([_script_payload(*row) for row in page], cursor, limit, len(filtered))

    @router.get("/{report_id}/network")
    def get_network(report_id: UUID, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        report = _authorized_report(session, report_id, request, response, settings, resolver)
        network = session.scalar(select(CommentNetwork).where(CommentNetwork.analysis_run_id == report.analysis_run_id))
        if network is None:
            raise DomainError("NETWORK_NOT_FOUND", "댓글 네트워크가 없습니다.", status_code=404)
        nodes = list(session.scalars(select(CommentNetworkNode).where(CommentNetworkNode.network_id == network.id)))
        edges = list(session.scalars(select(CommentNetworkEdge).where(CommentNetworkEdge.network_id == network.id)))
        return {
            "network_id": str(network.id),
            "status": network.status,
            "graph_type": network.graph_type,
            "directed": network.directed,
            "summary": network.summary,
            "nodes": [
                {
                    "node_key": node.node_key,
                    "node_type": node.node_type,
                    "label": node.label,
                    "comment_count": node.comment_count,
                    "hate_speech_count": node.hate_speech_count,
                    "hate_speech_ratio": float(node.hate_speech_ratio),
                    "metrics": node.metrics,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "source_node_key": edge.source_node_key,
                    "target_node_key": edge.target_node_key,
                    "edge_type": edge.edge_type,
                    "weight": float(edge.weight),
                    "is_hate_speech": edge.is_hate_speech,
                }
                for edge in edges
            ],
        }

    @router.post("/{report_id}/exports", status_code=status.HTTP_202_ACCEPTED)
    def create_export(report_id: UUID, body: ExportRequest, request: Request, response: Response, session: SessionDependency) -> dict[str, Any]:
        if settings.auth_configured:
            require_csrf(request, settings)
            user = resolver.required(request, response, session)
            report = _report(session, report_id)
            if report.owner_user_id != user.id:
                raise DomainError("REPORT_FORBIDDEN", "이 보고서의 export를 생성할 권한이 없습니다.", status_code=403)
        else:
            report = _report(session, report_id)
        export = export_service.create(session, report, body.format)
        return {
            "export_id": str(export.id),
            "report_id": str(report.id),
            "format": export.format,
            "status": export.status,
            "status_url": f"/api/exports/{export.id}",
        }

    return router


def build_report_pages_router(get_session: Callable[[], Iterator[Session]], settings: Settings) -> APIRouter:
    router = APIRouter(tags=["report-pages"])
    SessionDependency = Annotated[Session, Depends(get_session)]
    renderer = HtmlReportRenderer()
    resolver = AuthResolver(settings)

    @router.get("/reports/{report_id}", response_class=HTMLResponse)
    def report_page(report_id: UUID, request: Request, response: Response, session: SessionDependency) -> str:
        return renderer.render(_authorized_report(session, report_id, request, response, settings, resolver))

    return router


def _report(session: Session, report_id: UUID) -> ReportSnapshot:
    report = session.get(ReportSnapshot, report_id)
    if report is None:
        raise DomainError("REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.", status_code=404)
    return report


def _authorized_report(
    session: Session,
    report_id: UUID,
    request: Request,
    response: Response,
    settings: Settings,
    resolver: AuthResolver,
) -> ReportSnapshot:
    report = _report(session, report_id)
    if not settings.auth_configured or report.is_public_sample:
        return report
    user = resolver.required(request, response, session)
    if report.owner_user_id != user.id:
        raise DomainError("REPORT_FORBIDDEN", "이 보고서를 조회할 권한이 없습니다.", status_code=403)
    return report


def _report_list_payload(report: ReportSnapshot) -> dict[str, Any]:
    summary = report.payload.get("comment_analysis_summary", {})
    collection = report.payload.get("collection_summary", {})
    video = report.payload.get("video", {})
    total = int(summary.get("succeeded") or summary.get("total") or 0)
    hate_count = int(summary.get("hate_speech_count") or 0)
    categories = summary.get("category_distribution") or {}
    return {
        "report_id": str(report.id),
        "youtube_video_id": report.payload.get("youtube_video_id"),
        "status": report.status,
        "created_at": report.created_at,
        "title": video.get("title") or report.title,
        "channel_title": video.get("channel_title"),
        "thumbnail_url": video.get("thumbnail_url"),
        "comments_collected": int(collection.get("comments_collected") or 0) + int(collection.get("replies_collected") or 0),
        "transcript_available": bool(collection.get("transcript_available")),
        "hate_speech_ratio": hate_count / total * 100 if total else 0,
        "top_categories": [name for name, _count in sorted(categories.items(), key=lambda item: item[1], reverse=True)[:3]],
    }


def _analysis_payload(result) -> dict[str, Any]:
    return {
        "status": result.status,
        "is_hate_speech": result.is_hate_speech,
        "categories": result.categories,
        "target_group": result.target_group,
        "hate_type": result.hate_type,
        "reasoning": result.reasoning,
        "rag_context_status": result.rag_context_status,
        "similar_cases_used": result.similar_cases_used,
        "definition_docs_used": result.definition_docs_used,
    }


def _comment_payload(comment, result) -> dict[str, Any]:
    return {
        "comment_snapshot_id": str(comment.id),
        "youtube_comment_id": comment.youtube_comment_id,
        "is_reply": comment.is_reply,
        "parent_youtube_comment_id": comment.parent_youtube_comment_id,
        "author_display_name": comment.author_display_name,
        "author_channel_id": comment.author_channel_id,
        "text_original": comment.text_original,
        "like_count": comment.like_count,
        "published_at": comment.published_at,
        "analysis": _analysis_payload(result),
    }


def _script_payload(segment, result) -> dict[str, Any]:
    return {
        "segment_id": str(segment.id),
        "segment_index": segment.segment_index,
        "start_seconds": float(segment.start_seconds or 0),
        "end_seconds": float(segment.end_seconds or 0),
        "text": segment.text,
        "analysis": _analysis_payload(result),
    }


def _page(items: list, cursor: int, limit: int, total: int) -> dict[str, Any]:
    next_cursor = cursor + limit if cursor + limit < total else None
    return {"items": items, "total": total, "next_cursor": next_cursor, "has_more": next_cursor is not None}
