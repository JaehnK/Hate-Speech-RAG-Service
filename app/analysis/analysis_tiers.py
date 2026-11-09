"""User-selectable analysis tiers: which model classifies, and whether Jev pre-filters.

Accuracy and cost figures come from the public benchmark runs in docs/49; they are
shown to users as guidance, so update them only from a new measured run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.config import Settings
from app.core.errors import DomainError


@dataclass(frozen=True)
class AnalysisTier:
    key: str
    label: str
    summary: str
    model: str
    model_label: str
    jev_prefilter: bool
    benchmark_accuracy: float | None
    benchmark_f1: float | None
    usd_per_1000_comments: float | None

    def public(self) -> dict:
        return asdict(self)


# Figures from the held-out benchmark (970 items, docs/49). Sonnet 5.5 scored
# F1 0.830 vs 0.818 at 17x the cost (difference not significant), so larger models are
# not offered.
TIERS: dict[str, AnalysisTier] = {
    tier.key: tier
    for tier in (
        AnalysisTier(
            key="economy",
            label="절약",
            summary="문제없는 게 확실한 댓글은 경량 모델이 먼저 걸러내고, 나머지만 AI가 분석합니다.",
            model="claude-haiku-5-5",
            model_label="Jev 1.14 + Claude Haiku 5.5",
            jev_prefilter=True,
            benchmark_accuracy=0.767,
            benchmark_f1=0.818,
            usd_per_1000_comments=1.25,
        ),
        AnalysisTier(
            key="standard",
            label="기본",
            summary="모든 댓글을 AI가 분류 기준, 공식 규범 문서, 유사 사례를 참고해 분석합니다.",
            model="claude-haiku-5-5",
            model_label="Claude Haiku 5.5",
            jev_prefilter=False,
            benchmark_accuracy=0.767,
            benchmark_f1=0.818,
            usd_per_1000_comments=1.45,
        ),
    )
}
DEFAULT_TIER = "standard"


def available_tiers(settings: Settings) -> list[AnalysisTier]:
    return [tier for tier in TIERS.values() if not tier.jev_prefilter or settings.jev_prefilter_enabled]


def resolve_tier(key: str | None, settings: Settings) -> AnalysisTier:
    tier = TIERS.get(key or DEFAULT_TIER)
    if tier is None or tier not in available_tiers(settings):
        raise DomainError("ANALYSIS_TIER_UNAVAILABLE", "선택한 분석 단계를 사용할 수 없습니다.", status_code=422)
    return tier
