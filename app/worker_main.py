from app.core.config import load_settings
from app.db.session import build_engine, build_session_factory
from app.jobs.worker import JobWorker


def main() -> None:
    settings = load_settings()
    worker = JobWorker(
        build_session_factory(build_engine(settings.database_url)),
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )
    worker.run_forever()


if __name__ == "__main__":
    main()
