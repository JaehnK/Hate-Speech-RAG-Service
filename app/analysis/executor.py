from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from queue import Queue
from threading import Event
from typing import Protocol

from app.analysis.models import AnalysisItem, AnalysisOutcome, SourceType
from app.analysis.rag_classifier import ClassificationError, ClassificationResult
from app.jobs.exceptions import WorkerShutdownRequested


class Classifier(Protocol):
    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult: ...


class ClassifierPool:
    def __init__(self, classifiers: list[Classifier]) -> None:
        if not classifiers:
            raise ValueError("at least one classifier is required")
        self.classifiers = classifiers
        self.available: Queue[Classifier] = Queue()
        for classifier in classifiers:
            self.available.put(classifier)

    def classify(self, item: AnalysisItem) -> AnalysisOutcome:
        classifier = self.available.get()
        try:
            return _classify(classifier, item)
        finally:
            self.available.put(classifier)

    def close(self) -> None:
        for classifier in self.classifiers:
            close = getattr(classifier, "close", None)
            if close is not None:
                close()


class RagRuntime:
    def __init__(
        self,
        classifiers: list[Classifier],
        *,
        mode: str = "sequential",
        item_concurrency: int = 1,
        heartbeat_interval_seconds: float = 30,
        stop_event: Event | None = None,
    ) -> None:
        if mode not in {"sequential", "parallel"}:
            raise ValueError(f"unsupported RAG execution mode: {mode}")
        if item_concurrency < 1:
            raise ValueError("item concurrency must be positive")
        self.pool = ClassifierPool(classifiers)
        self.mode = mode
        self.item_concurrency = item_concurrency
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.stop_event = stop_event or Event()

    def run(
        self,
        items: Iterable[AnalysisItem],
        persist: Callable[[AnalysisOutcome], None],
        heartbeat: Callable[[], None],
    ) -> None:
        if self.mode == "sequential":
            for item in items:
                if self.stop_event.is_set():
                    raise WorkerShutdownRequested
                persist(self.pool.classify(item))
            return

        iterator = iter(items)
        executor = ThreadPoolExecutor(max_workers=self.item_concurrency, thread_name_prefix="rag-item")
        in_flight: set[Future[AnalysisOutcome]] = set()
        shutdown_requested = False
        try:
            if self.stop_event.is_set():
                raise WorkerShutdownRequested
            for _index in range(self.item_concurrency):
                if not _submit_one(executor, iterator, in_flight, self.pool.classify):
                    break

            while in_flight:
                if self.stop_event.is_set():
                    shutdown_requested = True
                done, _pending = wait(
                    in_flight,
                    timeout=self.heartbeat_interval_seconds,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    heartbeat()
                    continue
                if self.stop_event.is_set():
                    shutdown_requested = True
                for future in done:
                    in_flight.remove(future)
                    persist(future.result())
                    if self.stop_event.is_set():
                        shutdown_requested = True
                    if not shutdown_requested:
                        _submit_one(executor, iterator, in_flight, self.pool.classify)
            if shutdown_requested:
                raise WorkerShutdownRequested
        except BaseException:
            for future in in_flight:
                future.cancel()
            raise
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    def close(self) -> None:
        self.pool.close()


def _submit_one(
    executor: ThreadPoolExecutor,
    items,
    in_flight: set[Future[AnalysisOutcome]],
    classify: Callable[[AnalysisItem], AnalysisOutcome],
) -> bool:
    try:
        item = next(items)
    except StopIteration:
        return False
    in_flight.add(executor.submit(classify, item))
    return True


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
