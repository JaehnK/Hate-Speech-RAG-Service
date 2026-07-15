import pytest

from app.analysis.retriever import DualVectorRetriever


class FakeEmbedding:
    def __init__(self) -> None:
        self.calls = []

    def embed_query(self, texts):
        self.calls.append(texts)
        return [[0.1, 0.2]]


class FakeCollection:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, definition, example) -> None:
        self.collections = {
            "hate_speech_definitions": definition,
            "hate_speech_examples": example,
        }

    def get_or_create_collection(self, name, **_kwargs):
        return self.collections[name]


def _definition_result():
    return {
        "ids": [["definition:1"]],
        "documents": [["definition"]],
        "metadatas": [[{
            "source_id": "source",
            "source_title": "title",
            "retrieval_tags": "[]",
            "related_categories": "[]",
        }]],
        "distances": [[0.1]],
    }


def _example_result():
    return {
        "ids": [["example:1"]],
        "documents": [["example"]],
        "metadatas": [[{
            "source_dataset": "fixture",
            "source_split": "train",
            "license_tier": "commercial_ok",
            "mapped_categories": "[]",
            "is_hate_speech": True,
        }]],
        "distances": [[0.2]],
    }


def test_dual_retriever_reuses_one_query_embedding() -> None:
    embedding = FakeEmbedding()
    definition = FakeCollection(_definition_result())
    example = FakeCollection(_example_result())
    retriever = DualVectorRetriever("unused", embedding, FakeClient(definition, example))

    bundle = retriever.retrieve("query", definition_n=8, example_n=6)

    assert embedding.calls == [["query"]]
    assert definition.calls == [{"query_embeddings": [[0.1, 0.2]], "n_results": 8}]
    assert example.calls == [{"query_embeddings": [[0.1, 0.2]], "n_results": 6}]
    assert bundle.definitions[0].doc_id == "definition:1"
    assert bundle.examples[0].doc_id == "example:1"
    assert bundle.failures == ()


@pytest.mark.parametrize(
    ("failed_collection", "expected_failures", "definition_count", "example_count"),
    [
        ("definition", ("definitions",), 0, 1),
        ("example", ("examples",), 1, 0),
    ],
)
def test_dual_retriever_preserves_degraded_results(
    failed_collection,
    expected_failures,
    definition_count,
    example_count,
) -> None:
    definition = FakeCollection(_definition_result())
    example = FakeCollection(_example_result())
    if failed_collection == "definition":
        definition.error = RuntimeError("definition unavailable")
    else:
        example.error = RuntimeError("example unavailable")
    retriever = DualVectorRetriever("unused", FakeEmbedding(), FakeClient(definition, example))

    bundle = retriever.retrieve("query", definition_n=8, example_n=6)

    assert bundle.failures == expected_failures
    assert len(bundle.definitions) == definition_count
    assert len(bundle.examples) == example_count
