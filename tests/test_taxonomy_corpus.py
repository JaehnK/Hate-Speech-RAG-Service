from app.analysis.taxonomy import ALLOWED_CATEGORIES, CATEGORY_CARDS, build_internal_taxonomy_documents


def test_internal_taxonomy_has_required_cards() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    assert len(documents) == 10 + len(ALLOWED_CATEGORIES)
    assert "taxonomy:allowed_categories:0" in doc_ids
    assert "taxonomy:hate_threshold:0" in doc_ids
    assert "taxonomy:non_hate_rule:0" in doc_ids
    assert "taxonomy:other_rule:0" in doc_ids
    assert "taxonomy:political_axis:0" in doc_ids
    assert "taxonomy:context_exception:0" in doc_ids
    assert "taxonomy:multi_label_rule:0" in doc_ids
    assert "taxonomy:hate_type:0" in doc_ids
    assert "taxonomy:target_group:0" in doc_ids
    assert "conflict:exclusive_categories:0" in doc_ids


def test_internal_taxonomy_has_category_card_for_each_allowed_category() -> None:
    documents = build_internal_taxonomy_documents()
    doc_ids = {doc.doc_id for doc in documents}

    for category in ALLOWED_CATEGORIES:
        assert f"category:{category}:0" in doc_ids


def test_category_cards_publish_inclusion_exclusion_and_boundaries() -> None:
    documents = build_internal_taxonomy_documents()

    assert set(CATEGORY_CARDS) == set(ALLOWED_CATEGORIES)
    for category in ALLOWED_CATEGORIES:
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


def test_political_axis_card_is_retrievable_by_tag() -> None:
    documents = build_internal_taxonomy_documents()
    political_axis = next(doc for doc in documents if doc.doc_id == "taxonomy:political_axis:0")

    assert "political_axis" in political_axis.retrieval_tags
    assert "state_authority" in political_axis.related_categories
    assert "non_state_community" in political_axis.related_categories


def test_internal_taxonomy_documents_have_stable_hashes() -> None:
    documents = build_internal_taxonomy_documents()

    assert all(len(doc.chunk_hash) == 64 for doc in documents)
