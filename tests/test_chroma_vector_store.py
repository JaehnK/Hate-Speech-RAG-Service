from app.analysis.rag_ingest import ingest_internal_taxonomy
from app.analysis.taxonomy import build_internal_taxonomy_documents
from app.analysis.vector_store import _upsert_batches, query_definition_documents


def test_ingests_internal_taxonomy_to_chroma(tmp_path) -> None:
    count = ingest_internal_taxonomy(tmp_path, reset=True)

    assert count == len(build_internal_taxonomy_documents())


def test_political_query_retrieves_political_axis(tmp_path) -> None:
    ingest_internal_taxonomy(tmp_path, reset=True)

    results = query_definition_documents(
        tmp_path,
        "정치 지지층과 정당 권위체를 비하하는 댓글",
        n_results=8,
    )

    assert "taxonomy:political_axis:0" in {result.doc_id for result in results}


def test_protected_attribute_query_retrieves_gender_card(tmp_path) -> None:
    ingest_internal_taxonomy(tmp_path, reset=True)

    results = query_definition_documents(
        tmp_path,
        "성별과 성역할을 이유로 비하하는 표현",
        n_results=8,
    )

    assert "category:gender:0" in {result.doc_id for result in results}


def test_upsert_batches_limits_each_external_embedding_request() -> None:
    class RecordingCollection:
        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def upsert(self, *, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
            assert len(ids) == len(documents) == len(metadatas)
            self.batch_sizes.append(len(ids))

    collection = RecordingCollection()
    count = 513

    _upsert_batches(
        collection,
        ids=[str(index) for index in range(count)],
        documents=["document"] * count,
        metadatas=[{}] * count,
    )

    assert collection.batch_sizes == [100, 100, 100, 100, 100, 13]


def test_upsert_batches_embeds_concurrently_but_writes_complete_batches() -> None:
    class RecordingEmbedding:
        def __call__(self, *, input: list[str]) -> list[list[float]]:
            return [[float(document)] for document in input]

    class RecordingCollection:
        def __init__(self) -> None:
            self.batches: list[tuple[list[str], list[list[float]]]] = []

        def upsert(
            self,
            *,
            ids: list[str],
            documents: list[str],
            metadatas: list[dict],
            embeddings: list[list[float]],
        ) -> None:
            assert len(ids) == len(documents) == len(metadatas) == len(embeddings)
            self.batches.append((ids, embeddings))

    collection = RecordingCollection()
    _upsert_batches(
        collection,
        ids=[str(index) for index in range(5)],
        documents=[str(index) for index in range(5)],
        metadatas=[{}] * 5,
        batch_size=2,
        embedding_function=RecordingEmbedding(),
        embedding_concurrency=2,
    )

    assert collection.batches == [
        (["0", "1"], [[0.0], [1.0]]),
        (["2", "3"], [[2.0], [3.0]]),
        (["4"], [[4.0]]),
    ]
