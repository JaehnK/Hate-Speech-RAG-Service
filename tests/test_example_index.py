import chromadb
import numpy as np
import pytest

from app.analysis.collections import EXAMPLE_COLLECTION_NAME
from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.example_index import ExampleIndex, build_example_index, has_example_index, index_directory
from app.analysis.retriever import DualVectorRetriever
from app.analysis.vector_store import _get_collection, parse_example_query_result


def _metadata(i: int) -> dict:
    return {
        "source_dataset": "k-haters",
        "source_split": "train",
        "license_tier": "commercial_ok",
        "mapped_categories": '["profanity"]' if i % 2 else "[]",
        "is_hate_speech": bool(i % 2),
        "target_labels": "[]",
    }


@pytest.fixture
def store(tmp_path):
    rng = np.random.default_rng(0)
    vectors = rng.normal(size=(300, 32)).astype(np.float32)
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    for name in ("hate_speech_taxonomy", "hate_speech_authoritative"):
        _get_collection(tmp_path / "chroma", name, client=client)
    examples = _get_collection(tmp_path / "chroma", EXAMPLE_COLLECTION_NAME, client=client)
    examples.add(
        ids=[f"ex:{i}" for i in range(300)],
        embeddings=vectors.tolist(),
        documents=[f"comment {i}" for i in range(300)],
        metadatas=[_metadata(i) for i in range(300)],
    )
    return tmp_path / "chroma", vectors


def test_index_matches_exact_cosine_neighbours(store) -> None:
    persist, vectors = store
    summary = build_example_index(str(persist), str(index_directory(persist)))
    assert summary["examples"] == 300 and has_example_index(persist)

    index = ExampleIndex(index_directory(persist))
    assert index.count() == 300
    normalized = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    for row in (0, 17, 299):
        query = vectors[row] + 0.01
        expected = np.argsort(-(normalized @ (query / np.linalg.norm(query))))[:5]
        result = index.query(query_embeddings=[query.tolist()], n_results=5)
        assert result["ids"][0] == [f"ex:{i}" for i in expected]
        assert result["distances"][0] == sorted(result["distances"][0])

    parsed = parse_example_query_result(index.query(query_embeddings=[vectors[3].tolist()], n_results=1))
    assert parsed[0].doc_id == "ex:3"
    assert parsed[0].text == "comment 3"
    assert parsed[0].is_hate_speech is True
    assert parsed[0].mapped_categories == ("profanity",)
    assert parsed[0].distance == pytest.approx(0.0, abs=1e-3)


def test_retriever_prefers_example_index_when_built(store) -> None:
    persist, _ = store
    assert not isinstance(DualVectorRetriever(persist, HashEmbeddingFunction(32)).example_collection, ExampleIndex)

    build_example_index(str(persist), str(index_directory(persist)))
    retriever = DualVectorRetriever(persist, HashEmbeddingFunction(32))
    assert isinstance(retriever.example_collection, ExampleIndex)

    bundle = retriever.retrieve("comment", taxonomy_n=0, authoritative_n=0, example_n=4)
    assert len(bundle.examples) == 4
    assert bundle.failures == ()
