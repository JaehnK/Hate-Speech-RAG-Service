from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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


# Mirrors CATEGORY_LABELS in frontend/src/utils.ts so the export reads like the web report.
CATEGORY_LABELS = {
    "gender": "성별",
    "age": "연령",
    "identity": "정체성",
    "profanity": "욕설",
    "state_authority": "국가 권위체",
    "non_state_authority": "비국가 권위체",
    "state_regime": "국가 제도",
    "non_state_regime": "비국가 제도",
    "state_community": "국가 공동체",
    "non_state_community": "비국가 공동체",
    "no_target": "대상 없음",
    "other": "기타",
    "unclassified": "미분류",
}

RAG_CONTEXT_LABELS = {
    "complete": "정의·유사 사례 사용",
    "definition_only": "정의 문서만 사용",
    "example_only": "유사 사례만 사용",
    "unavailable": "검색 근거 없음",
}


class HtmlReportRenderer:
    def __init__(self) -> None:
        template_dir = Path(__file__).with_name("templates")
        self.environment = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(("html", "xml")),
        )
        self.environment.filters["category"] = category_label
        self.environment.filters["rag_context"] = lambda status: RAG_CONTEXT_LABELS.get(status or "", "상태 미기록")
        self.environment.filters["playback"] = _playback_time
        self.environment.filters["number"] = lambda value: f"{value or 0:,}"

    def render(self, session: Session, report: ReportSnapshot) -> str:
        payload = report.payload
        summary = payload.get("comment_analysis_summary") or {}
        collection = payload.get("collection_summary") or {}
        total = summary.get("total") or 0
        categories = sorted((summary.get("category_distribution") or {}).items(), key=lambda item: item[1], reverse=True)
        hate_comments = [
            (comment, result)
            for comment, result in session.execute(
                select(CommentSnapshot, CommentAnalysisResult)
                .join(CommentAnalysisResult, CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id)
                .where(CommentAnalysisResult.analysis_run_id == report.analysis_run_id, CommentAnalysisResult.is_hate_speech.is_(True))
                .order_by(func.coalesce(CommentSnapshot.like_count, 0).desc(), CommentSnapshot.collected_at.desc(), CommentSnapshot.id)
            )
        ]
        script_segments = session.execute(
            select(TranscriptSegment, ScriptAnalysisResult)
            .join(ScriptAnalysisResult, ScriptAnalysisResult.transcript_segment_id == TranscriptSegment.id)
            .where(ScriptAnalysisResult.analysis_run_id == report.analysis_run_id)
            .order_by(TranscriptSegment.segment_index)
        ).all()
        return self.environment.get_template("report.html").render(
            report=report,
            payload=payload,
            video=payload.get("video") or {},
            collected=(collection.get("comments_collected") or 0) + (collection.get("replies_collected") or 0),
            summary=summary,
            hate_ratio=_percent(summary.get("hate_speech_count") or 0, total),
            categories=[(name, count, _percent(count, total)) for name, count in categories],
            hate_comments=hate_comments,
            script_summary=payload.get("script_analysis_summary") or {},
            script_segments=script_segments,
            network=_network_overview(session, report),
            config=payload.get("analysis_config") or {},
        )


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, f"알 수 없는 분류 ({category})")


def _percent(part: int, total: int) -> float:
    return part / total * 100 if total else 0.0


def _playback_time(value) -> str:
    seconds = max(0, int(float(value or 0)))
    hours, minutes, remainder = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{hours}:{minutes:02d}:{remainder:02d}" if hours else f"{minutes}:{remainder:02d}"


def _network_overview(session: Session, report: ReportSnapshot) -> dict | None:
    network = session.scalar(select(CommentNetwork).where(CommentNetwork.analysis_run_id == report.analysis_run_id))
    if network is None:
        return None
    nodes = list(session.scalars(select(CommentNetworkNode).where(CommentNetworkNode.network_id == network.id)))
    edges = list(session.scalars(select(CommentNetworkEdge).where(CommentNetworkEdge.network_id == network.id)))
    # Same formulas as buildNetworkMetrics in frontend/src/CommentNetworkGraph.tsx.
    connected = {key for edge in edges for key in (edge.source_node_key, edge.target_node_key)}
    unique_edges = {(edge.source_node_key, edge.target_node_key) for edge in edges if edge.source_node_key != edge.target_node_key}
    node_count = len(nodes)
    degrees = [float((node.metrics or {}).get("degree") or 0) for node in nodes]
    top_authors = sorted(
        (node for node in nodes if node.hate_speech_count),
        key=lambda node: (node.hate_speech_count, node.comment_count, float((node.metrics or {}).get("degree") or 0)),
        reverse=True,
    )[:10]
    return {
        "node_count": node_count,
        "edge_count": len(edges),
        "connected_nodes": len(connected),
        "isolated_nodes": max(0, node_count - len(connected)),
        "hate_nodes": sum(1 for node in nodes if node.hate_speech_count > 0),
        "hate_edges": sum(1 for edge in edges if edge.is_hate_speech),
        "average_degree": sum(degrees) / node_count if node_count else 0.0,
        "density": len(unique_edges) / (node_count * (node_count - 1)) * 100 if node_count > 1 else 0.0,
        "top_authors": top_authors,
    }


class ExcelExporter:
    def render(self, session: Session, report: ReportSnapshot) -> bytes:
        from io import BytesIO

        workbook = Workbook()
        summary = workbook.active
        summary.title = "summary"
        summary.append(["field", "value"])
        for key, value in _flatten(report.payload):
            summary.append([key, value])

        comments = workbook.create_sheet("comment_analysis")
        comments.append(["youtube_comment_id", "is_reply", "text", "status", "is_hate_speech", "categories", "분석 사유"])
        for comment, result in session.execute(
            select(CommentSnapshot, CommentAnalysisResult)
            .join(CommentAnalysisResult, CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id)
            .where(CommentAnalysisResult.analysis_run_id == report.analysis_run_id)
        ):
            comments.append([comment.youtube_comment_id, comment.is_reply, comment.text_original, result.status, result.is_hate_speech, _json(result.categories), result.reasoning])

        scripts = workbook.create_sheet("script_analysis")
        scripts.append(["segment_index", "start_seconds", "end_seconds", "text", "status", "is_hate_speech", "categories", "분석 사유"])
        for segment, result in session.execute(
            select(TranscriptSegment, ScriptAnalysisResult)
            .join(ScriptAnalysisResult, ScriptAnalysisResult.transcript_segment_id == TranscriptSegment.id)
            .where(ScriptAnalysisResult.analysis_run_id == report.analysis_run_id)
        ):
            scripts.append([segment.segment_index, float(segment.start_seconds or 0), float(segment.end_seconds or 0), segment.text, result.status, result.is_hate_speech, _json(result.categories), result.reasoning])

        nodes = workbook.create_sheet("network_nodes")
        nodes.append(["node_key", "label", "comment_count", "hate_speech_count", "hate_speech_ratio", "metrics"])
        network = session.scalar(select(CommentNetwork).where(CommentNetwork.analysis_run_id == report.analysis_run_id))
        if network:
            for node in session.scalars(select(CommentNetworkNode).where(CommentNetworkNode.network_id == network.id)):
                nodes.append([node.node_key, node.label, node.comment_count, node.hate_speech_count, float(node.hate_speech_ratio), _json(node.metrics)])

        edges = workbook.create_sheet("network_edges")
        edges.append(["source_node_key", "target_node_key", "edge_type", "weight", "is_hate_speech"])
        if network:
            for edge in session.scalars(select(CommentNetworkEdge).where(CommentNetworkEdge.network_id == network.id)):
                edges.append([edge.source_node_key, edge.target_node_key, edge.edge_type, float(edge.weight), edge.is_hate_speech])

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, _json(value) if isinstance(value, (list, dict)) else value


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
