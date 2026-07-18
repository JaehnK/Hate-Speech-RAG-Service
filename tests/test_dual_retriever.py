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
    def __init__(self, taxonomy, authoritative, example) -> None:
        self.collections = {
            "hate_speech_taxonomy": taxonomy,
            "hate_speech_authoritative": authoritative,
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
    taxonomy = FakeCollection(_definition_result())
    authoritative = FakeCollection(_definition_result())
    example = FakeCollection(_example_result())
    retriever = DualVectorRetriever("unused", embedding, FakeClient(taxonomy, authoritative, example))

    bundle = retriever.retrieve("query", taxonomy_n=4, authoritative_n=4, example_n=6)

    assert embedding.calls == [["query"]]
    assert taxonomy.calls == [{"query_embeddings": [[0.1, 0.2]], "n_results": 4}]
    assert authoritative.calls == [{"query_embeddings": [[0.1, 0.2]], "n_results": 4}]
    assert example.calls == [{"query_embeddings": [[0.1, 0.2]], "n_results": 6}]
    assert bundle.taxonomy[0].doc_id == "definition:1"
    assert bundle.authoritative[0].doc_id == "definition:1"
    assert bundle.examples[0].doc_id == "example:1"
    assert bundle.failures == ()


@pytest.mark.parametrize(
    ("failed_collection", "expected_failures", "taxonomy_count", "authoritative_count", "example_count"),
    [
        ("taxonomy", ("taxonomy",), 0, 1, 1),
        ("authoritative", ("authoritative",), 1, 0, 1),
        ("example", ("examples",), 1, 1, 0),
    ],
)
def test_dual_retriever_preserves_degraded_results(
    failed_collection,
    expected_failures,
    taxonomy_count,
    authoritative_count,
    example_count,
) -> None:
    taxonomy = FakeCollection(_definition_result())
    authoritative = FakeCollection(_definition_result())
    example = FakeCollection(_example_result())
    if failed_collection == "taxonomy":
        taxonomy.error = RuntimeError("taxonomy unavailable")
    elif failed_collection == "authoritative":
        authoritative.error = RuntimeError("authoritative unavailable")
    else:
        example.error = RuntimeError("example unavailable")
    retriever = DualVectorRetriever("unused", FakeEmbedding(), FakeClient(taxonomy, authoritative, example))

    bundle = retriever.retrieve("query", taxonomy_n=4, authoritative_n=4, example_n=6)

    assert bundle.failures == expected_failures
    assert len(bundle.taxonomy) == taxonomy_count
    assert len(bundle.authoritative) == authoritative_count
    assert len(bundle.examples) == example_count
