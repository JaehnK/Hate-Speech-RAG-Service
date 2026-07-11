import httpx
import pytest

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import Base
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
