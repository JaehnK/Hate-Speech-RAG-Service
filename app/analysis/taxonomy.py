from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.analysis.models import DefinitionDocument


TAXONOMY_VERSION = "v0.3.0"
DEFAULT_DEFINITION_CORPUS_VERSION = "definition-corpus-2026-07-16-v0.3"

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

@dataclass(frozen=True)
class CategoryCard:
    name: str
    definition: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    boundary: str
    cues: tuple[str, ...]
    retrieval_tags: tuple[str, ...] = ()
    multi_label: bool = True


CATEGORY_CARDS: dict[str, CategoryCard] = {
    "gender": CategoryCard(
        name="성별",
        definition="성별, 생물학적 성, 성역할 또는 임신·출산·가족 역할을 이유로 사람이나 집단을 공격하는 표현.",
        include=("여성·남성 집단의 열등성이나 무가치를 일반화", "성별을 이유로 배제·차별·폭력을 정당화", "성역할을 따르지 않는다는 이유의 모욕·위협"),
        exclude=("공격이나 비하가 없는 성별 통계·정책 토론", "성별과 무관한 개인의 행동·성과 비판", "성적지향·트랜스젠더·비이분법 정체성만을 겨냥한 공격"),
        boundary="성별정체성·성적지향 공격은 identity를 우선하고, 성별 공격과 함께 나타나면 복수 선택한다.",
        cues=("여자·남자·엄마·아빠 등 성별·가족역할 지칭", "집단 일반화, 열등성, 배제, 성적 대상화"),
        retrieval_tags=("protected_attribute", "sex", "gender_role"),
    ),
    "age": CategoryCard(
        name="연령",
        definition="나이, 연령대 또는 세대 소속을 이유로 사람이나 집단을 공격하는 표현.",
        include=("청소년·노인·특정 세대 전체의 무능·해악을 일반화", "연령을 이유로 권리·참여 배제를 주장", "나이에 근거한 모욕적 호칭이나 위협"),
        exclude=("공격 없이 연령별 특성·정책 효과를 설명", "세대 정책이나 이해관계에 대한 구체적 비판", "나이와 무관한 개인 행동 비판"),
        boundary="세대 정치 지지 성향이 핵심 표적이면 non_state_community를 함께 검토한다.",
        cues=("노인·청년·10대·기성세대·특정 세대명", "나이 때문에 무능하다는 일반화, 세대 퇴출 주장"),
        retrieval_tags=("protected_attribute", "generation"),
    ),
    "identity": CategoryCard(
        name="정체성",
        definition="출신지역, 인종·민족, 국적, 종교, 성적지향, 성별정체성, 장애 등 보호 속성을 이유로 공격하는 표현.",
        include=("보호 속성 집단의 열등성·비인간화·위험성을 일반화", "해당 정체성을 이유로 배제·추방·차별·폭력을 주장", "집단을 겨냥한 멸칭이나 혐오 고정관념"),
        exclude=("공격이 없는 문화·종교·국적 정보", "정치 이념·정당·후보 지지층에 대한 공격", "직업·외모·취향처럼 이 taxonomy가 보호 속성으로 정하지 않은 표적"),
        boundary="국적·민족 정체성 공격은 identity, 시민·유권자라는 정치 공동체 공격은 state_community로 구분한다.",
        cues=("지역·민족·국적·종교·성소수자·장애 집단명", "오염·기생·추방·말살 등 비인간화와 배제 표현"),
        retrieval_tags=("protected_attribute", "race", "nationality", "religion", "disability", "sexual_identity"),
    ),
    "profanity": CategoryCard(
        name="욕설",
        definition="대상에게 직접 향하는 욕설, 비속어, 외설적 모욕 또는 모욕적 호칭이라는 표현 방식.",
        include=("사람·집단을 직접 부르는 욕설·멸칭", "다른 category 공격을 강화하는 노골적 비속어", "대상 없는 강한 욕설 자체가 분석 대상인 경우"),
        exclude=("보도·교육·비판 목적으로 욕설을 인용하고 동조하지 않는 경우", "대상을 공격하지 않는 단순 감탄·강조", "불쾌하지만 욕설·비속어에 해당하지 않는 의견"),
        boundary="표적 category와 함께 복수 선택할 수 있고, 식별 가능한 표적이 전혀 없으면 no_target을 함께 사용한다.",
        cues=("직접 욕설, 외설적 비유, 모욕적 별칭", "2인칭·집단명과 욕설의 결합"),
        retrieval_tags=("expression_form", "insult"),
    ),
    "state_authority": CategoryCard(
        name="국가 권위체",
        definition="국가기관 또는 공적 직무를 수행하는 공직자를 권위체로 표적화한 정치적 공격 표현.",
        include=("정부부처·국회·법원·수사기관 등 국가기관 전체를 비인간화·모욕", "대통령·장관·판사·경찰 등 공직자를 직무 집단으로 공격", "공적 권위체에 대한 위협·폭력·제거 선동"),
        exclude=("결정·수사·판결·업무에 대한 근거 있는 비판", "법·정책·선거 절차 자체를 표적으로 한 표현", "정당·후보·언론 등 비국가 권위체 공격"),
        boundary="누가 수행했는지가 표적이면 authority, 법·정책·절차가 표적이면 state_regime을 선택한다.",
        cues=("정부·국회·법원·검찰·경찰·공무원·현직 공직자", "기관·직무 집단을 향한 멸시, 제거, 폭력 주장"),
        retrieval_tags=("political_category", "state", "authority"),
    ),
    "non_state_authority": CategoryCard(
        name="비국가 권위체",
        definition="국가기관은 아니지만 정치적 의사결정·의제 설정 권한을 가진 조직이나 인물을 표적화한 공격 표현.",
        include=("정당·후보·정치인·당 지도부에 대한 집단적 모욕·위협", "언론사·기업·시민단체 지도부 등 비국가 권위체를 악의 집단으로 일반화", "비국가 조직 또는 지도자의 제거·폭력을 선동"),
        exclude=("특정 보도·공약·사업 결정에 대한 구체적 비판", "정당 지지자·팬덤·이념 집단 같은 일반 구성원 공격", "국가기관과 법률상 공직자 공격"),
        boundary="조직·지도자가 표적이면 authority, 지지자·구성원 집단이 표적이면 non_state_community를 선택한다.",
        cues=("정당·후보·정치인·언론사·기업 지도부", "조직 전체의 악성·무가치 일반화, 지도자 위협"),
        retrieval_tags=("political_category", "non_state", "authority"),
    ),
    "state_regime": CategoryCard(
        name="국가 제도",
        definition="국가가 운영하는 법, 정책, 선거·사법·행정 제도와 공식 절차를 표적으로 한 적대적 정치 표현.",
        include=("헌정·선거·사법·행정 제도 전체를 모욕적 대상으로 규정", "법·정책·공식 절차를 폭력적으로 파괴하거나 배제하자는 선동", "국가 제도 자체를 비인간적 악으로 단정하는 공격"),
        exclude=("정책의 효과·정당성·위헌성에 대한 비판과 개정 요구", "제도를 운용한 공직자·기관을 표적으로 한 공격", "정당·기업 등 비국가 조직의 내부 규칙 비판"),
        boundary="강한 반대만으로 분류하지 않고 모욕·비하·위협·파괴 선동 등 hate threshold를 충족해야 한다.",
        cues=("법·정책·헌법·선거제도·재판절차·행정절차", "제도 전체의 말살·파괴·오염 표현"),
        retrieval_tags=("political_category", "state", "regime"),
    ),
    "non_state_regime": CategoryCard(
        name="비국가 제도",
        definition="정당·언론·기업·시민단체 등 비국가 조직의 내부 규칙, 절차 또는 운영 체계를 표적으로 한 공격 표현.",
        include=("정당 경선·공천·당규 전체를 모욕하거나 파괴를 선동", "언론 편집 절차·플랫폼 운영 규칙·조직 내부 제도를 적대적 대상으로 공격", "비국가 절차 자체를 부패한 악으로 일반화"),
        exclude=("절차상 오류·불공정성에 대한 근거 있는 비판과 개선 요구", "비국가 조직·지도자 자체에 대한 공격", "국가의 법·정책·공식 행정 절차에 대한 공격"),
        boundary="조직은 non_state_authority, 조직의 규칙·절차는 non_state_regime으로 구분한다.",
        cues=("경선·공천·당규·편집규정·플랫폼규칙·내부절차", "절차 전체를 폐기·파괴·오염 대상으로 표현"),
        retrieval_tags=("political_category", "non_state", "regime"),
    ),
    "state_community": CategoryCard(
        name="국가 공동체",
        definition="국민, 시민, 유권자처럼 국가의 정치적 구성원이라는 지위로 묶인 공동체를 표적화한 공격 표현.",
        include=("국민·시민·유권자 전체를 무능·기생·배신 집단으로 일반화", "국가 구성원 집단의 권리 박탈·배제·폭력을 주장", "정치적 공동체 전체를 비인간화"),
        exclude=("국민 여론·투표 결과에 대한 기술과 비판", "특정 국적·민족 자체를 이유로 한 공격", "정당 지지층·이념 집단·팬덤 공격"),
        boundary="국적·민족 정체성이 이유면 identity, 시민·유권자라는 정치적 구성원 지위가 이유면 state_community다.",
        cues=("국민·시민·유권자·납세자 등 국가 구성원 명칭", "공동체 전체의 무가치 일반화와 권리 박탈 주장"),
        retrieval_tags=("political_category", "state", "community"),
    ),
    "non_state_community": CategoryCard(
        name="비국가 공동체",
        definition="정당 지지층, 정치 팬덤, 이념 집단, 운동 진영, 온라인 정치 커뮤니티를 표적화한 공격 표현.",
        include=("특정 후보·정당 지지자 전체를 열등·위험 집단으로 일반화", "이념·운동·팬덤 구성원의 배제·추방·폭력을 주장", "온라인 정치 커뮤니티 전체를 멸칭으로 공격"),
        exclude=("특정 주장·시위·댓글 행동에 대한 구체적 비판", "정당·후보·언론 등 조직이나 지도자 공격", "종교·국적·성별 등 보호 정체성 집단 공격"),
        boundary="조직·지도자는 non_state_authority, 지지자·일반 구성원은 non_state_community로 구분한다.",
        cues=("지지자·팬덤·좌파·우파·진영·온라인 커뮤니티명", "구성원 전체의 무지·악성·제거 필요성 일반화"),
        retrieval_tags=("political_category", "non_state", "community"),
    ),
    "no_target": CategoryCard(
        name="대상 없음",
        definition="공격적·혐오적 강도는 있으나 문맥에서 사람, 집단, 기관, 제도 등 표적을 식별할 수 없는 경우.",
        include=("대상 없이 단독으로 제시된 강한 욕설", "지시어의 선행 대상이 없어 누구를 겨냥했는지 복원할 수 없는 공격", "수집된 문맥만으로 표적을 특정할 수 없는 위협적 표현"),
        exclude=("대명사라도 앞 문맥에서 표적이 식별되는 경우", "집단명·기관명·제도명이 명시된 경우", "비혐오 또는 단순 감탄"),
        boundary="profanity와 함께 사용할 수 있지만 target category와 함께 사용할 수 없고 target_group은 null이어야 한다.",
        cues=("표적 명사와 복원 가능한 선행사가 없음", "독립 욕설·불특정 위협"),
        retrieval_tags=("fallback", "target_rule"),
    ),
    "other": CategoryCard(
        name="기타",
        definition="hate threshold는 충족하지만 현재 허용된 구체 category로 표적이나 근거 속성을 표현할 수 없는 경우.",
        include=("직업·외모·경제적 지위·취향 등 미정의 속성 집단에 대한 심각한 공격", "분명한 표적과 공격이 있으나 정치 2축이나 보호 속성에 해당하지 않음", "새로운 유형이라 taxonomy 확장 검토가 필요한 사례"),
        exclude=("기존 category로 설명 가능한 사례", "표적이 없는 경우", "비혐오·단순 비판·판단 불확실 사례"),
        boundary="최후 수단이며 반드시 단독으로 사용한다. 반복되는 other 표적은 taxonomy 개정 후보로 검토한다.",
        cues=("공격과 표적은 명확하지만 기존 category 근거가 없음", "미정의 집단 속성"),
        retrieval_tags=("fallback", "taxonomy_gap"),
        multi_label=False,
    ),
    "unclassified": CategoryCard(
        name="비혐오·미분류",
        definition="혐오표현이 아니거나 인용·비판·정보 전달 등으로 hate threshold를 충족하지 않는 경우.",
        include=("대상에 대한 구체적 행위·정책 비판", "혐오표현을 보도·연구·비판 목적으로 인용", "중립 정보, 질문, 모호하여 공격으로 확정할 수 없는 표현"),
        exclude=("집단 비인간화·열등성 일반화·배제·위협·폭력 선동", "명확한 직접 욕설이나 멸칭 공격", "hate threshold를 충족하는 category 사례"),
        boundary="is_hate_speech=false일 때만 단독 사용하며 target_group과 hate_type은 null이다.",
        cues=("사실 서술, 반대 의견, 정책 비판, 혐오 인용에 대한 거리두기", "공격의 대상·근거·행위가 불충분"),
        retrieval_tags=("non_hate", "fallback"),
        multi_label=False,
    ),
}

CATEGORY_DEFINITIONS: dict[str, str] = {code: card.definition for code, card in CATEGORY_CARDS.items()}


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
            doc_id="taxonomy:hate_threshold:0",
            tags=("taxonomy", "hate_threshold", "decision_rule"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "혐오·공격 판정 기준: 대상의 정체성·소속·지위 등을 근거로 열등성이나 무가치를 "
                "일반화하거나, 비인간화, 배제·차별, 위협·폭력, 제거·억압 선동, 직접적 심각한 "
                "모욕 중 하나 이상이 있어야 한다. 불쾌함, 반대, 풍자, 정책·행위 비판, 사실 서술만으로는 "
                "혐오로 분류하지 않는다. 명확하지 않으면 unclassified를 선택한다."
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
                "정치 category는 두 축을 순서대로 판단한다. 첫째, 국가기관·법률상 공직이면 state, "
                "정당·후보·언론·기업·시민단체 또는 그 구성원이면 non_state다. 둘째, 조직·지도자·공직자처럼 "
                "행위 주체가 표적이면 authority, 법·정책·선거·내부 규칙·절차가 표적이면 regime, 국민·유권자·"
                "지지층·팬덤·이념 집단 같은 일반 구성원이 표적이면 community다. 강한 정치적 반대나 정책 비판만으로는 "
                "부족하며 hate_threshold를 먼저 충족해야 한다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:context_exception:0",
            tags=("taxonomy", "context_rule", "quotation", "satire"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "문맥 예외: 뉴스 보도, 연구·교육, 반박·비판 목적으로 혐오표현을 인용하고 화자가 동조하지 않으면 "
                "인용된 욕설만으로 혐오로 판정하지 않는다. 풍자·반어는 문자 그대로만 읽지 말고 실제 공격 대상과 "
                "화자의 태도를 확인한다. 수집된 item만으로 태도나 대상을 확정할 수 없으면 unclassified를 선택한다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:multi_label_rule:0",
            tags=("taxonomy", "multi_label", "conflict_rule"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "복수 category는 서로 다른 근거가 각각 명시될 때만 선택한다. profanity는 공격 방식이므로 target category와 "
                "함께 사용할 수 있다. 보호 속성이 둘 이상이면 해당 category를 함께 선택할 수 있다. 같은 정치 표적을 "
                "authority와 community로 중복 선택하지 말고 실제 표적 단위를 우선한다. other와 unclassified는 항상 단독이다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:hate_type:0",
            tags=("taxonomy", "hate_type", "output_rule"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "hate_type은 표현 방식을 한국어로 요약한다. 권장 유형은 모욕·비하, 집단 일반화, 비인간화, "
                "배제·차별, 위협·폭력, 제거·억압 선동, 욕설이다. 여러 방식이 함께 있으면 핵심 1~2개를 "
                "슬래시로 결합하되 category code나 대상 이름을 hate_type에 반복하지 않는다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="taxonomy:target_group:0",
            tags=("taxonomy", "target_group", "output_rule"),
            related_categories=ALLOWED_CATEGORIES,
            chunk_text=(
                "target_group은 원문에서 공격받는 사람·집단·기관·제도명을 간결한 한국어 명사구로 기록한다. "
                "욕설을 제거하고 원문보다 넓은 집단으로 일반화하지 않는다. 대명사는 item 문맥에서 선행 대상이 "
                "명확할 때만 복원한다. no_target 또는 unclassified이면 null이다."
            ),
            corpus_version=corpus_version,
        ),
        _doc(
            doc_id="conflict:exclusive_categories:0",
            tags=("taxonomy", "conflict_rule"),
            related_categories=("other", "unclassified"),
            chunk_text=(
                "unclassified는 비혐오에만 단독 사용한다. other는 혐오표현이지만 구체 category로 분류할 수 없을 때 "
                "단독 사용한다. no_target은 표적이 없을 때만 사용하고 profanity 외 target category와 함께 사용할 수 없으며 "
                "target_group은 null이어야 한다."
            ),
            corpus_version=corpus_version,
        ),
    ]

    for category in ALLOWED_CATEGORIES:
        card = CATEGORY_CARDS[category]
        documents.append(
            _doc(
                doc_id=f"category:{category}:0",
                tags=("taxonomy", "category_card", category, *card.retrieval_tags),
                related_categories=(category,),
                chunk_text=_category_card_text(category, card),
                corpus_version=corpus_version,
            )
        )

    return documents


def _category_card_text(category: str, card: CategoryCard) -> str:
    multi_label = "허용" if card.multi_label else "단독 사용"
    return "\n".join(
        (
            f"카테고리: {category} ({card.name})",
            f"정의: {card.definition}",
            "포함 기준: " + " / ".join(card.include),
            "제외 기준: " + " / ".join(card.exclude),
            f"경계 규칙: {card.boundary}",
            "판단 단서: " + " / ".join(card.cues),
            f"복수 선택: {multi_label}",
        )
    )


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
