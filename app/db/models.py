from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")
TEXT_LIST = JSON().with_variant(ARRAY(Text()), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    google_sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_api_keys_user_provider"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary)
    key_fingerprint: Mapped[str] = mapped_column(String(64))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        Index("ix_analysis_jobs_status_created_at", "status", "created_at"),
        Index("ix_analysis_jobs_video_created_at", "youtube_video_id", "created_at"),
        Index("ix_analysis_jobs_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    input_value: Mapped[str] = mapped_column(Text)
    youtube_video_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    requested_by: Mapped[str | None] = mapped_column(String(255))
    request_options: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "step_key", name="uq_job_steps_job_step"),
        Index("ix_job_steps_status_started_at", "status", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    items_total: Mapped[int | None] = mapped_column(Integer)
    items_completed: Mapped[int] = mapped_column(Integer, default=0)
    items_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Channel(Base):
    __tablename__ = "channels"

    youtube_channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    custom_url: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    last_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VideoMetadataSnapshot(Base):
    __tablename__ = "video_metadata_snapshots"
    __table_args__ = (Index("ix_video_metadata_video_collected", "youtube_video_id", "collected_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32))
    youtube_channel_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    channel_title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category_id: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    made_for_kids: Mapped[bool | None] = mapped_column(Boolean)
    tags: Mapped[list[str] | None] = mapped_column(TEXT_LIST)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommentSnapshot(Base):
    __tablename__ = "comment_snapshots"
    __table_args__ = (
        UniqueConstraint("job_id", "youtube_comment_id", name="uq_comments_job_youtube_id"),
        Index("ix_comments_job_reply", "job_id", "is_reply"),
        Index("ix_comments_job_parent", "job_id", "parent_youtube_comment_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), index=True)
    youtube_comment_id: Mapped[str] = mapped_column(String(128))
    parent_youtube_comment_id: Mapped[str | None] = mapped_column(String(128))
    parent_comment_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("comment_snapshots.id"))
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_depth: Mapped[int] = mapped_column(Integer, default=0)
    author_display_name: Mapped[str | None] = mapped_column(Text)
    author_channel_id: Mapped[str | None] = mapped_column(String(128), index=True)
    text_display: Mapped[str | None] = mapped_column(Text)
    text_original: Mapped[str | None] = mapped_column(Text)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    reply_count: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranscriptSnapshot(Base):
    __tablename__ = "transcript_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), index=True)
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_auto_generated: Mapped[bool | None] = mapped_column(Boolean)
    source_type: Mapped[str] = mapped_column(String(32), default="public_caption")
    source_uri: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("transcript_snapshot_id", "segment_index", name="uq_segments_snapshot_index"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    transcript_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("transcript_snapshots.id", ondelete="CASCADE"), index=True)
    segment_index: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[Decimal | None] = mapped_column(Numeric)
    end_seconds: Mapped[Decimal | None] = mapped_column(Numeric)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32))
    llm_provider: Mapped[str] = mapped_column(String(64))
    llm_model: Mapped[str] = mapped_column(String(128))
    embedding_provider: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(128))
    example_vector_collection: Mapped[str] = mapped_column(String(128))
    definition_vector_collection: Mapped[str] = mapped_column(String(128))
    definition_corpus_version: Mapped[str | None] = mapped_column(String(128))
    retriever_config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisResultMixin:
    status: Mapped[str] = mapped_column(String(32))
    is_hate_speech: Mapped[bool | None] = mapped_column(Boolean)
    categories: Mapped[list[str] | None] = mapped_column(TEXT_LIST)
    target_group: Mapped[str | None] = mapped_column(Text)
    hate_type: Mapped[str | None] = mapped_column(Text)
    evidence_strength: Mapped[Decimal | None] = mapped_column(Numeric)
    reasoning: Mapped[str | None] = mapped_column(Text)
    similar_cases_used: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON_VALUE)
    definition_docs_used: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON_VALUE)
    rag_context_status: Mapped[str | None] = mapped_column(String(32))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommentAnalysisResult(AnalysisResultMixin, Base):
    __tablename__ = "comment_analysis_results"
    __table_args__ = (UniqueConstraint("analysis_run_id", "comment_snapshot_id", name="uq_comment_results_run_comment"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    comment_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("comment_snapshots.id", ondelete="CASCADE"), index=True)


class ScriptAnalysisResult(AnalysisResultMixin, Base):
    __tablename__ = "script_analysis_results"
    __table_args__ = (UniqueConstraint("analysis_run_id", "transcript_segment_id", name="uq_script_results_run_segment"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    transcript_segment_id: Mapped[UUID] = mapped_column(ForeignKey("transcript_segments.id", ondelete="CASCADE"), index=True)


class CommentNetwork(Base):
    __tablename__ = "comment_networks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    graph_type: Mapped[str] = mapped_column(String(64), default="comment_reply_author_network")
    directed: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    layout_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommentNetworkNode(Base):
    __tablename__ = "comment_network_nodes"
    __table_args__ = (UniqueConstraint("network_id", "node_key", name="uq_network_nodes_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("comment_networks.id", ondelete="CASCADE"), index=True)
    node_key: Mapped[str] = mapped_column(String(160))
    node_type: Mapped[str] = mapped_column(String(32), default="author")
    label: Mapped[str | None] = mapped_column(Text)
    author_channel_id: Mapped[str | None] = mapped_column(String(128), index=True)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    hate_speech_count: Mapped[int] = mapped_column(Integer, default=0)
    hate_speech_ratio: Mapped[Decimal] = mapped_column(Numeric, default=0)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class CommentNetworkEdge(Base):
    __tablename__ = "comment_network_edges"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("comment_networks.id", ondelete="CASCADE"), index=True)
    source_node_key: Mapped[str] = mapped_column(String(160), index=True)
    target_node_key: Mapped[str] = mapped_column(String(160), index=True)
    edge_type: Mapped[str] = mapped_column(String(32), default="reply_to")
    weight: Mapped[Decimal] = mapped_column(Numeric, default=1)
    comment_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("comment_snapshots.id"))
    parent_comment_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("comment_snapshots.id"))
    is_hate_speech: Mapped[bool | None] = mapped_column(Boolean)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_public_sample: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    payload_uri: Mapped[str | None] = mapped_column(Text)
    html_uri: Mapped[str | None] = mapped_column(Text)
    source_counts: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    failure_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("report_snapshots.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    file_uri: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(128))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"), index=True)
    job_step_id: Mapped[UUID | None] = mapped_column(ForeignKey("job_steps.id"))
    analysis_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_runs.id"))
    level: Mapped[str] = mapped_column(String(16), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecretReference(Base):
    __tablename__ = "secret_references"
    __table_args__ = (UniqueConstraint("secret_key", "provider", name="uq_secret_references_key_provider"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    secret_key: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ApiQuotaEvent(Base):
    __tablename__ = "api_quota_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    quota_cost: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
