from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

from app.analysis.llm_client import LlmClient, LlmResponse
from app.analysis.models import DefinitionDocument, DefinitionSearchResult
from app.analysis.models import ExampleDocument, ExampleSearchResult, SourceType
from app.analysis.models import ValidationResult
from app.analysis.observability import NoopObservabilityClient, ObservabilityClient
from app.analysis.prompt_template import PROMPT_VERSION, build_category_prompt
from app.analysis.prompt_validator import validate_classification_output
from app.analysis.retriever import DualVectorRetriever
from app.analysis.retry import RetryCancelled
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION
from app.jobs.exceptions import WorkerShutdownRequested


DEFAULT_EXAMPLE_MIN_SIMILARITY = 0.4


@dataclass(frozen=True)
class ClassificationResult:
    payload: dict[str, Any]
    prompt_version: str
    model: str
    usage: dict[str, int]
    validation: ValidationResult
    attempts: int
    rag_context_status: str
    example_collection: str
    definition_collection: str
    definition_corpus_version: str
    retrieved_examples: tuple[ExampleSearchResult, ...]
    retrieved_definitions: tuple[DefinitionSearchResult, ...]


class ClassificationError(Exception):
    pass


class RagClassifier:
    def __init__(
        self,
        persist_directory: Path | str,
        llm_client: LlmClient,
        embedding_function=None,
        observability: ObservabilityClient | None = None,
        taxonomy_k: int = 4,
        definition_k: int = 4,
        example_k: int = 6,
        example_min_similarity: float = DEFAULT_EXAMPLE_MIN_SIMILARITY,
        definition_corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
        retriever: DualVectorRetriever | None = None,
        should_stop=None,
    ) -> None:
        self.llm_client = llm_client
        self.retriever = retriever or DualVectorRetriever(persist_directory, embedding_function)
        self.observability = observability or NoopObservabilityClient()
        self.taxonomy_k = taxonomy_k
        self.definition_k = definition_k
        self.example_k = example_k
        self.example_min_similarity = example_min_similarity
        self.definition_corpus_version = definition_corpus_version
        self.should_stop = should_stop or (lambda: False)

    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult:
        if self.should_stop():
            raise WorkerShutdownRequested
        with self.observability.observation(
            "rag.retrieval",
            as_type="retriever",
            input_value=input_text,
            metadata={"source_type": source_type},
        ):
            try:
                bundle = self.retriever.retrieve(
                    _retrieval_query(input_text, source_type),
                    definition_n=self.taxonomy_k + self.definition_k,
                    example_n=self.example_k,
                )
            except RetryCancelled as exc:
                raise WorkerShutdownRequested from exc
            except Exception as exc:
                raise ClassificationError("both RAG vector stores are unavailable") from exc
            definitions = list(bundle.definitions)
            examples = list(bundle.examples)
            examples = [
                result
                for result in examples
                if _example_similarity(result) >= self.example_min_similarity
            ]

        if len(bundle.failures) == 2:
            raise ClassificationError("both RAG vector stores are unavailable")
        context_status = _context_status(definitions, examples)

        prompt = build_category_prompt(
            input_text=input_text,
            source_type=source_type,
            taxonomy_context=[_definition_document(result) for result in definitions[: self.taxonomy_k]],
            definition_context=[_definition_document(result) for result in definitions[self.taxonomy_k :]],
            example_context=[_example_document(result) for result in examples],
        )

        last_validation = ValidationResult(valid=False, errors=("not_attempted",))
        response = LlmResponse(text="", model=self.llm_client.model, usage={})
        for attempt in range(1, 3):
            if self.should_stop():
                raise WorkerShutdownRequested
            with self.observability.observation(
                "rag.classification",
                as_type="generation",
                input_value=prompt,
                metadata={"prompt_version": PROMPT_VERSION, "attempt": attempt},
                model=self.llm_client.model,
            ):
                try:
                    response = self.llm_client.complete(prompt)
                except RetryCancelled as exc:
                    raise WorkerShutdownRequested from exc
                except Exception as exc:
                    raise ClassificationError("LLM classification request failed") from exc

            payload, validation = _validated_payload(response.text)
            last_validation = validation
            if validation.valid and payload is not None:
                return ClassificationResult(
                    payload=payload,
                    prompt_version=PROMPT_VERSION,
                    model=response.model,
                    usage=response.usage,
                    validation=validation,
                    attempts=attempt,
                    rag_context_status=context_status,
                    example_collection=EXAMPLE_COLLECTION_NAME,
                    definition_collection=DEFINITION_COLLECTION_NAME,
                    definition_corpus_version=self.definition_corpus_version,
                    retrieved_examples=tuple(examples),
                    retrieved_definitions=tuple(definitions),
                )

            prompt = _retry_prompt(prompt, validation)

        raise ClassificationError(f"LLM output failed validation: {last_validation.errors}")

    def close(self) -> None:
        self.retriever.close()
        close = getattr(self.llm_client, "close", None)
        if close is not None:
            close()
        self.observability.flush()


def _retrieval_query(input_text: str, source_type: SourceType) -> str:
    return f"{input_text}\nsource_type={source_type}"


def _validated_payload(text: str) -> tuple[dict[str, Any] | None, ValidationResult]:
    try:
        payload = json.loads(_extract_json(text))
    except json.JSONDecodeError:
        return None, ValidationResult(valid=False, errors=("json_parse_failed",))

    validation = validate_classification_output(payload)
    return payload, validation


def _extract_json(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _retry_prompt(prompt: str, validation: ValidationResult) -> str:
    return "\n".join(
        [
            prompt,
            "",
            "Previous output failed validation.",
            f"Validation errors: {', '.join(validation.errors)}",
            "Return corrected valid JSON only.",
        ]
    )


def _definition_document(result: DefinitionSearchResult) -> DefinitionDocument:
    return DefinitionDocument(
        doc_id=result.doc_id,
        source_id=result.source_id,
        source_title=result.source_title,
        source_url=None,
        publisher="",
        document_type="retrieved_definition",
        language="ko",
        normalized_language="ko",
        license_tier="",
        retrieval_tags=result.retrieval_tags,
        related_categories=result.related_categories,
        chunk_text=result.chunk_text,
        chunk_hash="",
        corpus_version="",
    )


def _example_document(result: ExampleSearchResult) -> ExampleDocument:
    score = None if result.distance is None else 1 - result.distance
    return ExampleDocument(
        doc_id=result.doc_id,
        text=result.text,
        source_dataset=result.source_dataset,
        source_split=result.source_split,
        source_revision=None,
        license_tier=result.license_tier,
        mapped_categories=result.mapped_categories,
        is_hate_speech=result.is_hate_speech,
        score=score,
    )


def _context_status(definitions: list[DefinitionSearchResult], examples: list[ExampleSearchResult]) -> str:
    if definitions and examples:
        return "complete"
    if examples:
        return "example_only"
    if definitions:
        return "definition_only"
    return "unavailable"


def _example_similarity(result: ExampleSearchResult) -> float:
    return float("-inf") if result.distance is None else 1 - result.distance
