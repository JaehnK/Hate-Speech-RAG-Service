from app.analysis.prompt_validator import validate_classification_output


def _base_payload() -> dict[str, object]:
    return {
        "input_text": "정치 팬덤을 모욕하는 댓글",
        "is_hate_speech": True,
        "categories": ["non_state_community", "profanity"],
        "target_group": "정치 지지층",
        "hate_type": "모욕/비하",
        "reasoning": "정치 지지층을 집단적으로 비하한다.",
        "similar_cases_used": [],
        "definition_docs_used": [],
    }


def test_valid_hate_output() -> None:
    result = validate_classification_output(_base_payload())

    assert result.valid
    assert result.errors == ()


def test_valid_non_hate_output() -> None:
    payload = _base_payload()
    payload["is_hate_speech"] = False
    payload["categories"] = ["unclassified"]
    payload["target_group"] = None
    payload["hate_type"] = None

    result = validate_classification_output(payload)

    assert result.valid


def test_non_hate_must_only_use_unclassified() -> None:
    payload = _base_payload()
    payload["is_hate_speech"] = False
    payload["categories"] = ["gender"]

    result = validate_classification_output(payload)

    assert not result.valid
    assert "non_hate_must_use_only_unclassified" in result.errors


def test_hate_must_not_use_unclassified() -> None:
    payload = _base_payload()
    payload["categories"] = ["unclassified"]

    result = validate_classification_output(payload)

    assert not result.valid
    assert "hate_must_not_use_unclassified" in result.errors


def test_other_category_is_exclusive() -> None:
    payload = _base_payload()
    payload["categories"] = ["other", "profanity"]

    result = validate_classification_output(payload)

    assert not result.valid
    assert "other_must_be_exclusive" in result.errors


def test_unknown_category_is_invalid() -> None:
    payload = _base_payload()
    payload["categories"] = ["animal"]

    result = validate_classification_output(payload)

    assert not result.valid
    assert "unknown_categories:animal" in result.errors


def test_reasoning_must_be_korean() -> None:
    payload = _base_payload()
    payload["reasoning"] = "This is an English explanation."

    result = validate_classification_output(payload)

    assert not result.valid
    assert "reasoning_must_be_korean" in result.errors
