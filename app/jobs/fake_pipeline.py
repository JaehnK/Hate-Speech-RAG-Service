from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from app.analysis.prompt_template import PROMPT_VERSION
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION, TAXONOMY_VERSION
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME
from app.db.models import AnalysisJob, AnalysisRun, ReportSnapshot, VideoMetadataSnapshot
from app.jobs.orchestrator import StepResult


def build_fake_handlers() -> dict:
    return {
        "collect_metadata": _collect_metadata,
        "collect_comments": lambda _s, _j: StepResult(metrics={"comments_collected": 0}),
        "collect_transcript": lambda _s, _j: StepResult(metrics={"segments_collected": 0}),
        "create_analysis_run": _create_analysis_run,
        "analyze_comments": lambda _s, _j: StepResult(metrics={"comments_analyzed": 0}),
        "analyze_script": lambda _s, _j: StepResult(metrics={"script_segments_analyzed": 0}),
        "build_comment_network": lambda _s, _j: StepResult(metrics={"nodes": 0, "edges": 0}),
        "build_report_snapshot": _build_report,
    }


def _collect_metadata(session: Session, job: AnalysisJob) -> StepResult:
    session.add(
        VideoMetadataSnapshot(
            job_id=job.id,
            youtube_video_id=job.youtube_video_id,
            title=f"Fake video {job.youtube_video_id}",
            channel_title="Fake channel",
            raw_payload={"mode": "fake"},
        )
    )
    return StepResult(metrics={"video_count": 1})


def _create_analysis_run(session: Session, job: AnalysisJob) -> StepResult:
    session.add(
        AnalysisRun(
            job_id=job.id,
            youtube_video_id=job.youtube_video_id,
            status="running",
            llm_provider="fake",
            llm_model="fake",
            embedding_provider="hash",
            embedding_model="hash-v1",
            example_vector_collection=EXAMPLE_COLLECTION_NAME,
            definition_vector_collection=DEFINITION_COLLECTION_NAME,
            definition_corpus_version=DEFAULT_DEFINITION_CORPUS_VERSION,
            retriever_config={"mode": "fake", "taxonomy_version": TAXONOMY_VERSION},
            prompt_versions={"comment": PROMPT_VERSION, "script": PROMPT_VERSION},
        )
    )
    session.flush()
    return StepResult(metrics={"analysis_run_count": 1})


def _build_report(session: Session, job: AnalysisJob) -> StepResult:
    run = session.scalar(select(AnalysisRun).where(AnalysisRun.job_id == job.id))
    metadata = session.scalar(select(VideoMetadataSnapshot).where(VideoMetadataSnapshot.job_id == job.id))
    if run is None or metadata is None:
        return StepResult("failed", error_code="REPORT_BUILD_ERROR", error_message="필수 artifact가 없습니다.")
    run.status = "succeeded"
    report_id = uuid4()
    report = ReportSnapshot(
        id=report_id,
        analysis_run_id=run.id,
        owner_user_id=job.user_id,
        status="succeeded",
        title=metadata.title or job.youtube_video_id,
        payload={
            "report_id": str(report_id),
            "job_id": str(job.id),
            "video": {"youtube_video_id": job.youtube_video_id, "title": metadata.title},
            "sections": {"comments": {"status": "succeeded"}, "script": {"status": "succeeded"}, "network": {"status": "succeeded"}},
            "mode": "fake" if run.llm_provider == "fake" else "production",
        },
        source_counts={"comments": 0, "script_segments": 0},
    )
    session.add(report)
    session.flush()
    return StepResult(metrics={"report_id": str(report.id)})
