from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import AnalysisJob, AnalysisRun
from app.jobs.orchestrator import StepResult
from app.reporting.builder import ReportBuilder
from app.reporting.network import CommentNetworkBuilder


def build_reporting_handlers() -> dict:
    network_builder = CommentNetworkBuilder()
    report_builder = ReportBuilder()

    def build_network(session: Session, job: AnalysisJob) -> StepResult:
        network = network_builder.build(session, _run(session, job))
        return StepResult(metrics={"network_id": str(network.id), **network.summary})

    def build_report(session: Session, job: AnalysisJob) -> StepResult:
        run = _run(session, job)
        report = report_builder.build(session, run)
        run.status = report.status
        return StepResult(metrics={"report_id": str(report.id)})

    return {"build_comment_network": build_network, "build_report_snapshot": build_report}


def _run(session: Session, job: AnalysisJob) -> AnalysisRun:
    run = session.scalar(select(AnalysisRun).where(AnalysisRun.job_id == job.id).order_by(AnalysisRun.started_at.desc()))
    if run is None:
        raise DomainError("ANALYSIS_RUN_NOT_FOUND", "분석 실행 정보가 없습니다.")
    return run
