"""Turn cited document ids into readable sources for reports.

The classifier records cited definition documents by id (for example
`normative:kr-kcsc-info-review-rule:2:…`). Reports show the source title, the cited
section, its type and a link instead, looked up from the normative corpus shipped
with the app (data/normative). Unknown ids pass through unchanged.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.analysis.normative_corpus import DEFAULT_CORPUS_DIR, load_normative_documents

SOURCE_TYPE_LABELS = {
    "official_standard": "국내 법령·심의규정",
    "official_guideline": "국가인권위원회 기준",
    "international_summary": "국제 기준 요약",
    "platform_summary": "플랫폼 정책 요약",
    "dataset_guideline": "데이터셋 라벨 기준",
    "internal_taxonomy": "HateScope 분류 기준",
}


@lru_cache(maxsize=1)
def _normative_index(corpus_dir: str = DEFAULT_CORPUS_DIR) -> dict[str, dict[str, str]]:
    try:
        documents = load_normative_documents(corpus_dir)
    except (OSError, ValueError):
        return {}
    index = {}
    for document in documents:
        first_line = document.chunk_text.split("\n", 1)[0]
        section = first_line.split("] ", 1)[1] if "] " in first_line else first_line
        index[document.doc_id] = {
            "title": document.source_title,
            "section": section,
            "source_url": document.source_url or "",
            "source_type": document.document_type,
        }
    return index


def describe_citation(item: Any) -> dict[str, Any]:
    """Add title, section, source_url, source_type and source_label to a cited document."""
    if not isinstance(item, dict):
        return {"doc_id": str(item)}
    doc_id = str(item.get("doc_id") or "")
    enriched = dict(item)
    known = _normative_index().get(doc_id)
    if known:
        enriched.update(known)
    elif item.get("source_id") == "internal_taxonomy" or doc_id.startswith(("taxonomy:", "category:", "conflict:")):
        enriched.setdefault("source_type", "internal_taxonomy")
    source_type = enriched.get("source_type")
    if source_type in SOURCE_TYPE_LABELS:
        enriched["source_label"] = SOURCE_TYPE_LABELS[source_type]
    return enriched


def describe_citations(items: Any) -> list[dict[str, Any]]:
    return [describe_citation(item) for item in (items or [])]
