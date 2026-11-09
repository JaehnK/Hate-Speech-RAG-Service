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


def test_retriever_skips_collections_with_zero_k() -> None:
    taxonomy = FakeCollection(_definition_result())
    authoritative = FakeCollection(_definition_result())
    example = FakeCollection(_example_result())
    retriever = DualVectorRetriever("unused", FakeEmbedding(), FakeClient(taxonomy, authoritative, example))

    bundle = retriever.retrieve("query", taxonomy_n=0, authoritative_n=0, example_n=6)

    assert bundle.failures == ()
    assert taxonomy.calls == [] and authoritative.calls == []
    assert len(bundle.examples) == 1


def test_retriever_llm_only_baseline_skips_embedding() -> None:
    embedding = FakeEmbedding()
    collections = [FakeCollection(error=RuntimeError("must not query")) for _ in range(3)]
    retriever = DualVectorRetriever("unused", embedding, FakeClient(*collections))

    bundle = retriever.retrieve("query", taxonomy_n=0, authoritative_n=0, example_n=0)

    assert bundle.failures == ()
    assert embedding.calls == []


def _definition_rows(ids):
    meta = {"source_id": "source", "source_title": "title", "retrieval_tags": "[]", "related_categories": "[]"}
    return {
        "ids": [list(ids)],
        "documents": [[f"text {doc_id}" for doc_id in ids]],
        "metadatas": [[dict(meta) for _ in ids]],
        "distances": [[0.1 * (i + 1) for i in range(len(ids))]],
    }


class PinnableCollection(FakeCollection):
    def __init__(self, ranked) -> None:
        super().__init__(_definition_rows(ranked))
        self.get_calls = 0

    def get(self, ids, include):
        self.get_calls += 1
        rows = _definition_rows(ids)
        return {"ids": rows["ids"][0], "documents": rows["documents"][0], "metadatas": rows["metadatas"][0]}


def test_pinned_taxonomy_cards_come_first_without_duplicates() -> None:
    taxonomy = PinnableCollection(["rule:a", "card:x", "card:y", "card:z"])
    retriever = DualVectorRetriever(
        "unused",
        embedding_function=FakeEmbedding(),
        client=FakeClient(taxonomy, FakeCollection(_definition_result()), FakeCollection(_example_result())),
    )

    bundle = retriever.retrieve(
        "q", taxonomy_n=2, authoritative_n=0, example_n=0, pinned_taxonomy_ids=("rule:a", "rule:b")
    )
    retriever.retrieve("q", taxonomy_n=2, authoritative_n=0, example_n=0, pinned_taxonomy_ids=("rule:a", "rule:b"))

    assert [result.doc_id for result in bundle.taxonomy] == ["rule:a", "rule:b", "card:x", "card:y"]
    assert taxonomy.calls[0]["n_results"] == 4
    assert taxonomy.get_calls == 1


class SlotCollection(FakeCollection):
    def query(self, **kwargs):
        self.calls.append(kwargs)
        kind = kwargs["where"]["document_type"]
        return _definition_rows([f"{kind}:{i}" for i in range(kwargs["n_results"])])


def test_authoritative_slots_query_each_source_type() -> None:
    authoritative = SlotCollection()
    retriever = DualVectorRetriever(
        "unused",
        embedding_function=FakeEmbedding(),
        client=FakeClient(FakeCollection(_definition_result()), authoritative, FakeCollection(_example_result())),
    )

    bundle = retriever.retrieve(
        "q",
        taxonomy_n=0,
        authoritative_n=4,
        example_n=0,
        authoritative_slots=(("official_standard", 2), ("platform_summary", 1), ("dataset_guideline", 0)),
    )

    assert [result.doc_id for result in bundle.authoritative] == [
        "official_standard:0",
        "official_standard:1",
        "platform_summary:0",
    ]
    assert [call["where"] for call in authoritative.calls] == [
        {"document_type": "official_standard"},
        {"document_type": "platform_summary"},
    ]


class GuidedSlotCollection(FakeCollection):
    def __init__(self, guided_hits) -> None:
        super().__init__()
        self.guided_hits = guided_hits

    def query(self, **kwargs):
        self.calls.append(kwargs)
        where = kwargs["where"]
        if "$and" in where:
            ids = self.guided_hits[: kwargs["n_results"]]
        else:
            ids = [f"{where['document_type']}:{i}" for i in range(kwargs["n_results"])]
        return _definition_rows(ids)


def test_guided_slot_filters_by_example_categories_and_tops_up() -> None:
    authoritative = GuidedSlotCollection(guided_hits=["guided:0"])
    examples = FakeCollection({
        "ids": [["e1", "e2"]],
        "documents": [["a", "b"]],
        "metadatas": [[
            {"source_dataset": "k", "source_split": "train", "license_tier": "x",
             "mapped_categories": '["identity"]', "is_hate_speech": True, "target_labels": "[]"},
            {"source_dataset": "k", "source_split": "train", "license_tier": "x",
             "mapped_categories": '["identity"]', "is_hate_speech": True, "target_labels": "[]"},
        ]],
        "distances": [[0.1, 0.2]],
    })
    retriever = DualVectorRetriever(
        "unused",
        embedding_function=FakeEmbedding(),
        client=FakeClient(FakeCollection(_definition_result()), authoritative, examples),
    )

    bundle = retriever.retrieve(
        "q", taxonomy_n=0, authoritative_n=3, example_n=2,
        authoritative_slots=(("official_standard", 2, True), ("international_summary", 1, False)),
    )

    assert [result.doc_id for result in bundle.authoritative] == [
        "guided:0",
        "official_standard:0",
        "international_summary:0",
    ]
    assert authoritative.calls[0]["where"] == {
        "$and": [{"document_type": "official_standard"}, {"cat_identity": True}]
    }
