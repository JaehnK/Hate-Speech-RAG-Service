---
source_id: dataset-k-haters-paper
title: "K-HATERS: A Hate Speech Detection Corpus in Korean with Target-Specific Ratings (Park et al., Findings of EMNLP 2023)"
publisher: Association for Computational Linguistics (ACL Anthology)
source_url: https://aclanthology.org/2023.findings-emnlp.952/
source_type: dataset_guideline
license_basis: cc_by_4.0
language: ko
version: Findings of EMNLP 2023, pp. 14264-14278 (arXiv 2310.15439); 데이터 저장소 README·HuggingFace 공개본 대조
retrieved_at: 2026-11-09
---

## 표적별 공격성 평정 체계 (13개 평정 변수, 3점 척도)
tags: rating_scheme, likert, target_specific, rationale, dataset_overview
categories:
level: label_scheme

K-HATERS는 2021년 7~8월 네이버 뉴스의 정치, 사회, 세계 섹션 댓글을 중심으로 만든 한국어 혐오 표현 말뭉치로, 최종 192,158개 댓글로 구성된다. 학습·검증·평가는 172,158/10,000/10,000개로 나뉜다. 주석은 크라우드소싱으로 진행되었다.

이 데이터셋의 특징은 이진 라벨 대신 표적별 공격성 평정을 받았다는 점이다. 평정 변수는 13개다. 한국에서 대표적인 혐오 표적인 7개 보호 속성 집단(성별, 연령, 인종(출신), 종교, 정치, 직업, 장애)에 대한 공격성, 개인을 향한 공격 여부, 불특정 대상을 향한 공격 여부, 그리고 공격 방식을 나타내는 세부 평정 4개(모욕, 욕설, 외설·성희롱, 위협·폭력)다. 각 평정은 0~2의 3점 척도다. 0은 공격성 없음, 1은 약하거나 공격적일 가능성이 있는 표현으로 풍자, 고정관념, 편견 같은 암시적 혐오를 포함하며, 2는 독자가 불쾌하게 느낄 만한 분명히 유해한 표현이다. 주석자는 평정 근거가 된 공격 구간(offensiveness rationale)과 표적 구간(target rationale)도 표시했다.

부록 지침은 모욕을 대상의 가치와 사회적 평가를 깎아내리고 경멸감을 드러내는 표현으로 설명한다.

분류 시 시사점: 0과 2 사이의 약한 공격(풍자·고정관념)도 별도 등급으로 존재한다는 점을 기억하고, 서비스에서는 이런 암시적 표현이 표적을 일반화해 비하할 때만 판정 문턱을 넘는 것으로 본다.

## 4분류 라벨 정의: normal, offensive, L1 hate, L2 hate
tags: label_transformation, normal, offensive, l1_hate, l2_hate, implicit_hate
categories:
level: label_scheme

논문은 13개 평정을 4분류 공격 언어 범주와 다중 표적 라벨로 변환하는 방식을 제안하고, 공개 데이터셋도 이 변환 결과를 담고 있다. 변환 규칙은 다음과 같다. 모든 평정이 0이면 normal이다. 평정이 0보다 큰 항목이 있지만 보호 속성 집단을 향하지 않으면 offensive다. 보호 속성 집단을 향한 평정이 0보다 크면 hate이고, 이를 다시 두 단계로 나눈다. 보호 집단에 대한 최고 평정이 2이고 공격 구간이 표시되어 있으면 L2 hate, 최고 평정이 1이거나 공격 근거 구간이 없으면 L1 hate다. 저장소 README는 L2 hate를 보호 속성 집단을 향한 명시적 혐오, L1 hate를 더 암시적인 형태의 혐오로 요약한다.

전체 분포는 normal 27.1%, offensive 40.9%, L1 hate 11.4%, L2 hate 20.6%다. 공격적 표현이 포함된 댓글이 70%를 넘지만, 상당수는 표적을 특정할 수 없거나 보호 집단을 향하지 않아 offensive로 분류되었다. 혐오 61,444개 중 35.49%가 L1 hate로, 암시적 혐오의 비중이 작지 않다.

HuggingFace 공개본의 라벨 문자열은 `normal`, `offensive`, `L1_hate`, `L2_hate`다.

분류 시 시사점: L1 hate처럼 풍자·고정관념 형태의 암시적 집단 비하도 혐오 후보로 검토하되, 서비스 기준에서는 L1·L2 hate와 offensive를 모두 `is_hate_speech=true` 후보로 보고 차이는 category와 hate_type에 반영한다.

## 표적 라벨 목록과 서비스 category 대응
tags: target_label, protected_attribute, multi_label, label_naming
categories: gender, age, identity, other
level: label_scheme

표적 라벨은 해당 표적 평정이 0보다 크면 붙는 다중 라벨이며, 한 댓글에 최대 9개까지 가능하다. 논문이 제시하는 9개 표적은 성별, 연령, 인종(출신), 종교, 정치, 직업, 장애, 개인, 기타(불특정 대상)다. 부록 지침은 인종 항목을 인종/지역(Race/Region)으로, 정치를 정치 성향으로 적는다. 세부 평정 4개(모욕·욕설·외설·위협)는 표적 라벨에 들어가지 않는다.

라벨 이름은 문서마다 조금씩 다르다. 저장소 README는 gender, age, race, religion, politics, job, disability, individuals, others로 적지만, 로컬에 받은 HuggingFace 공개본의 실제 값은 `gender`, `age`, `region`, `religion`, `political`, `job`, `disabled`, `individual`, `others`다. 즉 공개 데이터에는 race 대신 region이 쓰인다. 공개본에서 가장 많은 표적은 individual, political, region 순이며, 논문도 이 말뭉치의 혐오가 주로 정치와 지역 관련 집단을 겨냥한다고 보고한다.

서비스 category로는 gender는 `gender`, age는 `age`, region(인종·출신 지역)·religion·disabled는 `identity`에 대응한다. job은 서비스가 정의하지 않은 속성이므로 `other` 후보다. political은 서비스의 정치 category가 더 세분되어 있어 지지층, 정당·정치인, 제도 중 실제 표적을 보고 정해야 하고, individual과 others는 표적의 지위에 따라 판단한다.

분류 시 시사점: K-HATERS의 political 사례는 하나의 category로 일괄 매핑하지 말고 공격받는 단위에 따라 `non_state_community`·`non_state_authority` 등으로 나누며, region은 `identity`로 처리한다.

## offensive와 hate의 분리 vs 이 서비스의 통합 판정
tags: offensive_vs_hate, protected_group, service_policy, boundary
categories: profanity, no_target
level: label_scheme

K-HATERS는 공격성의 표적이 보호 속성 집단인지에 따라 offensive와 hate를 엄격하게 나눈다. 7개 보호 속성(성별, 연령, 인종·출신, 종교, 정치, 직업, 장애)을 향한 공격만 hate이고, 특정 개인이나 불특정 대상을 향한 욕설·모욕은 강도가 높더라도 offensive에 머문다. 공개본 표적 중 individual이 가장 많다는 점을 보면, 개인을 향한 심한 욕설 상당수가 이 데이터셋에서는 hate가 아닌 offensive로 표시되어 있다. 반대로 K-HATERS는 정치와 직업을 보호 속성으로 포함하므로, 정치 집단을 향한 공격은 hate로 분류된다.

이 서비스는 이 구분을 따르지 않는다. 보호 집단에 대한 혐오뿐 아니라 개인이나 집단을 향한 모욕·욕설도 모두 `is_hate_speech=true`로 판정한다. 따라서 K-HATERS의 offensive 라벨을 서비스의 비혐오 정답으로 사용하면 안 된다. offensive 사례는 대개 서비스에서 `profanity`(표적이 없으면 `no_target` 병기)나 표적 category가 붙는 혐오 사례이며, 공격 표현이 전혀 없는 normal만 `unclassified`에 가깝다.

분류 시 시사점: K-HATERS 예시를 검색해 쓸 때 offensive·L1 hate·L2 hate를 모두 서비스의 혐오 후보로 다루고, 둘의 차이는 혐오 여부가 아니라 집단 표적 category를 붙일지 `profanity`·`no_target`만 붙일지의 차이로 해석한다.
