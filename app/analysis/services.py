from __future__ import annotations

from typing import Protocol

from app.analysis.models import AnalysisItem, AnalysisOutcome, SourceType, StepAttemptContext
from app.analysis.rag_classifier import ClassificationError, ClassificationResult
from app.analysis.result_store import AnalysisResultStore


class Classifier(Protocol):
    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult: ...


class CommentAnalyzer:
    def __init__(self, classifier: Classifier, result_store: AnalysisResultStore) -> None:
        self.classifier = classifier
        self.result_store = result_store

    def analyze(self, context: StepAttemptContext) -> dict[str, int]:
        total, items = self.result_store.load_comment_items(context)
        self.result_store.reconcile(context, "comment", total)
        for item in items:
            self.result_store.persist(context, "comment", _classify(self.classifier, item))
        progress = self.result_store.reconcile(context, "comment", total)
        return {"comments_analyzed": total, "succeeded": progress["succeeded"], "failed": progress["failed"]}


class ScriptAnalyzer:
    def __init__(self, classifier: Classifier, result_store: AnalysisResultStore) -> None:
        self.classifier = classifier
        self.result_store = result_store

    def analyze(self, context: StepAttemptContext) -> dict[str, int]:
        total, items = self.result_store.load_script_items(context)
        self.result_store.reconcile(context, "script", total)
        for item in items:
            self.result_store.persist(context, "script", _classify(self.classifier, item))
        progress = self.result_store.reconcile(context, "script", total)
        return {"script_segments_analyzed": total, "succeeded": progress["succeeded"], "failed": progress["failed"]}


def _classify(classifier: Classifier, item: AnalysisItem) -> AnalysisOutcome:
    try:
        result = classifier.classify_text(item.text, item.source_type)
    except ClassificationError as exc:
        return AnalysisOutcome(
            source_id=item.source_id,
            status="failed",
            result_values={"error_code": "LLM_ERROR", "error_message": str(exc)},
        )
    payload = result.payload
    return AnalysisOutcome(
        source_id=item.source_id,
        status="succeeded",
        result_values={
            "is_hate_speech": payload["is_hate_speech"],
            "categories": payload["categories"],
            "target_group": payload.get("target_group"),
            "hate_type": payload.get("hate_type"),
            "reasoning": payload.get("reasoning"),
            "similar_cases_used": payload.get("similar_cases_used", []),
            "definition_docs_used": payload.get("definition_docs_used", []),
            "rag_context_status": result.rag_context_status,
            "prompt_version": result.prompt_version,
            "model_name": result.model,
            "raw_response": payload,
        },
    )
