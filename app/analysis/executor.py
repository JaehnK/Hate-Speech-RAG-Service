from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from queue import Queue
from threading import Event, Lock
from time import monotonic
from typing import Protocol

from app.analysis.models import AnalysisItem, AnalysisOutcome, SourceType
from app.analysis.rag_classifier import ClassificationError, ClassificationResult
from app.jobs.exceptions import WorkerShutdownRequested


class Classifier(Protocol):
    def classify_text(self, input_text: str, source_type: SourceType) -> ClassificationResult: ...


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {
            "embedding_retries": 0,
            "llm_retries": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def increment_retry(self, provider: str) -> None:
        key = "embedding_retries" if provider == "embedding" else "llm_retries"
        with self._lock:
            self._values[key] += 1

    def record_outcome(self, outcome: AnalysisOutcome) -> None:
        with self._lock:
            self._values["input_tokens"] += outcome.usage.get("input_tokens", 0)
            self._values["output_tokens"] += outcome.usage.get("output_tokens", 0)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)


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
        shutdown_grace_seconds: float = 30,
        stop_event: Event | None = None,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        if mode not in {"sequential", "parallel"}:
            raise ValueError(f"unsupported RAG execution mode: {mode}")
        if item_concurrency < 1:
            raise ValueError("item concurrency must be positive")
        self.pool = ClassifierPool(classifiers)
        self.mode = mode
        self.item_concurrency = item_concurrency
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.shutdown_grace_seconds = shutdown_grace_seconds
        self.stop_event = stop_event or Event()
        self.metrics = metrics or RuntimeMetrics()

    def run(
        self,
        items: Iterable[AnalysisItem],
        persist: Callable[[AnalysisOutcome], None],
        heartbeat: Callable[[], None],
        progress: Callable[[dict[str, int]], None] | None = None,
    ) -> None:
        started = monotonic()
        baseline = self.metrics.snapshot()
        completed = 0
        succeeded = 0
        failed = 0
        last_logged_count = 0
        last_logged_at = started

        def record(outcome: AnalysisOutcome, in_flight: int) -> None:
            nonlocal completed, succeeded, failed, last_logged_count, last_logged_at
            persist(outcome)
            self.metrics.record_outcome(outcome)
            completed += 1
            succeeded += outcome.status == "succeeded"
            failed += outcome.status == "failed"
            now = monotonic()
            if progress is not None and (completed - last_logged_count >= 10 or now - last_logged_at >= 5):
                progress(_progress_payload(
                    completed, succeeded, failed, in_flight, self.item_concurrency, started, baseline, self.metrics
                ))
                last_logged_count = completed
                last_logged_at = now

        def finish_progress() -> None:
            if progress is not None:
                progress(_progress_payload(
                    completed, succeeded, failed, 0, self.item_concurrency, started, baseline, self.metrics
                ))

        if self.mode == "sequential":
            for item in items:
                if self.stop_event.is_set():
                    raise WorkerShutdownRequested
                record(self.pool.classify(item), 0)
            finish_progress()
            return

        iterator = iter(items)
        executor = ThreadPoolExecutor(max_workers=self.item_concurrency, thread_name_prefix="rag-item")
        in_flight: set[Future[AnalysisOutcome]] = set()
        shutdown_requested = False
        shutdown_deadline = None
        try:
            if self.stop_event.is_set():
                raise WorkerShutdownRequested
            for _index in range(self.item_concurrency):
                if not _submit_one(executor, iterator, in_flight, self.pool.classify):
                    break

            while in_flight:
                if self.stop_event.is_set():
                    shutdown_requested = True
                    shutdown_deadline = shutdown_deadline or monotonic() + self.shutdown_grace_seconds
                if shutdown_deadline is not None and monotonic() >= shutdown_deadline:
                    raise WorkerShutdownRequested
                wait_timeout = self.heartbeat_interval_seconds
                if shutdown_deadline is not None:
                    wait_timeout = min(wait_timeout, max(0, shutdown_deadline - monotonic()))
                done, _pending = wait(
                    in_flight,
                    timeout=wait_timeout,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    heartbeat()
                    if progress is not None and monotonic() - last_logged_at >= 5:
                        progress(_progress_payload(
                            completed,
                            succeeded,
                            failed,
                            len(in_flight),
                            self.item_concurrency,
                            started,
                            baseline,
                            self.metrics,
                        ))
                        last_logged_at = monotonic()
                    continue
                if self.stop_event.is_set():
                    shutdown_requested = True
                    shutdown_deadline = shutdown_deadline or monotonic() + self.shutdown_grace_seconds
                for future in done:
                    in_flight.remove(future)
                    record(future.result(), len(in_flight))
                    if self.stop_event.is_set():
                        shutdown_requested = True
                    if not shutdown_requested:
                        _submit_one(executor, iterator, in_flight, self.pool.classify)
            if shutdown_requested:
                raise WorkerShutdownRequested
            finish_progress()
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
        usage=getattr(result, "usage", {}),
        validation_attempts=getattr(result, "attempts", 1),
    )


def _progress_payload(
    completed: int,
    succeeded: int,
    failed: int,
    in_flight: int,
    item_concurrency: int,
    started: float,
    baseline: dict[str, int],
    metrics: RuntimeMetrics,
) -> dict[str, int]:
    current = metrics.snapshot()
    return {
        "completed": completed,
        "succeeded": succeeded,
        "failed": failed,
        "in_flight": in_flight,
        "item_concurrency": item_concurrency,
        "embedding_retries": current["embedding_retries"] - baseline["embedding_retries"],
        "llm_retries": current["llm_retries"] - baseline["llm_retries"],
        "input_tokens": current["input_tokens"] - baseline["input_tokens"],
        "output_tokens": current["output_tokens"] - baseline["output_tokens"],
        "elapsed_ms": int((monotonic() - started) * 1000),
    }
