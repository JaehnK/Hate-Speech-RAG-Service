from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    AnalysisRun,
    CommentAnalysisResult,
    CommentNetwork,
    CommentSnapshot,
    JobStep,
    ReportSnapshot,
    ScriptAnalysisResult,
    TranscriptSegment,
    TranscriptSnapshot,
    VideoMetadataSnapshot,
)


class ReportBuilder:
    def build(self, session: Session, run: AnalysisRun) -> ReportSnapshot:
        metadata = session.scalar(select(VideoMetadataSnapshot).where(VideoMetadataSnapshot.job_id == run.job_id))
        if metadata is None:
            raise DomainError("REPORT_BUILD_ERROR", "영상 metadata가 없어 보고서를 생성할 수 없습니다.")

        comment_rows = session.execute(
            select(CommentSnapshot, CommentAnalysisResult)
            .outerjoin(
                CommentAnalysisResult,
                (CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id)
                & (CommentAnalysisResult.analysis_run_id == run.id),
            )
            .where(CommentSnapshot.job_id == run.job_id)
        ).all()
        script_rows = session.execute(
            select(TranscriptSegment, ScriptAnalysisResult)
            .join(TranscriptSnapshot, TranscriptSegment.transcript_snapshot_id == TranscriptSnapshot.id)
            .outerjoin(
                ScriptAnalysisResult,
                (ScriptAnalysisResult.transcript_segment_id == TranscriptSegment.id)
                & (ScriptAnalysisResult.analysis_run_id == run.id),
            )
            .where(TranscriptSnapshot.job_id == run.job_id)
        ).all()
        network = session.scalar(select(CommentNetwork).where(CommentNetwork.analysis_run_id == run.id))
        failures = [
            {"step_key": step.step_key, "status": step.status, "error_code": step.error_code, "message": step.error_message}
            for step in session.scalars(select(JobStep).where(JobStep.job_id == run.job_id))
            if step.status in {"failed", "skipped"}
        ]
        comment_summary = _analysis_summary([result for _item, result in comment_rows])
        script_summary = _analysis_summary([result for _item, result in script_rows])
        payload = {
            "youtube_video_id": run.youtube_video_id,
            "video": {
                "title": metadata.title,
                "channel_title": metadata.channel_title,
                "published_at": _iso(metadata.published_at),
                "view_count": metadata.view_count,
                "comment_count": metadata.comment_count,
                "thumbnail_url": metadata.thumbnail_url,
            },
            "collection_summary": {
                "comments_collected": sum(not comment.is_reply for comment, _result in comment_rows),
                "replies_collected": sum(comment.is_reply for comment, _result in comment_rows),
                "transcript_available": bool(script_rows),
            },
            "comment_analysis_summary": comment_summary,
            "script_analysis_summary": script_summary,
            "network_summary": network.summary if network else {"status": "skipped", "node_count": 0, "edge_count": 0},
            "representative_comments": _representative_comments(comment_rows),
            "failure_summary": failures,
            "analysis_config": {
                "llm_provider": run.llm_provider,
                "llm_model": run.llm_model,
                "embedding_provider": run.embedding_provider,
                "embedding_model": run.embedding_model,
                "example_collection": run.example_vector_collection,
                "definition_collection": run.definition_vector_collection,
                "definition_corpus_version": run.definition_corpus_version,
                "prompt_versions": run.prompt_versions,
            },
        }
        report = ReportSnapshot(
            analysis_run_id=run.id,
            status="partial_success" if failures else "succeeded",
            title=f"{metadata.title or run.youtube_video_id} 혐오표현 분석 보고서",
            payload=payload,
            source_counts={"comments": len(comment_rows), "script_segments": len(script_rows)},
            failure_summary={"items": failures} if failures else None,
        )
        session.add(report)
        session.flush()
        return report


def _analysis_summary(results) -> dict:
    existing = [result for result in results if result is not None]
    categories = Counter(category for result in existing if result.categories for category in result.categories if category != "unclassified")
    return {
        "total": len(results),
        "succeeded": sum(result.status == "succeeded" for result in existing),
        "failed": sum(result.status == "failed" for result in existing),
        "missing": len(results) - len(existing),
        "hate_speech_count": sum(bool(result.is_hate_speech) for result in existing),
        "category_distribution": dict(sorted(categories.items())),
    }


def _representative_comments(rows, limit: int = 10) -> list[dict]:
    candidates = [(comment, result) for comment, result in rows if result and result.is_hate_speech]
    candidates.sort(key=lambda row: (row[0].like_count or 0, row[0].published_at or row[0].collected_at), reverse=True)
    return [
        {
            "youtube_comment_id": comment.youtube_comment_id,
            "text": comment.text_original,
            "like_count": comment.like_count,
            "categories": result.categories,
            "reasoning": result.reasoning,
        }
        for comment, result in candidates[:limit]
    ]


def _iso(value):
    return value.isoformat() if value else None
