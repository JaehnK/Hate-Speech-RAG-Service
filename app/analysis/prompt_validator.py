from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.analysis.models import ValidationResult
from app.analysis.taxonomy import ALLOWED_CATEGORIES


REQUIRED_OUTPUT_FIELDS: tuple[str, ...] = (
    "input_text",
    "is_hate_speech",
    "categories",
    "target_group",
    "hate_type",
    "reasoning",
    "similar_cases_used",
    "definition_docs_used",
)


def validate_classification_output(
    payload: Mapping[str, Any],
    allowed_categories: tuple[str, ...] = ALLOWED_CATEGORIES,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [field for field in REQUIRED_OUTPUT_FIELDS if field not in payload]
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")

    is_hate_speech = payload.get("is_hate_speech")
    if not isinstance(is_hate_speech, bool):
        errors.append("is_hate_speech_must_be_bool")

    categories = payload.get("categories")
    if not _is_string_list(categories):
        errors.append("categories_must_be_string_list")
        categories = []

    category_set = set(categories)
    unknown = sorted(category_set.difference(allowed_categories))
    if unknown:
        errors.append(f"unknown_categories:{','.join(unknown)}")

    if is_hate_speech is False and categories != ["unclassified"]:
        errors.append("non_hate_must_use_only_unclassified")

    if is_hate_speech is True:
        if not categories:
            errors.append("hate_must_have_at_least_one_category")
        if "unclassified" in category_set:
            errors.append("hate_must_not_use_unclassified")
        if "other" in category_set and len(categories) > 1:
            errors.append("other_must_be_exclusive")
        if "no_target" in category_set:
            if category_set - {"no_target", "profanity"}:
                errors.append("no_target_conflicts_with_target_category")
            if payload.get("target_group") is not None:
                errors.append("no_target_requires_null_target_group")
        if payload.get("target_group") is None and category_set.difference({"profanity", "no_target"}):
            warnings.append("target_group_missing_for_targeted_category")

    if not isinstance(payload.get("similar_cases_used", []), list):
        errors.append("similar_cases_used_must_be_list")
    if not isinstance(payload.get("definition_docs_used", []), list):
        errors.append("definition_docs_used_must_be_list")

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or not re.search(r"[가-힣]", reasoning):
        errors.append("reasoning_must_be_korean")

    return ValidationResult(valid=not errors, errors=tuple(errors), warnings=tuple(warnings))


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
