from collections.abc import Iterator

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.admin import build_admin_router
from app.api.auth import build_auth_router
from app.api.exports import build_exports_router
from app.api.jobs import build_jobs_router
from app.api.me import build_me_router
from app.api.reports import build_report_pages_router, build_reports_router
from app.auth.google_oauth import GoogleOAuthProvider
from app.auth.services import ApiKeyValidator
from app.core.config import Settings, load_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory


DEFAULT_CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:"
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' https: data:; connect-src 'self'"
)
DOCS_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}


def create_app(
    settings: Settings | None = None,
    oauth_provider: GoogleOAuthProvider | None = None,
    api_key_validator: ApiKeyValidator | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    docs_enabled = settings.api_docs_enabled and settings.app_env != "production"

    app = FastAPI(
        title="YouTube Hate Speech Report",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.state.get_session = get_session
    app.include_router(build_auth_router(get_session, settings, oauth_provider, api_key_validator))
    app.include_router(build_me_router(get_session, settings))
    app.include_router(build_jobs_router(get_session, settings))
    app.include_router(build_reports_router(get_session, settings))
    app.include_router(build_report_pages_router(get_session, settings))
    app.include_router(build_exports_router(get_session, settings))
    app.include_router(build_admin_router(get_session, settings))

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}},
        )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = DOCS_CSP if request.url.path in DOCS_PATHS else DEFAULT_CSP
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/readiness")
    def readiness(session: Session = Depends(get_session)) -> dict:
        session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "checks": {
                "database": "ok",
                "youtube_api_key": "configured" if settings.youtube_api_key else "not_configured",
                "llm_api_key": "configured" if settings.llm_api_key else "not_configured",
            },
        }

    return app


app = create_app()
