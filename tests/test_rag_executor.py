from threading import Event, Lock
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.analysis.executor import RagRuntime
from app.analysis.models import AnalysisItem
from app.jobs.exceptions import WorkerShutdownRequested


class DelayedClassifier:
    def __init__(self, delay: float, state: dict, lock: Lock) -> None:
        self.delay = delay
        self.state = state
        self.lock = lock

    def classify_text(self, text, _source_type):
        with self.lock:
            self.state["active"] += 1
            self.state["max_active"] = max(self.state["max_active"], self.state["active"])
        sleep(self.delay)
        with self.lock:
            self.state["active"] -= 1
        return SimpleNamespace(
            payload={
                "input_text": text,
                "is_hate_speech": False,
                "categories": ["unclassified"],
                "target_group": None,
                "hate_type": None,
                "reasoning": text,
                "similar_cases_used": [],
                "definition_docs_used": [],
            },
            rag_context_status="complete",
            prompt_version="test-v1",
            model="fake",
        )


def test_parallel_runtime_is_bounded_and_faster_than_sequential() -> None:
    items = _items(40)
    sequential_state = {"active": 0, "max_active": 0}
    parallel_state = {"active": 0, "max_active": 0}
    sequential = RagRuntime([DelayedClassifier(0.02, sequential_state, Lock())])
    parallel_lock = Lock()
    parallel = RagRuntime(
        [DelayedClassifier(0.02, parallel_state, parallel_lock) for _index in range(4)],
        mode="parallel",
        item_concurrency=4,
    )

    sequential_started = monotonic()
    sequential.run(items, lambda _outcome: None, lambda: None)
    sequential_elapsed = monotonic() - sequential_started
    parallel_started = monotonic()
    progress = []
    parallel.run(items, lambda _outcome: None, lambda: None, progress.append)
    parallel_elapsed = monotonic() - parallel_started

    assert sequential_state["max_active"] == 1
    assert parallel_state["max_active"] == 4
    assert parallel_elapsed * 3 < sequential_elapsed
    assert progress[-1]["completed"] == 40
    assert progress[-1]["item_concurrency"] == 4
    assert progress[-1]["in_flight"] == 0


def test_parallel_runtime_persists_every_out_of_order_result() -> None:
    class VariableClassifier(DelayedClassifier):
        def classify_text(self, text, source_type):
            self.delay = (6 - int(text)) * 0.005
            return super().classify_text(text, source_type)

    state = {"active": 0, "max_active": 0}
    lock = Lock()
    runtime = RagRuntime(
        [VariableClassifier(0, state, lock) for _index in range(3)],
        mode="parallel",
        item_concurrency=3,
    )
    completed = []

    runtime.run(_items(6), lambda outcome: completed.append(outcome.result_values["reasoning"]), lambda: None)

    assert sorted(completed) == [str(index) for index in range(6)]
    assert completed != sorted(completed)


def test_runtime_stops_submitting_and_drains_active_items() -> None:
    stop_event = Event()
    state = {"active": 0, "max_active": 0}
    lock = Lock()
    runtime = RagRuntime(
        [DelayedClassifier(0.01, state, lock) for _index in range(2)],
        mode="parallel",
        item_concurrency=2,
        stop_event=stop_event,
    )
    completed = []

    def persist(outcome) -> None:
        completed.append(outcome.source_id)
        stop_event.set()

    with pytest.raises(WorkerShutdownRequested):
        runtime.run(_items(10), persist, lambda: None)

    assert 1 <= len(completed) <= 2


def _items(count: int) -> list[AnalysisItem]:
    return [AnalysisItem(uuid4(), "comment", str(index)) for index in range(count)]
