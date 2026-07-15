from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.collectors.comments import CommentCollector
from app.collectors.metadata import VideoMetadataCollector
from app.collectors.transcript import TranscriptCollector
from app.core.errors import DomainError
from app.db.models import AnalysisJob, AnalysisRun, ApiQuotaEvent, CommentSnapshot, TranscriptSegment, TranscriptSnapshot
from app.jobs.orchestrator import StepResult
from app.jobs.progress import JobProgressReporter


def build_collection_analysis_handlers(
    metadata_collector: VideoMetadataCollector,
    comment_collector: CommentCollector,
    transcript_collector: TranscriptCollector,
    comment_analyzer: CommentAnalyzer,
    script_analyzer: ScriptAnalyzer,
    analysis_run_values: dict,
    progress_reporter: JobProgressReporter | None = None,
) -> dict:
    def collect_metadata(session: Session, job: AnalysisJob) -> StepResult:
        metadata_collector.collect(session, job)
        _quota_event(session, job, "videos.list", "used")
        return StepResult(metrics={"video_count": 1})

    def collect_comments(session: Session, job: AnalysisJob) -> StepResult:
        try:
            comments = comment_collector.collect_all(session, job)
        except DomainError as exc:
            _quota_event(session, job, "commentThreads.list", _quota_status(exc.code), exc.code)
            if exc.code == "COMMENTS_DISABLED":
                return StepResult("skipped", error_code=exc.code, error_message=exc.message)
            return StepResult("failed", error_code=exc.code, error_message=exc.message)
        _quota_event(session, job, "commentThreads.list", "used")
        return StepResult(metrics={"comments_collected": len(comments)})

    def collect_transcript(session: Session, job: AnalysisJob) -> StepResult:
        try:
            _snapshot, segments = transcript_collector.collect(session, job)
        except DomainError as exc:
            if exc.code == "CAPTION_NOT_AVAILABLE":
                return StepResult("skipped", error_code=exc.code, error_message=exc.message)
            raise
        return StepResult(metrics={"segments_collected": len(segments)})

    def create_analysis_run(session: Session, job: AnalysisJob) -> StepResult:
        run = AnalysisRun(job_id=job.id, youtube_video_id=job.youtube_video_id, status="running", **analysis_run_values)
        session.add(run)
        session.flush()
        return StepResult(metrics={"analysis_run_id": str(run.id)})

    def analyze_comments(session: Session, job: AnalysisJob) -> StepResult:
        if _step_status(session, job, "collect_comments") != "succeeded":
            return StepResult("skipped", error_code="COMMENT_COLLECTION_INCOMPLETE")
        count = session.scalar(select(func.count()).select_from(CommentSnapshot).where(CommentSnapshot.job_id == job.id))
        if not count:
            return StepResult("skipped", error_code="COMMENTS_UNAVAILABLE")
        return StepResult(metrics=comment_analyzer.analyze(session, _run(session, job), progress_reporter))

    def analyze_script(session: Session, job: AnalysisJob) -> StepResult:
        if _step_status(session, job, "collect_transcript") != "succeeded":
            return StepResult("skipped", error_code="CAPTION_NOT_AVAILABLE")
        count = session.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .join(TranscriptSnapshot, TranscriptSegment.transcript_snapshot_id == TranscriptSnapshot.id)
            .where(TranscriptSnapshot.job_id == job.id)
        )
        if not count:
            return StepResult("skipped", error_code="CAPTION_NOT_AVAILABLE")
        return StepResult(metrics=script_analyzer.analyze(session, _run(session, job), progress_reporter))

    return {
        "collect_metadata": collect_metadata,
        "collect_comments": collect_comments,
        "collect_transcript": collect_transcript,
        "create_analysis_run": create_analysis_run,
        "analyze_comments": analyze_comments,
        "analyze_script": analyze_script,
    }


def _run(session: Session, job: AnalysisJob) -> AnalysisRun:
    run = session.scalar(select(AnalysisRun).where(AnalysisRun.job_id == job.id).order_by(AnalysisRun.started_at.desc()))
    if run is None:
        raise DomainError("ANALYSIS_RUN_NOT_FOUND", "분석 실행 정보가 없습니다.")
    return run


def _step_status(session: Session, job: AnalysisJob, step_key: str) -> str | None:
    from app.db.models import JobStep

    return session.scalar(select(JobStep.status).where(JobStep.job_id == job.id, JobStep.step_key == step_key))


def _quota_event(session: Session, job: AnalysisJob, operation: str, status: str, error_code: str | None = None) -> None:
    session.add(
        ApiQuotaEvent(
            job_id=job.id,
            provider="youtube",
            operation=operation,
            quota_cost=1,
            status=status,
            error_code=error_code,
            metadata_json={},
        )
    )


def _quota_status(error_code: str) -> str:
    if error_code == "YOUTUBE_QUOTA_EXCEEDED":
        return "quota_exceeded"
    if error_code == "YOUTUBE_RATE_LIMITED":
        return "rate_limited"
    return "failed"
