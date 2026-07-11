from __future__ import annotations

from hashlib import sha256

from app.analysis.models import DefinitionDocument


TAXONOMY_VERSION = "v0.2.0"
DEFAULT_DEFINITION_CORPUS_VERSION = "definition-corpus-2026-07-09-v0.2"

ALLOWED_CATEGORIES: tuple[str, ...] = (
    "gender",
    "age",
    "identity",
    "profanity",
    "state_authority",
    "non_state_authority",
    "state_regime",
    "non_state_regime",
    "state_community",
    "non_state_community",
    "no_target",
    "other",
    "unclassified",
)

POLITICAL_CATEGORIES: tuple[str, ...] = (
    "state_authority",
    "non_state_authority",
    "state_regime",
    "non_state_regime",
    "state_community",
    "non_state_community",
)

CATEGORY_DEFINITIONS: dict[str, str] = {
    "gender": "성별, 성역할, 가족 역할을 근거로 한 모욕, 비하, 차별 표현.",
    "age": "특정 연령대 또는 세대를 근거로 한 모욕, 비하, 차별 표현.",
    "identity": "출신지역, 인종, 국적, 종교, 성적지향, 장애 등 보호 속성 기반 표현.",
    "profanity": "직접적인 욕설, 비속어, 모욕적 호칭이 포함된 표현.",
    "state_authority": "국가 기관, 공직자, 공적 권위체를 표적으로 하는 정치 혐오 표현.",
    "non_state_authority": "정당, 정치인, 언론, 기업 등 비국가기관 권위체를 표적으로 하는 정치 혐오 표현.",
    "state_regime": "선거 제도, 법, 정책, 행정 절차 등 국가 시스템을 표적으로 하는 정치 혐오 표현.",
    "non_state_regime": "정당 경선, 내부 규칙, 비국가기관의 제도나 절차를 표적으로 하는 정치 혐오 표현.",
    "state_community": "국민, 국가 공동체, 특정 국가 구성원 전체를 표적으로 하는 정치 혐오 표현.",
    "non_state_community": "정치 지지층, 팬덤, 이념 집단, 온라인 정치 커뮤니티를 표적으로 하는 정치 혐오 표현.",
    "no_target": "혐오적 표현은 있으나 명시적 대상이 식별되지 않는 경우.",
    "other": "혐오표현으로 판단되지만 허용된 구체 카테고리에 넣을 수 없는 경우.",
    "unclassified": "혐오표현이 아니거나 카테고리 분류 대상이 아닌 경우.",
}


def build_internal_taxonomy_documents(
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
) -> list[DefinitionDocument]:
    documents = [
        _doc(
            doc_id="taxonomy:allowed_categories:0",
            tags=("taxonomy", "allowed_categories"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "MVP categories are: "
                + ", ".join(ALLOWED_CATEGORIES)
                + ". Choose only these category codes."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:non_hate_rule:0",
            tags=("taxonomy", "non_hate_rule"),
            related_categories=("unclassified",),
            chunk_text=(
                "비혐오 표현은 is_hate_speech=false, "
                'categories=["unclassified"], target_group=null, hate_type=null로 저장한다.'
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:other_rule:0",
            tags=("taxonomy", "other_rule"),
            related_categories=("other",),
            chunk_text=(
                "other는 혐오표현으로 판단되지만 구체 카테고리에 넣을 수 없을 때만 "
                "사용하며, 다른 category와 함께 사용할 수 없다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:political_axis:0",
            tags=("taxonomy", "political_axis", "political_category"),
            related_categories=POLITICAL_CATEGORIES,
            chunk_text=(
                "정치 혐오 카테고리는 대상 유형(authority, regime, community)과 "
                "행위자 성격(state, non_state)을 함께 판단해 여섯 정치 카테고리 중 "
                "하나 이상을 선택한다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="conflict:exclusive_categories:0",
            tags=("taxonomy", "conflict_rule"),
            related_categories=("other", "unclassified"),
            chunk_text=(
                "unclassified는 비혐오에만 사용한다. other는 혐오표현이지만 "
                "구체 카테고리로 분류할 수 없을 때 단독으로 사용한다."
            ),
            corpus_version=corpus_version,
        ),
    ]

    for category in ALLOWED_CATEGORIES:
        documents.append(
            _doc(
                doc_id=f"category:{category}:0",
                tags=("taxonomy", "category_card"),
                related_categories=(category,),
                chunk_text=f"{category}: {CATEGORY_DEFINITIONS[category]}",
                corpus_version=corpus_version,
            )
        )

    return documents


def _doc(
    doc_id: str,
    tags: tuple[str, ...],
    related_categories: tuple[str, ...],
    chunk_text: str,
    corpus_version: str,
) -> DefinitionDocument:
    return DefinitionDocument(
        doc_id=doc_id,
        source_id="internal_taxonomy",
        source_title=f"Hate Speech Category Taxonomy {TAXONOMY_VERSION}",
        source_url=None,
        publisher="internal",
        document_type="taxonomy_card",
        language="ko",
        normalized_language="ko",
        license_tier="internal",
        retrieval_tags=tags,
        related_categories=related_categories,
        chunk_text=chunk_text,
        chunk_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
        corpus_version=corpus_version,
    )
