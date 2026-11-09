---
source_id: dataset-kold
title: "KOLD: Korean Offensive Language Dataset (Jeong et al., EMNLP 2022)"
publisher: Association for Computational Linguistics (ACL Anthology)
source_url: https://aclanthology.org/2022.emnlp-main.744/
source_type: dataset_guideline
license_basis: cc_by_4.0
language: ko
version: EMNLP 2022 main conference (arXiv 2205.11315)
retrieved_at: 2026-11-09
---

## KOLD의 "공격적 표현" 정의와 3단계 계층 구조
tags: offensive_definition, hierarchical_annotation, olid
categories: profanity
level: label_scheme

KOLD는 NAVER 뉴스와 YouTube 영상의 제목·댓글에서 수집한 40,429개 댓글에 라벨을 붙인 한국어 공격적 표현 데이터셋이다. 수집 기간은 2020년 3월부터 2022년 3월까지이며, 공격적 댓글이 드물기 때문에 사전에 정한 키워드로 기사와 영상을 골랐다. 주석자에게는 기사나 영상 제목을 맥락으로 함께 보여 주었다.

라벨 체계는 영어 OLID의 다층 구조를 따른다. Level A는 공격적(OFF)인지 아닌지(NOT), Level B는 공격의 표적 유형, Level C는 표적 집단을 정한다. 논문은 대상 없는 욕설이든, 모욕이나 위협처럼 표적이 있는 공격이든, 명시적이든 암시적이든 어떤 형태라도 포함하면 공격적인 댓글로 본다. 정답 라벨은 주석자 3명의 다수결로 정하고, 결정되지 않으면 검수자가 판정했다. 전체 데이터 중 공격적 댓글은 20,130개로 약 절반이다.

이 정의는 혐오 집단 여부와 무관하게 욕설과 모욕까지 넓게 공격적 표현으로 묶는다는 점에서, 집단 혐오와 개인·집단 대상 모욕·욕설을 모두 혐오로 판정하는 이 서비스의 기준과 범위가 비슷하다.

분류 시 시사점: KOLD의 OFF 라벨은 서비스의 `is_hate_speech=true`와 대체로 대응하는 넓은 기준으로 참고하되, NOT이면서 정책 비판만 있는 사례는 `unclassified` 근거로 쓴다.

## Level B: 표적 유형 (Untargeted / Individual / Group / Others)
tags: target_type, untargeted, individual, group, cyberbullying
categories: no_target, profanity
level: label_scheme

Level B는 공격적 댓글의 표적 유형을 네 가지로 나눈다. 첫째, Untargeted(UNT)는 특정 표적이 없는 공격적 댓글로, 논문은 대상 없는 욕설과 비속어가 여기에 속한다고 설명한다. 둘째, Individual(IND)은 특정 개인을 향한 공격으로, 유명인이나 글에서 구체적으로 가리키는 이름 있는·없는 개인을 포함하며 논문은 이를 사이버 괴롭힘으로 분류한다. 셋째, Group(GRP)은 성별이나 종교처럼 보호되는 특성을 공유하는 사람들의 집단을 향한 공격으로, 일반적으로 혐오 표현으로 간주된다. 넷째, Others(OTH)는 위 두 유형에 속하지 않는 표적, 즉 조직, 회사, 사건 등을 향한 공격이다.

KOLD 통계에서 공격적 댓글 20,130개 가운데 UNT는 2,596개이고, 표적이 있는 공격 중에서는 GRP가 70.1%로 가장 많고 IND가 22.0%로 뒤를 잇는다.

서비스 category와 맞춰 보면 UNT는 `no_target`(욕설이면 `profanity` 병기)에, IND는 대상 개인의 지위와 공격 방식에 따라 `profanity` 또는 정치 표적 category에, OTH의 조직·기업 표적은 정당·언론·기업을 포함하는 `non_state_authority` 등에 대응할 수 있다.

분류 시 시사점: 표적 유형이 무엇이든 공격성이 있으면 혐오로 판정하고, UNT는 `no_target`, GRP는 Level C 속성에 맞는 category로 옮기며 개인·조직 표적은 실제 공격받는 단위에 따라 category를 고른다.

## Level C: 표적 집단 속성과 세부 집단
tags: target_group, protected_attribute, korean_context, multi_group
categories: gender, identity, age, non_state_community, other
level: label_scheme

Level C는 GRP로 분류된 댓글의 구체적 표적을 두 단계로 정한다. 상위는 표적 집단 속성, 하위는 표적 집단이다. 논문 부록 표에 실린 구성은 다음과 같다. 성별 및 성적 지향(LGBTQ+, 남성, 여성), 인종·민족·국적(아시아인, 흑인, 중국인, 인도인, 조선족, 동남아시아인, 백인), 정치 성향(보수, 진보), 종교(불교, 천주교, 기독교, 이슬람), 기타(연령차별, 장애인, 질병, 페미니스트, 외모, 사회경제적 지위)다. 중국인·조선족·인도인은 초기 1,000개 표본 분석에서 비중이 커서 한국 맥락에 맞게 추가했다. 한 댓글이 여러 집단을 겨냥하면 복수 집단을 붙일 수 있는데, 논문은 페미니스트 여성을 비하하는 멸칭이 여성과 페미니스트 두 집단을 동시에 겨냥하는 예를 든다. 페미니스트는 성별의 하위가 아니라 이념을 공유하는 집단으로 보아 기타에 넣었다.

서비스 category로 옮기면 남성·여성은 `gender`, LGBTQ+는 `identity`, 인종·민족·국적과 종교, 장애인은 `identity`, 연령차별은 `age`, 보수·진보 지지 집단은 이념 집단이므로 `non_state_community`에 대응한다. 외모·사회경제적 지위·질병은 서비스 taxonomy에 정의되지 않은 속성이므로 `other` 후보다.

분류 시 시사점: 한 댓글이 성별과 이념을 함께 겨냥하면 복수 category를 허용하는 KOLD 방식처럼 `gender`와 `non_state_community`를 각각의 근거가 있을 때 함께 선택한다.

## 공격 구간(offensive span)과 표적 구간(target span) 주석
tags: span_annotation, rationale, implicit_offense, explainability
categories:
level: label_scheme

KOLD는 범주 라벨과 함께 판단 근거가 되는 텍스트 구간을 표시한다. 공격 구간은 댓글이 왜 공격적인지를 정당화하는 부분, 즉 근거(rationale)다. 명시적 욕설뿐 아니라 풍자나 은유 같은 암시적 공격 표현도 포함하며, 공격성이 여러 문장에 걸쳐 있으면 모두 표시한다. 근거의 충실성을 고려해, 공격 구간은 아주 약한 공격성이라도 전달하는 모든 표현을 포함하면서도 필요한 만큼만 담은 최소 구간으로 정의한다. 접사나 이모지도 공격성을 담고 있으면 포함한다.

표적 구간은 공격 대상을 가리키는 문자 구간으로, 개인·집단·기타 표적 유형 모두에서 수집한다. 표적을 가리키는 단어 자체가 멸칭이면 공격 구간과 겹칠 수 있다. 논문은 중국인을 비하하는 한국어 멸칭을 예로 든다. 정답 구간은 주석자 3명 중 2명을 넘는 사람이 표시한 문자 위치로 정했다.

이 구조는 분류기가 판정 근거를 설명할 때 어떤 표현이 공격성을 만들고 어떤 표현이 표적을 지시하는지 분리해서 서술하는 데 참고할 수 있다.

분류 시 시사점: reasoning에는 공격 구간(욕설·풍자·멸칭)과 표적 구간(누구를 가리키는지)을 나눠 적고, 표적 지시어 자체가 멸칭이면 `profanity`와 표적 category를 함께 붙이는 근거로 삼는다.
