"""Public methodology: the exact prompt and models the worker uses.

The prompt is rendered from the same builder the classifier calls, with the
retrieved contexts replaced by placeholders, so what visitors read cannot drift
from what runs.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from app.analysis.analysis_tiers import available_tiers
from app.analysis.normative_corpus import load_normative_documents
from app.analysis.taxonomy import CATEGORY_CARDS, TAXONOMY_CATEGORY_CODES, TAXONOMY_VERSION, build_internal_taxonomy_documents
from app.analysis.prompt_template import AUTHORITATIVE_SLOTS, PINNED_TAXONOMY_IDS, build_category_prompt
from app.core.config import Settings

SOURCE_TYPE_NAMES = {
    "official_standard": "국내 법령·심의규정",
    "official_guideline": "국가인권위원회 기준",
    "international_summary": "국제 기준 요약",
    "platform_summary": "플랫폼 정책 요약",
    "dataset_guideline": "데이터셋 라벨 기준",
}
CONTEXT_PLACEHOLDERS = (
    "(검색한 분류 체계 항목 4개 + 항상 넣는 판정 기준 2개)",
    "(비슷한 사례의 유형으로 골라 찾은 법령·심의 기준 문서 7개)",
    "(의미가 가까운, 사람이 판정해 둔 사례 6개: 문장, 출처 데이터셋, 혐오 여부, 유형, 유사도)",
)
# The example index lives outside the web container (usearch files on the worker disk),
# so its size is recorded here from the loader inventory (docs/40_public_artifact_inventory.md).
EXAMPLE_CORPUS = {"label": "K-HATERS 학습용 데이터", "count": 172_157}


def render_prompt_preview(prompt_version: str) -> str:
    prompt = build_category_prompt(
        "<분석할 댓글·답글·자막 문장>", "comment", (), (), (), prompt_version=prompt_version
    )
    for placeholder in CONTEXT_PLACEHOLDERS:
        prompt = prompt.replace("(empty)", placeholder, 1)
    return prompt


def _pinned_cards(prompt_version: str) -> list[dict[str, str]]:
    pinned = PINNED_TAXONOMY_IDS.get(prompt_version, ())
    documents = {doc.doc_id: doc for doc in build_internal_taxonomy_documents()}
    return [{"doc_id": doc_id, "text": documents[doc_id].chunk_text} for doc_id in pinned if doc_id in documents]


def taxonomy_categories() -> list[dict[str, Any]]:
    """The categories the classifier may output now, straight from the cards it reads."""
    categories = []
    for code in TAXONOMY_CATEGORY_CODES:
        card = CATEGORY_CARDS[code]
        categories.append(
            {
                "code": code,
                "name": card.name,
                "definition": card.definition,
                "include": list(card.include),
                "exclude": list(card.exclude),
            }
        )
    return categories


@lru_cache(maxsize=1)
def corpus_sizes() -> dict[str, Any]:
    """Counts of what retrieval searches, computed from the same loaders ingest uses."""
    try:
        normative = load_normative_documents()
        normative_chunks: int | None = len(normative)
        normative_sources: int | None = len({doc.source_id for doc in normative})
    except (OSError, ValueError):
        normative_chunks = normative_sources = None
    return {
        "taxonomy_items": len(build_internal_taxonomy_documents()),
        "normative_chunks": normative_chunks,
        "normative_sources": normative_sources,
        "examples": EXAMPLE_CORPUS["count"],
        "example_source": EXAMPLE_CORPUS["label"],
    }


def build_methodology_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/methodology", tags=["methodology"])

    @router.get("")
    def methodology() -> dict[str, Any]:
        version = settings.rag_prompt_version
        slots = AUTHORITATIVE_SLOTS.get(version, ())
        return {
            "prompt_version": version,
            "prompt": render_prompt_preview(version),
            "pinned_cards": _pinned_cards(version),
            "taxonomy": {"version": TAXONOMY_VERSION, "categories": taxonomy_categories()},
            "corpus": corpus_sizes(),
            "retrieval": {
                "taxonomy_k": 4,
                "example_k": 6,
                "authoritative_slots": [
                    {
                        "source_type": slot[0],
                        "label": SOURCE_TYPE_NAMES.get(slot[0], slot[0]),
                        "count": slot[1],
                        "guided_by_examples": bool(slot[2]) if len(slot) > 2 else False,
                    }
                    for slot in slots
                ],
            },
            "models": {
                "classifier": sorted({tier.model for tier in available_tiers(settings)}),
                "embedding": f"Upstage {settings.embedding_model}",
                "prefilter": {"model": settings.jev_model, "threshold": settings.jev_threshold}
                if settings.jev_prefilter_enabled
                else None,
            },
            "tiers": [tier.public() for tier in available_tiers(settings)],
        }

    return router
