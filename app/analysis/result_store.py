from __future__ import annotations

from typing import Literal
from uuid import uuid4

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker

from app.analysis.models import AnalysisItem, AnalysisOutcome, StepAttemptContext
from app.db.models import (
    CommentAnalysisResult,
    CommentSnapshot,
    JobStep,
    ScriptAnalysisResult,
    TranscriptSegment,
    TranscriptSnapshot,
    utcnow,
)
from app.jobs.exceptions import StaleStepExecution


ResultKind = Literal["comment", "script"]


class AnalysisResultStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def load_comment_items(self, context: StepAttemptContext) -> tuple[int, list[AnalysisItem]]:
        with self.session_factory() as session:
            total = session.scalar(
                select(func.count()).select_from(CommentSnapshot).where(CommentSnapshot.job_id == context.job_id)
            ) or 0
            statement = (
                select(CommentSnapshot.id, CommentSnapshot.text_original, CommentSnapshot.text_display, CommentSnapshot.is_reply)
                .outerjoin(
                    CommentAnalysisResult,
                    and_(
                        CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id,
                        CommentAnalysisResult.analysis_run_id == context.run_id,
                    ),
                )
                .where(CommentSnapshot.job_id == context.job_id, CommentAnalysisResult.id.is_(None))
                .order_by(CommentSnapshot.collected_at, CommentSnapshot.id)
            )
            items = [
                AnalysisItem(
                    source_id=row.id,
                    source_type="reply" if row.is_reply else "comment",
                    text=row.text_original or row.text_display or "",
                )
                for row in session.execute(statement)
            ]
        return total, items

    def load_script_items(self, context: StepAttemptContext) -> tuple[int, list[AnalysisItem]]:
        source = (
            select(TranscriptSegment)
            .join(TranscriptSnapshot, TranscriptSegment.transcript_snapshot_id == TranscriptSnapshot.id)
            .where(TranscriptSnapshot.job_id == context.job_id)
            .subquery()
        )
        with self.session_factory() as session:
            total = session.scalar(select(func.count()).select_from(source)) or 0
            statement = (
                select(source.c.id, source.c.text)
                .outerjoin(
                    ScriptAnalysisResult,
                    and_(
                        ScriptAnalysisResult.transcript_segment_id == source.c.id,
                        ScriptAnalysisResult.analysis_run_id == context.run_id,
                    ),
                )
                .where(ScriptAnalysisResult.id.is_(None))
                .order_by(source.c.segment_index)
            )
            items = [
                AnalysisItem(source_id=row.id, source_type="script_segment", text=row.text)
                for row in session.execute(statement)
            ]
        return total, items

    def persist(self, context: StepAttemptContext, kind: ResultKind, outcome: AnalysisOutcome) -> bool:
        model, source_column = _result_target(kind)
        with self.session_factory.begin() as session:
            _fence(session, context)
            values = {
                "id": uuid4(),
                "analysis_run_id": context.run_id,
                source_column.name: outcome.source_id,
                "status": outcome.status,
                "created_at": utcnow(),
                **outcome.result_values,
            }
            statement = _insert_for(session, model.__table__).values(**values).on_conflict_do_nothing(
                index_elements=["analysis_run_id", source_column.name]
            ).returning(model.id)
            inserted = session.scalar(statement) is not None
            if inserted:
                progress_values = {
                    "items_completed": func.coalesce(JobStep.items_completed, 0) + 1,
                    "heartbeat_at": utcnow(),
                }
                counter = JobStep.items_succeeded if outcome.status == "succeeded" else JobStep.items_failed
                progress_values[counter.key] = func.coalesce(counter, 0) + 1
                session.execute(update(JobStep).where(JobStep.id == context.step_id).values(**progress_values))
        return inserted

    def reconcile(self, context: StepAttemptContext, kind: ResultKind, total: int) -> dict[str, int]:
        model, _source_column = _result_target(kind)
        with self.session_factory.begin() as session:
            rows = dict(
                session.execute(
                    select(model.status, func.count())
                    .where(model.analysis_run_id == context.run_id)
                    .group_by(model.status)
                ).all()
            )
            succeeded = int(rows.get("succeeded", 0))
            failed = int(rows.get("failed", 0))
            statement = (
                update(JobStep)
                .where(
                    JobStep.id == context.step_id,
                    JobStep.status == "running",
                    JobStep.attempt_count == context.expected_attempt,
                )
                .values(
                    items_total=total,
                    items_completed=succeeded + failed,
                    items_succeeded=succeeded,
                    items_failed=failed,
                    heartbeat_at=utcnow(),
                )
                .returning(JobStep.id)
            )
            if session.scalar(statement) is None:
                raise StaleStepExecution(context.step_key)
        return {"total": total, "succeeded": succeeded, "failed": failed}

    def heartbeat(self, context: StepAttemptContext) -> None:
        with self.session_factory.begin() as session:
            _fence(session, context)


def _fence(session: Session, context: StepAttemptContext) -> None:
    statement = (
        update(JobStep)
        .where(
            JobStep.id == context.step_id,
            JobStep.status == "running",
            JobStep.attempt_count == context.expected_attempt,
        )
        .values(heartbeat_at=utcnow())
        .returning(JobStep.id)
    )
    if session.scalar(statement) is None:
        raise StaleStepExecution(context.step_key)


def _result_target(kind: ResultKind):
    if kind == "comment":
        return CommentAnalysisResult, CommentAnalysisResult.comment_snapshot_id
    return ScriptAnalysisResult, ScriptAnalysisResult.transcript_segment_id


def _insert_for(session: Session, table):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql.insert(table)
    if dialect == "sqlite":
        return sqlite.insert(table)
    raise RuntimeError(f"unsupported database dialect: {dialect}")
