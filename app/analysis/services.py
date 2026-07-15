from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import SourceType
from app.analysis.rag_classifier import ClassificationError, ClassificationResult
from app.db.models import AnalysisRun, CommentAnalysisResult, CommentSnapshot, ScriptAnalysisResult, TranscriptSegment, TranscriptSnapshot
from app.jobs.progress import JobProgressReporter


class Classifier(Protocol):
    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult: ...


class CommentAnalyzer:
    def __init__(self, classifier: Classifier) -> None:
        self.classifier = classifier

    def analyze(
        self,
        session: Session,
        run: AnalysisRun,
        progress: JobProgressReporter | None = None,
        step_key: str = "analyze_comments",
    ) -> dict[str, int]:
        comments = list(session.scalars(select(CommentSnapshot).where(CommentSnapshot.job_id == run.job_id)))
        _start_progress(progress, run.job_id, step_key, len(comments))
        succeeded = failed = 0
        for comment in comments:
            source_type = "reply" if comment.is_reply else "comment"
            result = _classify(self.classifier, comment.text_original or comment.text_display or "", source_type)
            row = CommentAnalysisResult(analysis_run_id=run.id, comment_snapshot_id=comment.id, **result)
            session.add(row)
            succeeded += row.status == "succeeded"
            failed += row.status == "failed"
            _advance_progress(progress, run.job_id, step_key, row.status == "succeeded")
        session.flush()
        return {"comments_analyzed": len(comments), "succeeded": succeeded, "failed": failed}


class ScriptAnalyzer:
    def __init__(self, classifier: Classifier) -> None:
        self.classifier = classifier

    def analyze(
        self,
        session: Session,
        run: AnalysisRun,
        progress: JobProgressReporter | None = None,
        step_key: str = "analyze_script",
    ) -> dict[str, int]:
        statement = (
            select(TranscriptSegment)
            .join(TranscriptSnapshot, TranscriptSegment.transcript_snapshot_id == TranscriptSnapshot.id)
            .where(TranscriptSnapshot.job_id == run.job_id)
            .order_by(TranscriptSegment.segment_index)
        )
        segments = list(session.scalars(statement))
        _start_progress(progress, run.job_id, step_key, len(segments))
        succeeded = failed = 0
        for segment in segments:
            result = _classify(self.classifier, segment.text, "script_segment")
            row = ScriptAnalysisResult(analysis_run_id=run.id, transcript_segment_id=segment.id, **result)
            session.add(row)
            succeeded += row.status == "succeeded"
            failed += row.status == "failed"
            _advance_progress(progress, run.job_id, step_key, row.status == "succeeded")
        session.flush()
        return {"script_segments_analyzed": len(segments), "succeeded": succeeded, "failed": failed}


def _classify(classifier: Classifier, text: str, source_type: SourceType) -> dict:
    try:
        result = classifier.classify_text(text, source_type)
    except ClassificationError as exc:
        return {
            "status": "failed",
            "error_code": "LLM_ERROR",
            "error_message": str(exc),
        }
    payload = result.payload
    return {
        "status": "succeeded",
        "is_hate_speech": payload["is_hate_speech"],
        "categories": payload["categories"],
        "target_group": payload.get("target_group"),
        "hate_type": payload.get("hate_type"),
        "reasoning": payload.get("reasoning"),
        "similar_cases_used": payload.get("similar_cases_used", []),
        "definition_docs_used": payload.get("definition_docs_used", []),
        "rag_context_status": result.rag_context_status,
        "prompt_version": result.prompt_version,
        "model_name": result.model,
        "raw_response": payload,
    }


def _start_progress(progress: JobProgressReporter | None, job_id: UUID, step_key: str, total: int) -> None:
    if progress is not None:
        progress.start(job_id, step_key, total)


def _advance_progress(progress: JobProgressReporter | None, job_id: UUID, step_key: str, succeeded: bool) -> None:
    if progress is not None:
        progress.advance(job_id, step_key, succeeded)
