from app.analysis.models import ExampleSearchResult
from app.analysis.normative_guidance import category_filter, guided_categories
from app.analysis.taxonomy import POLITICAL_CATEGORIES


def _example(categories, hate=True, targets=()):
    return ExampleSearchResult(
        doc_id="e", text="t", source_dataset="k-haters", source_split="train", license_tier="commercial_ok",
        mapped_categories=tuple(categories), is_hate_speech=hate, distance=0.1, target_labels=tuple(targets),
    )


def test_keeps_categories_shared_by_at_least_two_hate_examples() -> None:
    examples = [_example(["identity"]), _example(["identity", "profanity"]), _example(["gender"]),
                _example(["profanity"], hate=False), _example(["unclassified"], hate=False)]

    assert guided_categories(examples) == ("identity",)


def test_political_targets_expand_to_all_political_categories() -> None:
    examples = [_example([], targets=["political"]), _example([], targets=["political"])]

    assert set(guided_categories(examples)) == set(POLITICAL_CATEGORIES)


def test_category_filter_shapes() -> None:
    assert category_filter(()) is None
    assert category_filter(("identity",)) == {"cat_identity": True}
    assert category_filter(("identity", "gender")) == {"$or": [{"cat_identity": True}, {"cat_gender": True}]}
