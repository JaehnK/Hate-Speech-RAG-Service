from types import SimpleNamespace

from experiments.io import ExperimentInput
from experiments.run_rag_experiment import _run_item
from experiments.variants import ExperimentVariant


class FakeClassifier:
    def classify_text(self, _text, _source_type, _video_title=None):
        return SimpleNamespace(
            payload={"is_hate_speech": False, "categories": ["unclassified"]},
            model="fake",
            prompt_version="test-v1",
            usage={},
            attempts=1,
        )


def test_run_item_records_repeat_index() -> None:
    row = _run_item(
        FakeClassifier(),
        ExperimentVariant("three_vector_rag", taxonomy_k=4, definition_k=4, example_k=6),
        ExperimentInput("item-1", "text", "comment"),
        repeat_index=2,
    )

    assert row["status"] == "succeeded"
    assert row["repeat_index"] == 2


def test_completed_keys_only_counts_succeeded_rows(tmp_path) -> None:
    from experiments.io import append_jsonl
    from experiments.run_rag_experiment import completed_keys

    path = tmp_path / "results.jsonl"
    append_jsonl(path, [
        {"item_id": "a", "variant": "v", "repeat_index": 0, "status": "succeeded"},
        {"item_id": "b", "variant": "v", "repeat_index": 0, "status": "failed"},
    ])

    assert completed_keys(path) == {("a", "v", 0)}
    assert completed_keys(tmp_path / "missing.jsonl") == set()


def test_caching_embedding_embeds_each_text_once() -> None:
    from experiments.run_rag_experiment import CachingEmbedding

    class Inner:
        calls: list[list[str]] = []

        def embed_query(self, texts):
            self.calls.append(list(texts))
            return [[float(len(text))] for text in texts]

        def name(self):
            return "inner"

    inner = Inner()
    cached = CachingEmbedding(inner)

    assert cached.embed_query(["ab"]) == [[2.0]]
    assert cached.embed_query(["ab", "c"]) == [[2.0], [1.0]]
    assert inner.calls == [["ab"], ["c"]]
    assert cached.name() == "inner"
