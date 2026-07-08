from app.analysis.prompt_template import PROMPT_VERSION, build_category_prompt
from app.analysis.taxonomy import build_internal_taxonomy_documents


def test_prompt_contains_contract_without_hate_assumption() -> None:
    taxonomy_context = build_internal_taxonomy_documents()[:3]

    prompt = build_category_prompt(
        input_text="오늘 날씨가 좋네요",
        source_type="comment",
        taxonomy_context=taxonomy_context,
    )

    assert PROMPT_VERSION in prompt
    assert "Do not assume the input is hate speech." in prompt
    assert "주어질 문장은 모두 혐오표현" not in prompt
    assert '"definition_docs_used"' in prompt


def test_prompt_rejects_unknown_source_type() -> None:
    try:
        build_category_prompt(
            input_text="text",
            source_type="video",  # type: ignore[arg-type]
            taxonomy_context=[],
        )
    except ValueError as exc:
        assert "unsupported source_type" in str(exc)
    else:
        raise AssertionError("expected ValueError")
