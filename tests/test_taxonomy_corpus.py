from app.analysis.taxonomy import (
    ALLOWED_CATEGORIES,
    CATEGORY_CARDS,
    TAXONOMY_CATEGORY_CODES,
    V07_CATEGORY_MAP,
    build_internal_taxonomy_documents,
)


def test_internal_taxonomy_has_required_cards() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    # taxonomy v0.7.0: 9 rule documents + one card per current category (six + unclassified)
    assert len(documents) == 9 + len(TAXONOMY_CATEGORY_CODES) == 16
    assert "taxonomy:allowed_categories:0" in doc_ids
    assert "taxonomy:hate_threshold:0" in doc_ids
    assert "taxonomy:non_hate_rule:0" in doc_ids
    assert "taxonomy:other_rule:0" not in doc_ids
    assert "category:other:0" not in doc_ids
    assert "taxonomy:political_axis:0" not in doc_ids
    assert "taxonomy:political_target:0" in doc_ids
    assert "category:state_authority:0" not in doc_ids
    assert "category:no_target:0" not in doc_ids
    assert "taxonomy:context_exception:0" in doc_ids
    assert "taxonomy:multi_label_rule:0" in doc_ids
    assert "taxonomy:hate_type:0" in doc_ids
    assert "taxonomy:target_group:0" in doc_ids
    assert "conflict:exclusive_categories:0" in doc_ids


def test_internal_taxonomy_has_category_card_for_each_allowed_category() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    for category in TAXONOMY_CATEGORY_CODES:
        assert f"category:{category}:0" in doc_ids


def test_category_cards_publish_inclusion_exclusion_and_boundaries() -> None:
    documents = build_internal_taxonomy_documents()

    # Cards for older codes stay for display of stored results only.
    assert set(CATEGORY_CARDS) == set(ALLOWED_CATEGORIES) | set(TAXONOMY_CATEGORY_CODES)
    for category in TAXONOMY_CATEGORY_CODES:
        definition = CATEGORY_CARDS[category]
        card = next(doc for doc in documents if doc.doc_id == f"category:{category}:0")
        assert definition.include
        assert definition.exclude
        assert definition.boundary
        assert definition.cues
        assert "정의:" in card.chunk_text
        assert "포함 기준:" in card.chunk_text
        assert "제외 기준:" in card.chunk_text
        assert "경계 규칙:" in card.chunk_text
        assert "판단 단서:" in card.chunk_text
        assert category in card.retrieval_tags
        assert definition.definition in card.chunk_text


def test_political_target_card_names_the_two_political_categories() -> None:
    documents = build_internal_taxonomy_documents()
    card = next(doc for doc in documents if doc.doc_id == "taxonomy:political_target:0")

    assert "political_target" in card.retrieval_tags
    assert set(card.related_categories) == {"political_actor", "political_camp"}


def test_every_older_code_maps_onto_the_current_categories() -> None:
    older = set(ALLOWED_CATEGORIES) - set(TAXONOMY_CATEGORY_CODES)
    assert set(V07_CATEGORY_MAP) == older
    assert set(V07_CATEGORY_MAP.values()) <= set(TAXONOMY_CATEGORY_CODES)


def test_internal_taxonomy_documents_have_stable_hashes() -> None:
    documents = build_internal_taxonomy_documents()

    assert all(len(doc.chunk_hash) == 64 for doc in documents)
