from app.analysis.rag_ingest import ingest_internal_taxonomy
from app.analysis.taxonomy import build_internal_taxonomy_documents
from app.analysis.vector_store import query_definition_documents


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
