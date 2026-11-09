"""Optional Jev pre-filter in front of the RAG classifier (JEV_PREFILTER_ENABLED).

Items Jev scores as confidently non-hateful skip retrieval and the LLM. The gate only
ever turns an item into "not hate"; it never labels anything as hate, and any Jev
failure falls back to RAG, so the gate can never fail an item.

The threshold was validated on public benchmarks and a YouTube sample (docs/47). The
measured residual miss rate (1 of 174 filtered YouTube comments) is accepted rather
than patched with ad-hoc rules; filtered items are labelled as such in reports.
"""

from __future__ import annotations

import logging

from app.analysis.jev_client import JEV_QUESTION_VERSION, JevClient
from app.analysis.models import SourceType, ValidationResult
from app.analysis.rag_classifier import ClassificationResult
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION
from app.analysis.vector_store import AUTHORITATIVE_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME

logger = logging.getLogger(__name__)

JEV_FILTERED_STATUS = "jev_filtered"
DEFAULT_JEV_THRESHOLD = 0.07


class JevGatedClassifier:
    def __init__(self, inner, jev_client: JevClient, threshold: float = DEFAULT_JEV_THRESHOLD) -> None:
        self.inner = inner
        self.jev_client = jev_client
        self.threshold = threshold

    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult:
        try:
            score = self.jev_client.score(input_text)
        except Exception as exc:
            logger.warning("jev prefilter failed, falling back to RAG: %s", type(exc).__name__)
            return self.inner.classify_text(input_text, source_type)
        if score.p_hate >= self.threshold:
            return self.inner.classify_text(input_text, source_type)
        return _filtered_result(score.p_hate, score.model, self.threshold)

    def __getattr__(self, name: str):
        # Worker code reads attributes such as invalid_provider from the classifier.
        return getattr(self.inner, name)

    def close(self) -> None:
        self.inner.close()
        self.jev_client.close()  # shared across slots; httpx close is idempotent


def _filtered_result(p_hate: float, model: str, threshold: float) -> ClassificationResult:
    return ClassificationResult(
        payload={
            "is_hate_speech": False,
            "categories": ["unclassified"],
            "target_group": None,
            "hate_type": None,
            "reasoning": (
                f"Jev 사전 필터: 혐오 확률 {p_hate:.2f}가 기준 {threshold:.2f} 미만이라 "
                "LLM 분류 없이 혐오 아님으로 판정했습니다."
            ),
            "similar_cases_used": [],
            "definition_docs_used": [],
            "jev_p_hate": p_hate,
        },
        prompt_version=JEV_QUESTION_VERSION,
        model=model,
        usage={},
        validation=ValidationResult(valid=True, errors=()),
        attempts=1,
        rag_context_status=JEV_FILTERED_STATUS,
        example_collection=EXAMPLE_COLLECTION_NAME,
        definition_collection=AUTHORITATIVE_COLLECTION_NAME,
        definition_corpus_version=DEFAULT_DEFINITION_CORPUS_VERSION,
        retrieved_examples=(),
        retrieved_definitions=(),
    )
