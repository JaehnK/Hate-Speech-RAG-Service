from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from typing import Literal
from uuid import UUID


SourceType = Literal["comment", "reply", "script_segment"]


@dataclass(frozen=True)
class DefinitionDocument:
    doc_id: str
    source_id: str
    source_title: str
    source_url: str | None
    publisher: str
    document_type: str
    language: str
    normalized_language: str
    license_tier: str
    retrieval_tags: tuple[str, ...]
    related_categories: tuple[str, ...]
    chunk_text: str
    chunk_hash: str
    corpus_version: str


@dataclass(frozen=True)
class ExampleDocument:
    doc_id: str
    text: str
    source_dataset: str
    source_split: str
    source_revision: str | None
    license_tier: str
    mapped_categories: tuple[str, ...]
    is_hate_speech: bool
    raw_labels: dict[str, Any] = field(default_factory=dict)
    target_labels: tuple[str, ...] = ()
    hate_type_labels: tuple[str, ...] = ()
    text_hash: str = ""
    score: float | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DefinitionSearchResult:
    doc_id: str
    chunk_text: str
    source_id: str
    source_title: str
    retrieval_tags: tuple[str, ...]
    related_categories: tuple[str, ...]
    distance: float | None


@dataclass(frozen=True)
class ExampleSearchResult:
    doc_id: str
    text: str
    source_dataset: str
    source_split: str
    license_tier: str
    mapped_categories: tuple[str, ...]
    is_hate_speech: bool
    distance: float | None


@dataclass(frozen=True)
class RetrievalBundle:
    definitions: tuple[DefinitionSearchResult, ...]
    examples: tuple[ExampleSearchResult, ...]
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisItem:
    source_id: UUID
    source_type: SourceType
    text: str


@dataclass(frozen=True)
class AnalysisOutcome:
    source_id: UUID
    status: Literal["succeeded", "failed"]
    result_values: dict[str, Any]


@dataclass(frozen=True)
class StepAttemptContext:
    job_id: UUID
    step_id: UUID
    step_key: str
    run_id: UUID
    expected_attempt: int
