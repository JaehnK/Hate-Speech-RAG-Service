from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import Base
from app.db.models import OperationLog, utcnow
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.orchestrator import StepResult
from app.jobs.service import AnalysisJobService
from app.jobs.worker import JobWorker
from app.main import create_app


@pytest.mark.asyncio
async def test_job_api_worker_and_fake_report_end_to_end(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'jobs.db'}"))
    Base.metadata.create_all(app.state.engine)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/analysis-jobs", json={"input_value": "https://youtu.be/abcdefghijk"})
        second = await client.post("/api/analysis-jobs", json={"input_value": "abcdefghijk"})
        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["job_id"] != second.json()["job_id"]

        worker = JobWorker(app.state.session_factory)
        assert worker.run_once()
        assert worker.run_once()
        assert not worker.run_once()

        status_response = await client.get(first.json()["status_url"])
        status_payload = status_response.json()
        assert status_payload["status"] == "succeeded"
        assert status_payload["progress"]["percent"] == 100
        assert status_payload["links"]["report_api"]

        report_response = await client.get(status_payload["links"]["report_api"])
        assert report_response.status_code == 200
        assert report_response.json()["video"]["youtube_video_id"] == "abcdefghijk"


@pytest.mark.asyncio
async def test_invalid_input_and_unknown_job_return_contract_errors(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'jobs.db'}"))
    Base.metadata.create_all(app.state.engine)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        invalid = await client.post("/api/analysis-jobs", json={"input_value": "not-a-valid-video-id"})
        missing = await client.get("/api/analysis-jobs/00000000-0000-0000-0000-000000000000")

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_INPUT"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_required_step_failure_stops_downstream_pipeline(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'jobs.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        job = AnalysisJobService(session).create_job("abcdefghijk")
        job_id = job.id

    def fail_metadata(_session, _job) -> StepResult:
        raise DomainError("VIDEO_NOT_FOUND", "영상을 찾을 수 없습니다.", status_code=404)

    handlers = build_fake_handlers()
    handlers["collect_metadata"] = fail_metadata
    assert JobWorker(app.state.session_factory, handlers=handlers).run_once()

    with app.state.session_factory() as session:
        service = AnalysisJobService(session)
        assert service.get_job(job_id).status == "failed"
        steps = {step.step_key: step for step in service.get_steps(job_id)}
        assert steps["collect_metadata"].error_code == "VIDEO_NOT_FOUND"
        assert steps["collect_comments"].status == "skipped"
        assert steps["build_report_snapshot"].status == "skipped"


def test_worker_recovers_a_stale_running_step(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'stale.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        job = AnalysisJobService(session).create_job("abcdefghijk")
        job.status = "running"
        step = next(item for item in AnalysisJobService(session).get_steps(job.id) if item.step_key == "collect_metadata")
        step.status = "running"
        step.attempt_count = 1
        step.started_at = utcnow() - timedelta(minutes=20)
        step.heartbeat_at = step.started_at
        job_id = job.id
        session.commit()

    assert JobWorker(app.state.session_factory, stale_after_seconds=900).run_once()

    with app.state.session_factory() as session:
        service = AnalysisJobService(session)
        assert service.get_job(job_id).status == "succeeded"
        steps = {step.step_key: step for step in service.get_steps(job_id)}
        assert steps["collect_metadata"].attempt_count == 2
        recovery = session.scalar(select(OperationLog).where(OperationLog.event_type == "stale_job_recovered"))
        assert recovery is not None
        assert recovery.message == "collect_metadata"


def test_worker_does_not_recover_an_active_running_step(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'active.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        job = AnalysisJobService(session).create_job("abcdefghijk")
        job.status = "running"
        step = next(item for item in AnalysisJobService(session).get_steps(job.id) if item.step_key == "collect_metadata")
        step.status = "running"
        step.started_at = step.heartbeat_at = utcnow()
        job_id = job.id
        session.commit()

    assert not JobWorker(app.state.session_factory, stale_after_seconds=900).run_once()

    with app.state.session_factory() as session:
        assert AnalysisJobService(session).get_job(job_id).status == "running"
