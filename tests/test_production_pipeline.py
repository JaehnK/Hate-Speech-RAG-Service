from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

from app.analysis.services import CommentAnalyzer, ScriptAnalyzer
from app.collectors.comments import CommentCollector
from app.collectors.metadata import VideoMetadataCollector
from app.collectors.transcript import TranscriptCollector, TranscriptData, TranscriptItem
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import Base
from app.db.models import ApiQuotaEvent, CommentAnalysisResult, CommentSnapshot, ScriptAnalysisResult, TranscriptSegment, VideoMetadataSnapshot
from app.external.youtube import CommentRecord
from app.jobs.fake_pipeline import build_fake_handlers
from app.jobs.production_pipeline import build_collection_analysis_handlers
from app.jobs.service import AnalysisJobService
from app.jobs.worker import JobWorker
from app.main import create_app
from app.reporting.pipeline import build_reporting_handlers


class FakeYouTubeClient:
    def get_video(self, video_id):
        return {
            "id": video_id,
            "snippet": {"title": "Real adapter video", "channelTitle": "Channel"},
            "contentDetails": {"duration": "PT1M"},
            "statistics": {"commentCount": "1"},
            "status": {},
        }

    def iter_comments(self, _video_id):
        yield CommentRecord(
            youtube_comment_id="c1",
            parent_youtube_comment_id=None,
            author_display_name="Author",
            author_channel_id="author1",
            text_display="normal comment",
            text_original="normal comment",
            like_count=0,
            reply_count=0,
            published_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            raw_payload={},
        )


class FakeTranscriptProvider:
    def fetch(self, _video_id):
        return TranscriptData("ko", False, (TranscriptItem("normal script", 0, 5),))


class FakeClassifier:
    def classify_text(self, text, _source_type):
        return SimpleNamespace(
            payload={
                "input_text": text,
                "is_hate_speech": False,
                "categories": ["unclassified"],
                "target_group": None,
                "hate_type": None,
                "reasoning": "clean",
                "similar_cases_used": [],
                "definition_docs_used": [],
            },
            rag_context_status="complete",
            prompt_version="test-v1",
            model="fake-classifier",
        )


class PartiallyFailingYouTubeClient(FakeYouTubeClient):
    def iter_comments(self, video_id):
        yield from super().iter_comments(video_id)
        raise DomainError("YOUTUBE_QUOTA_EXCEEDED", "quota exceeded", retryable=True)


def test_real_adapter_pipeline_persists_collection_and_analysis_artifacts(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'production.db'}"))
    Base.metadata.create_all(app.state.engine)
    handlers = _handlers(FakeYouTubeClient())

    with app.state.session_factory() as session:
        job_id = AnalysisJobService(session).create_job("abcdefghijk").id
    assert JobWorker(app.state.session_factory, handlers=handlers).run_once()

    with app.state.session_factory() as session:
        assert AnalysisJobService(session).get_job(job_id).status == "succeeded"
        for model in (VideoMetadataSnapshot, CommentSnapshot, TranscriptSegment, CommentAnalysisResult, ScriptAnalysisResult):
            assert session.scalar(select(func.count()).select_from(model)) == 1
        assert session.scalar(select(func.count()).select_from(ApiQuotaEvent)) == 2


def test_incomplete_comment_collection_is_preserved_but_not_analyzed(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'partial.db'}"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        job_id = AnalysisJobService(session).create_job("abcdefghijk").id

    assert JobWorker(app.state.session_factory, handlers=_handlers(PartiallyFailingYouTubeClient())).run_once()

    with app.state.session_factory() as session:
        service = AnalysisJobService(session)
        assert service.get_job(job_id).status == "partial_success"
        steps = {step.step_key: step for step in service.get_steps(job_id)}
        assert steps["collect_comments"].error_code == "YOUTUBE_QUOTA_EXCEEDED"
        assert steps["analyze_comments"].error_code == "COMMENT_COLLECTION_INCOMPLETE"
        assert session.scalar(select(func.count()).select_from(CommentSnapshot)) == 1
        assert session.scalar(select(func.count()).select_from(CommentAnalysisResult)) == 0


def _handlers(youtube):
    classifier = FakeClassifier()
    handlers = build_fake_handlers()
    handlers.update(
        build_collection_analysis_handlers(
            VideoMetadataCollector(youtube),
            CommentCollector(youtube),
            TranscriptCollector(FakeTranscriptProvider()),
            CommentAnalyzer(classifier),
            ScriptAnalyzer(classifier),
            {
                "llm_provider": "fake-test",
                "llm_model": "fake-test",
                "embedding_provider": "hash",
                "embedding_model": "hash",
                "example_vector_collection": "examples",
                "definition_vector_collection": "definitions",
                "definition_corpus_version": "test-v1",
                "retriever_config": {},
                "prompt_versions": {},
            },
        )
    )
    handlers.update(build_reporting_handlers())
    return handlers
