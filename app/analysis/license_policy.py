from __future__ import annotations

from collections.abc import Iterable


COMMERCIAL_OK = "commercial_ok"
SHAREALIKE_REVIEW = "sharealike_review"
LICENSE_REVIEW_REQUIRED = "license_review_required"
PERMISSION_REQUIRED = "permission_required"
INTERNAL_EVAL_ONLY = "internal_eval_only"

DEFAULT_EXAMPLE_LICENSE_TIERS: tuple[str, ...] = (COMMERCIAL_OK,)


def normalize_license_tier(license_status: str | None) -> str:
    status = (license_status or "").lower()
    if not status:
        return LICENSE_REVIEW_REQUIRED
    if "internal_eval" in status:
        return INTERNAL_EVAL_ONLY
    if "permission_required" in status or "approval_required" in status or "cc_by_nc" in status:
        return PERMISSION_REQUIRED
    if "cc_by_sa" in status:
        return SHAREALIKE_REVIEW
    if "cc_by_4_0" in status or "cc-by-4.0" in status:
        return COMMERCIAL_OK
    if "license_review_required" in status or "usage_restriction" in status:
        return LICENSE_REVIEW_REQUIRED
    return LICENSE_REVIEW_REQUIRED


def examples_allowed(
    source: dict,
    allowed_license_tiers: Iterable[str] = DEFAULT_EXAMPLE_LICENSE_TIERS,
) -> bool:
    corpus_target = source.get("corpus_target") or {}
    if corpus_target.get("examples") is not True:
        return False

    license_tier = normalize_license_tier(source.get("license_status"))
    return license_tier in set(allowed_license_tiers)
