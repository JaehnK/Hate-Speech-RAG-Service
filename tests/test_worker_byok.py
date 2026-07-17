from types import SimpleNamespace

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import Base
from app.db.models import User, UserApiKey
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.service import AnalysisJobService
from app.jobs.worker import JobWorker
from app.main import create_app
from app.worker_main import _invalidate_rejected_keys, _setup_failure_handlers


def test_worker_runtime_setup_failure_finishes_job_instead_of_leaving_orphan(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'setup-failure.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        job = AnalysisJobService(session).create_job("abcdefghijk")
        job_id = job.id

    handlers = _setup_failure_handlers(
        build_fake_handlers(),
        DomainError("API_KEY_INVALID", "등록된 API 키가 유효하지 않습니다."),
    )
    assert JobWorker(app.state.session_factory, handlers=handlers).run_once()

    with app.state.session_factory() as session:
        service = AnalysisJobService(session)
        assert service.get_job(job_id).status == "failed"
        failed = next(step for step in service.get_steps(job_id) if step.step_key == "collect_metadata")
        assert failed.error_code == "API_KEY_INVALID"


def test_worker_marks_provider_key_invalid_after_runtime_rejection(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'rejected-key.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory.begin() as session:
        user = User(google_sub="google-sub", email="user@example.com")
        session.add(user)
        session.flush()
        row = UserApiKey(
            user_id=user.id,
            provider="anthropic",
            encrypted_key=b"encrypted",
            key_fingerprint="••••test",
            is_valid=True,
        )
        session.add(row)
        session.flush()
        user_id = user.id
        row_id = row.id

    runtime = SimpleNamespace(
        pool=SimpleNamespace(classifiers=[SimpleNamespace(invalid_provider="anthropic")])
    )
    _invalidate_rejected_keys(app.state.session_factory, user_id, runtime)

    with app.state.session_factory() as session:
        row = session.get(UserApiKey, row_id)
        assert row is not None
        assert not row.is_valid
        assert row.last_validation_error == "provider rejected key"
