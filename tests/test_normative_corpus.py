from pathlib import Path

import pytest

from app.analysis.license_policy import COMMERCIAL_OK, NONCOMMERCIAL_RESEARCH
from app.analysis.normative_corpus import NormativeCorpusError, load_normative_documents

FRONT = """---
source_id: {source_id}
title: 테스트 규정
publisher: 테스트 기관
source_url: https://example.test/rule
source_type: official_standard
license_basis: {basis}
---
"""
CHUNK = """
## 제1조: 차별 조장
tags: discrimination, protected_attribute
categories: {categories}
level: {level}

합리적 이유 없이 성별, 종교, 장애, 나이, 출신, 인종, 지역을 이유로 차별하거나 편견을 조장하는 내용은 유통할 수 없다. 분류 시 시사점: 집단 혐오로 본다.
"""


def _write(tmp_path: Path, name: str, basis="public_domain_statute", categories="gender, identity", level="group_hate"):
    (tmp_path / name).write_text(
        FRONT.format(source_id=name[:-3], basis=basis) + CHUNK.format(categories=categories, level=level),
        encoding="utf-8",
    )


def test_loads_chunks_with_metadata_and_skips_readme(tmp_path) -> None:
    _write(tmp_path, "rule.md")
    (tmp_path / "README.md").write_text("# not a source", encoding="utf-8")

    [document] = load_normative_documents(tmp_path)

    assert document.document_type == "official_standard"
    assert document.related_categories == ("gender", "identity")
    assert document.retrieval_tags[:2] == ("official_standard", "group_hate")
    assert document.chunk_text.startswith("[테스트 규정] 제1조: 차별 조장\n")
    assert "categories:" not in document.chunk_text
    assert document.license_tier == COMMERCIAL_OK


def test_noncommercial_sources_can_be_filtered_out(tmp_path) -> None:
    _write(tmp_path, "report.md", basis="public_work")

    assert load_normative_documents(tmp_path)[0].license_tier == NONCOMMERCIAL_RESEARCH
    assert load_normative_documents(tmp_path, allowed_license_tiers=(COMMERCIAL_OK,)) == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"categories": "gender, racism"}, "unknown categories"), ({"level": "severe"}, "unknown level")],
)
def test_rejects_invalid_chunk_metadata(tmp_path, kwargs, message) -> None:
    _write(tmp_path, "bad.md", **kwargs)

    with pytest.raises(NormativeCorpusError, match=message):
        load_normative_documents(tmp_path)


def test_repository_corpus_is_valid() -> None:
    documents = load_normative_documents("data/normative")

    assert documents
    assert len({document.doc_id for document in documents}) == len(documents)
