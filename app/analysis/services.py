from __future__ import annotations

from app.analysis.executor import RagRuntime
from app.analysis.models import StepAttemptContext
from app.analysis.result_store import AnalysisResultStore


class CommentAnalyzer:
    def __init__(self, runtime: RagRuntime, result_store: AnalysisResultStore) -> None:
        self.runtime = runtime
        self.result_store = result_store

    def analyze(self, context: StepAttemptContext) -> dict[str, int]:
        total, items = self.result_store.load_comment_items(context)
        self.result_store.reconcile(context, "comment", total)
        self.runtime.run(
            items,
            lambda outcome: self.result_store.persist(context, "comment", outcome),
            lambda: self.result_store.heartbeat(context),
        )
        progress = self.result_store.reconcile(context, "comment", total)
        return {"comments_analyzed": total, "succeeded": progress["succeeded"], "failed": progress["failed"]}


class ScriptAnalyzer:
    def __init__(self, runtime: RagRuntime, result_store: AnalysisResultStore) -> None:
        self.runtime = runtime
        self.result_store = result_store

    def analyze(self, context: StepAttemptContext) -> dict[str, int]:
        total, items = self.result_store.load_script_items(context)
        self.result_store.reconcile(context, "script", total)
        self.runtime.run(
            items,
            lambda outcome: self.result_store.persist(context, "script", outcome),
            lambda: self.result_store.heartbeat(context),
        )
        progress = self.result_store.reconcile(context, "script", total)
        return {"script_segments_analyzed": total, "succeeded": progress["succeeded"], "failed": progress["failed"]}
