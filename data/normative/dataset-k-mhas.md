---
source_id: dataset-k-mhas
title: "K-MHaS: A Multi-label Hate Speech Detection Dataset in Korean Online News Comment (Lee et al., COLING 2022)"
publisher: International Committee on Computational Linguistics (ACL Anthology 수록)
source_url: https://aclanthology.org/2022.coling-1.311/
source_type: dataset_guideline
license_basis: excerpt_quotation
language: ko
version: COLING 2022 Proceedings; 데이터 저장소 adlnlp/K-MHaS README 대조
retrieved_at: 2026-11-09
---

## 2층 주석 구조: 이진 분류와 8개 세부 다중 라벨
tags: multi_label, binary_classification, intersectionality, dataset_overview
categories:
level: label_scheme

K-MHaS는 2018년 1월부터 2020년 6월 사이의 한국어 온라인 뉴스 댓글 109,692개에 혐오 표현 라벨을 붙인 데이터셋이다. 주석 체계는 두 층으로 되어 있다. 먼저 혐오 표현(Hate Speech)인지 아닌지(Not Hate Speech)를 이진으로 나누고, 혐오 표현이면 8개 세부 범주로 나눈다. 세부 범주는 서로 배타적이지 않아서 한 댓글에 1개부터 4개까지 라벨을 붙일 수 있다. 저자들은 이 방식이 주관성과 교차성을 다루기 위한 것이라고 설명한다.

세부 범주 8개는 Politics(정치성향차별), Origin(출신차별), Physical(외모차별), Age(연령차별), Gender(성차별), Religion(종교차별), Race(인종차별), Profanity(혐오욕설)다. 각 언어의 혐오 표현은 사회·역사적 맥락이 다르다는 이유로 이 8개를 골랐으며, 특히 정치 범주는 한국 혐오 표현의 양상에 큰 영향을 준다는 이유로 포함했다. 이진 기준에서 혐오 표현은 45.7%, 비혐오는 54.3%이고, 혐오 표현 중 단일 라벨이 33.2%, 다중 라벨이 12.4%다.

라벨은 원어민 주석자 5명이 예비 라운드와 본 라운드를 거쳐 달았고, 불확실 사례는 5명이 함께 검토해 다수결로 정했다.

분류 시 시사점: 서비스도 `categories`에 복수 선택을 허용하므로, K-MHaS처럼 한 댓글에 서로 다른 공격 근거가 각각 있으면 여러 category를 함께 붙인다.

## 세부 라벨 정의 1: 정치·출신·인종·종교
tags: politics, origin, race, religion, protected_attribute
categories: identity
level: label_scheme

논문의 주석 지침은 각 세부 범주를 짧게 정의한다. Politics는 정치적 입장을 근거로 한 혐오 표현이다. Origin은 출신 지역이나 정체성을 근거로 한 혐오 표현이다. Race는 민족(ethnicity)을 근거로 한 혐오 표현이다. Religion은 종교를 근거로 한 혐오 표현이다. 주석자에게는 범주별 키워드나 그 대체 표현을 사회·문화·역사적 맥락 안에서 살피도록 했다.

라벨 분포를 보면 종교와 인종 범주가 가장 작은 비중을 차지한다. 저자들은 한국이 인종·종교 측면에서 비교적 단일한 사회라는 점과 연결해 해석한다. 저장소 예시에는 특정 지역 출신과 정치 성향을 동시에 비하하는 댓글이 Origin과 Politics 두 라벨을 함께 받은 사례가 있다.

서비스 category로 옮기면 Origin, Race, Religion은 모두 보호 속성 기반 표현이므로 `identity`에 대응한다. Politics는 대응이 단순하지 않다. 이 서비스는 정치적 표적을 국가·비국가, 권위체·제도·공동체로 나눈 6개 category로 세분하므로, K-MHaS의 Politics 하나가 이 중 무엇에 해당하는지는 실제 공격 대상(정당·정치인, 지지층, 제도 등)을 보고 따로 정해야 한다. 그래서 이 chunk의 categories에는 정치 category를 넣지 않았다.

분류 시 시사점: 지역·인종·민족·종교 근거 공격은 `identity`로 분류하고, 정치 성향 근거 공격은 지지층이면 `non_state_community`, 정당·정치인이면 `non_state_authority`처럼 공격받는 단위에 따라 정치 category를 고른다.

## 세부 라벨 정의 2: 외모·연령·성별
tags: physical, appearance, disability, age, gender, sexual_orientation
categories: gender, age, identity, profanity
level: label_scheme

Physical은 신체나 얼굴 같은 외모, 또는 장애를 근거로 한 혐오 표현이다. Age는 연령을 근거로 한 혐오 표현이다. Gender는 성별이나 성적 지향을 근거로 한 혐오 표현으로, 지침은 여성과 동성애자를 예로 든다. 지침은 경계 판단의 예도 제시한다. "여성"이라는 단어를 쓰는 것만으로는 혐오가 아니지만, 여성을 비난하거나 집단을 공격하는 언어를 쓰면 Gender로 분류한다.

이 정의들은 서비스 category와 일대일로 맞지 않는 부분이 있다. K-MHaS의 Gender는 성별과 성적 지향을 함께 묶지만, 서비스는 성별 집단 공격은 `gender`, 성적 지향·성소수자 공격은 `identity`로 나눈다. Physical도 외모와 장애를 함께 묶는데, 서비스에서는 장애가 `identity`에 속하고 외모는 정의된 속성이 아니라 `profanity` 후보다. Age는 `age`와 그대로 대응한다.

논문은 Gender 범주 댓글이 상대적으로 길다는 분석도 제시하며, 성별 기반 혐오가 폭넓게 쓰인다고 해석한다.

분류 시 시사점: 단어 언급만으로 판정하지 않고 집단을 비난·공격할 때만 해당 category를 붙이며, K-MHaS의 Gender·Physical 사례를 참고할 때는 성적 지향·장애를 `identity`로, 외모를 `profanity`로 분리한다.

## 세부 라벨 정의 3: Profanity(혐오욕설)
tags: profanity, swearing, residual_category, multi_label
categories: profanity, no_target
level: label_scheme

Profanity는 욕하기, 저주, 음란한 말, 비속어 형태의 혐오 표현을 뜻하며, 지침은 위의 다른 범주로 특정할 수 없는 혐오 표현도 이 범주에 넣도록 정의한다. 또한 혐오 표현은 다양하므로 욕설이나 저주 형태의 댓글은 모두 Profanity로 표시한다고 밝힌다. 그래서 다른 범주와 겹치는 일이 많다. 논문은 외모, 정치 성향, 성별을 한꺼번에 욕설로 공격하는 문장이 Physical, Politics, Gender, Profanity 네 라벨을 모두 받는 예를 든다.

라벨 분포에서 Profanity는 단일 라벨과 다중 라벨 모두에서 가장 많은 범주이며, 저자들은 이를 욕설이 혐오 표현 탐지에 핵심적이라는 신호로 해석한다. 상위 라벨 조합에도 Profanity와 Politics, Profanity와 Physical, Profanity와 Origin 등이 올라 있다.

이 구조는 서비스의 `profanity`가 공격 방식 category로서 표적 category와 함께 쓰인다는 설계와 같다. K-MHaS는 "다른 범주로 특정할 수 없는 혐오"까지 Profanity에 넣는데, 서비스의 `profanity`도 다른 category에 맞지 않는 공격을 함께 포함하므로 같은 방식이다.

분류 시 시사점: 욕설·비속어가 표적 공격을 강화하면 표적 category와 `profanity`를 함께 붙이고, 표적 없는 단독 욕설은 `profanity`와 `no_target`을 함께 쓰며, 다른 category에 맞지 않는 잔여 공격도 `profanity`로 보낸다.
