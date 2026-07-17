import signal
import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import BoundedSemaphore, Event
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.analysis.embeddings import create_embedding_function
from app.analysis.executor import RagRuntime, RuntimeMetrics
from app.analysis.llm_client import AnthropicLlmClient
from app.analysis.observability import LangfuseConfig, build_observability_client
from app.analysis.prompt_template import PROMPT_VERSION
from app.analysis.rag_classifier import DEFAULT_EXAMPLE_MIN_SIMILARITY, RagClassifier
from app.analysis.result_store import AnalysisResultStore
from app.analysis.retry import RetryPolicy
from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION, TAXONOMY_VERSION
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME
from app.auth.crypto import KeyEncryptionService
from app.auth.services import decrypt_api_keys_for_job
from app.collectors.comments import CommentCollector
from app.collectors.metadata import VideoMetadataCollector
from app.collectors.transcript import PublicTranscriptProvider, TranscriptCollector
from app.core.config import Settings, load_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.db.models import AnalysisJob, UserApiKey, utcnow
from app.external.youtube import YouTubeApiClient
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.production_pipeline import build_collection_analysis_handlers
from app.jobs.orchestrator import StepHandler
from app.jobs.worker import JobWorker
from app.reporting.pipeline import build_reporting_handlers


logger = logging.getLogger(__name__)


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    session_factory = build_session_factory(build_engine(settings.database_url))
    stop_event = Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
    handlers = build_fake_handlers()
    handlers.update(build_reporting_handlers())
    handler_factory = None
    if settings.pipeline_mode == "production":
        youtube = YouTubeApiClient(settings.youtube_api_key)
        handler_factory = _build_production_handler_factory(
            settings,
            session_factory,
            stop_event,
            handlers,
            youtube,
        )
    worker = JobWorker(
        session_factory,
        handlers=handlers,
        handler_factory=handler_factory,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        stale_after_seconds=settings.worker_stale_after_seconds,
    )
    worker.run_forever(stop_event.is_set)


def _build_production_handler_factory(
    settings: Settings,
    session_factory: sessionmaker[Session],
    stop_event: Event,
    base_handlers: dict[str, StepHandler],
    youtube: YouTubeApiClient,
) -> Callable[[UUID], AbstractContextManager[dict[str, StepHandler]]]:
    result_store = AnalysisResultStore(session_factory)

    @contextmanager
    def factory(job_id: UUID) -> Iterator[dict[str, StepHandler]]:
        try:
            api_keys, user_id = _api_keys_for_job(settings, session_factory, job_id)
            runtime = _build_runtime(settings, stop_event, api_keys)
        except DomainError as exc:
            yield _setup_failure_handlers(base_handlers, exc)
            return
        except Exception:
            logger.exception("failed to initialize job RAG runtime", extra={"job_id": str(job_id)})
            yield _setup_failure_handlers(
                base_handlers,
                DomainError("RAG_RUNTIME_INIT_ERROR", "RAG 실행 환경을 초기화할 수 없습니다."),
            )
            return
        handlers = dict(base_handlers)
        handlers.update(
            build_collection_analysis_handlers(
                VideoMetadataCollector(youtube),
                CommentCollector(youtube),
                TranscriptCollector(PublicTranscriptProvider()),
                CommentAnalyzer(runtime, result_store),
                ScriptAnalyzer(runtime, result_store),
                _analysis_run_values(settings),
            )
        )
        try:
            yield handlers
        finally:
            try:
                runtime.close()
            finally:
                if user_id is not None:
                    _invalidate_rejected_keys(session_factory, user_id, runtime)

    return factory


def _setup_failure_handlers(
    base_handlers: dict[str, StepHandler],
    error: DomainError,
) -> dict[str, StepHandler]:
    def fail(_session: Session, _job: AnalysisJob):
        raise error

    handlers = dict(base_handlers)
    handlers["collect_metadata"] = fail
    return handlers


def _api_keys_for_job(
    settings: Settings,
    session_factory: sessionmaker[Session],
    job_id: UUID,
) -> tuple[dict[str, str], UUID | None]:
    with session_factory() as session:
        job = session.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f"unknown job: {job_id}")
        if job.user_id is not None:
            if not settings.api_key_encryption_key:
                raise ValueError("API_KEY_ENCRYPTION_KEY is required for user-owned jobs")
            return (
                decrypt_api_keys_for_job(
                    session,
                    job.user_id,
                    KeyEncryptionService(settings.api_key_encryption_key),
                ),
                job.user_id,
            )
    return ({"anthropic": settings.llm_api_key or "", "upstage": settings.embedding_api_key or ""}, None)


def _invalidate_rejected_keys(
    session_factory: sessionmaker[Session],
    user_id: UUID,
    runtime: RagRuntime,
) -> None:
    providers = {
        getattr(classifier, "invalid_provider", None)
        for classifier in runtime.pool.classifiers
    } - {None}
    if not providers:
        return
    with session_factory.begin() as session:
        session.execute(
            update(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.provider.in_(providers))
            .values(is_valid=False, last_validation_error="provider rejected key", updated_at=utcnow())
        )


def _build_runtime(settings: Settings, stop_event: Event, api_keys: dict[str, str]) -> RagRuntime:
    slot_count = settings.rag_item_concurrency if settings.rag_execution_mode == "parallel" else 1
    metrics = RuntimeMetrics()
    embedding_gate = BoundedSemaphore(settings.rag_embedding_concurrency)
    llm_gate = BoundedSemaphore(settings.rag_llm_concurrency)
    retry_policy = RetryPolicy(max_attempts=settings.rag_item_max_attempts)
    return RagRuntime(
        [
            _build_classifier(
                settings,
                stop_event,
                embedding_gate,
                llm_gate,
                retry_policy,
                metrics,
                api_keys["anthropic"],
                api_keys["upstage"],
            )
            for _index in range(slot_count)
        ],
        mode=settings.rag_execution_mode,
        item_concurrency=settings.rag_item_concurrency,
        heartbeat_interval_seconds=settings.rag_heartbeat_interval_seconds,
        shutdown_grace_seconds=settings.rag_shutdown_grace_seconds,
        stop_event=stop_event,
        metrics=metrics,
    )


def _analysis_run_values(settings: Settings) -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "example_vector_collection": EXAMPLE_COLLECTION_NAME,
        "definition_vector_collection": DEFINITION_COLLECTION_NAME,
        "definition_corpus_version": DEFAULT_DEFINITION_CORPUS_VERSION,
        "retriever_config": {
            "taxonomy_k": 4,
            "definition_k": 4,
            "example_k": 6,
            "example_min_similarity": DEFAULT_EXAMPLE_MIN_SIMILARITY,
            "taxonomy_version": TAXONOMY_VERSION,
            "execution_mode": settings.rag_execution_mode,
            "item_concurrency": settings.rag_item_concurrency,
        },
        "prompt_versions": {"comment": PROMPT_VERSION, "script": PROMPT_VERSION},
    }


def _build_classifier(
    settings: Settings,
    stop_event: Event,
    embedding_gate: BoundedSemaphore,
    llm_gate: BoundedSemaphore,
    retry_policy: RetryPolicy,
    metrics: RuntimeMetrics,
    llm_api_key: str,
    embedding_api_key: str,
) -> RagClassifier:
    return RagClassifier(
        settings.chroma_persist_directory,
        AnthropicLlmClient(
            llm_api_key,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            timeout=settings.rag_request_timeout_seconds,
            gate=llm_gate,
            retry_policy=retry_policy,
            on_retry=lambda _exc, _attempt, _delay: metrics.increment_retry("llm"),
            should_stop=stop_event.is_set,
        ),
        embedding_function=create_embedding_function(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=embedding_api_key,
            base_url=settings.upstage_embedding_base_url,
            timeout=settings.rag_request_timeout_seconds,
            gate=embedding_gate,
            retry_policy=retry_policy,
            on_retry=lambda _exc, _attempt, _delay: metrics.increment_retry("embedding"),
            should_stop=stop_event.is_set,
        ),
        observability=build_observability_client(
            LangfuseConfig(
                enabled=settings.langfuse_enabled,
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                capture_io=settings.langfuse_capture_io,
            )
        ),
        should_stop=stop_event.is_set,
    )


if __name__ == "__main__":
    main()
