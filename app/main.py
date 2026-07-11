from collections.abc import Iterator

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.api.jobs import build_jobs_router
from app.api.reports import build_reports_router
from app.core.config import Settings, load_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    app = FastAPI(title="YouTube Hate Speech Report", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.state.get_session = get_session
    app.include_router(build_jobs_router(get_session))
    app.include_router(build_reports_router(get_session))

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/readiness")
    def readiness(session: Session = Depends(get_session)) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ready"}

    return app


app = create_app()
