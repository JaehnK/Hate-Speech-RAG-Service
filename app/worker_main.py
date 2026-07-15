from app.analysis.embeddings import create_embedding_function
from app.analysis.llm_client import AnthropicLlmClient
from app.analysis.observability import LangfuseConfig, build_observability_client
from app.analysis.prompt_template import PROMPT_VERSION
from app.analysis.rag_classifier import DEFAULT_EXAMPLE_MIN_SIMILARITY, RagClassifier
from app.analysis.result_store import AnalysisResultStore
from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME
from app.collectors.comments import CommentCollector
from app.collectors.metadata import VideoMetadataCollector
from app.collectors.transcript import PublicTranscriptProvider, TranscriptCollector
from app.core.config import load_settings
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.external.youtube import YouTubeApiClient
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.production_pipeline import build_collection_analysis_handlers
from app.jobs.worker import JobWorker
from app.reporting.pipeline import build_reporting_handlers


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    session_factory = build_session_factory(build_engine(settings.database_url))
    handlers = build_fake_handlers()
    handlers.update(build_reporting_handlers())
    classifier = None
    if settings.pipeline_mode == "production":
        youtube = YouTubeApiClient(settings.youtube_api_key)
        classifier = RagClassifier(
            settings.chroma_persist_directory,
            AnthropicLlmClient(
                settings.llm_api_key,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            ),
            embedding_function=create_embedding_function(
                provider=settings.embedding_provider,
                model=settings.embedding_model,
                api_key=settings.embedding_api_key,
                base_url=settings.upstage_embedding_base_url,
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
        )
        result_store = AnalysisResultStore(session_factory)
        handlers.update(
            build_collection_analysis_handlers(
                VideoMetadataCollector(youtube),
                CommentCollector(youtube),
                TranscriptCollector(PublicTranscriptProvider()),
                CommentAnalyzer(classifier, result_store),
                ScriptAnalyzer(classifier, result_store),
                {
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
                    },
                    "prompt_versions": {"comment": PROMPT_VERSION, "script": PROMPT_VERSION},
                },
            )
        )
    try:
        worker = JobWorker(
            session_factory,
            handlers=handlers,
            poll_interval_seconds=settings.worker_poll_interval_seconds,
            stale_after_seconds=settings.worker_stale_after_seconds,
        )
        worker.run_forever()
    finally:
        if classifier is not None:
            classifier.close()


if __name__ == "__main__":
    main()
