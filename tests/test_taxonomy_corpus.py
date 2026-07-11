from app.analysis.taxonomy import ALLOWED_CATEGORIES, build_internal_taxonomy_documents


def test_internal_taxonomy_has_required_cards() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    assert "taxonomy:allowed_categories:0" in doc_ids
    assert "taxonomy:non_hate_rule:0" in doc_ids
    assert "taxonomy:other_rule:0" in doc_ids
    assert "taxonomy:political_axis:0" in doc_ids
    assert "conflict:exclusive_categories:0" in doc_ids


def test_internal_taxonomy_has_category_card_for_each_allowed_category() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    for category in ALLOWED_CATEGORIES:
        assert f"category:{category}:0" in doc_ids


def test_political_axis_card_is_retrievable_by_tag() -> None:
    documents = build_internal_taxonomy_documents()
    political_axis = next(doc for doc in documents if doc.doc_id == "taxonomy:political_axis:0")

    assert "political_axis" in political_axis.retrieval_tags
    assert "state_authority" in political_axis.related_categories
    assert "non_state_community" in political_axis.related_categories


def test_internal_taxonomy_documents_have_stable_hashes() -> None:
    documents = build_internal_taxonomy_documents()

    assert all(len(doc.chunk_hash) == 64 for doc in documents)
