from pathlib import Path

from app.analysis.llm_client import DEFAULT_ANTHROPIC_MODEL, DEFAULT_SYSTEM_PROMPT
from app.analysis.prompt_template import PROMPT_VERSION
from app.analysis.rag_classifier import DEFAULT_EXAMPLE_MIN_SIMILARITY
from app.analysis.taxonomy import (
    ALLOWED_CATEGORIES,
    DEFAULT_DEFINITION_CORPUS_VERSION,
    TAXONOMY_VERSION,
)
from app.analysis.vector_store import AUTHORITATIVE_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME, TAXONOMY_COLLECTION_NAME


def test_rag_reproducibility_doc_tracks_runtime_contract() -> None:
    document = Path("docs/19_rag_methodology_reproducibility.md").read_text(encoding="utf-8")

    expected_values = (
        PROMPT_VERSION,
        DEFAULT_ANTHROPIC_MODEL,
        DEFAULT_SYSTEM_PROMPT,
        DEFAULT_DEFINITION_CORPUS_VERSION,
        TAXONOMY_VERSION,
        TAXONOMY_COLLECTION_NAME,
        AUTHORITATIVE_COLLECTION_NAME,
        EXAMPLE_COLLECTION_NAME,
        f"score >= {DEFAULT_EXAMPLE_MIN_SIMILARITY:.2f}",
        *ALLOWED_CATEGORIES,
    )
    for value in expected_values:
        assert value in document
