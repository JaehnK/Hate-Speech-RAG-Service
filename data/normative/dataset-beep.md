---
source_id: dataset-beep
title: "BEEP! Korean Corpus of Online News Comments for Toxic Speech Detection (Moon et al., SocialNLP 2020)"
publisher: Association for Computational Linguistics (ACL Anthology)
source_url: https://aclanthology.org/2020.socialnlp-1.4/
source_type: dataset_guideline
license_basis: cc_by_4.0
language: ko
version: SocialNLP 2020 (ACL workshop), pp. 25-31; 데이터 저장소 kocohub/korean-hate-speech README·영문 가이드라인 대조
retrieved_at: 2026-11-09
---

## 데이터 구성과 두 축의 주석 (사회적 편견 + 혐오 표현)
tags: dataset_overview, entertainment_news, bias_and_hate
categories:
level: label_scheme

BEEP!은 한국의 연예 뉴스 집계 플랫폼에 달린 댓글을 사람이 직접 라벨링한 한국어 유해 표현 말뭉치다. 공개된 라벨 데이터는 9,381개 댓글로, 학습 7,896개, 검증 471개, 테스트 974개로 나뉜다. 약 1만 개를 주석한 뒤 건너뛰었거나 합의에 이르지 못한 659개를 제외한 결과다. 댓글마다 주석자 3명이 라벨을 달고 다수결로 정했으며, 원문 기사 제목도 맥락 정보로 함께 공개했다.

각 댓글은 두 가지 측면에서 주석된다. 하나는 사회적 편견이 있는지(gender, others, none), 다른 하나는 혐오 표현의 정도(hate, offensive, none)다. 저자들은 혐오 표현이 사회적 편견과 밀접하게 연결되어 있다고 보고 두 축을 함께 주석했으며, 실제로 편견이 있는 댓글일수록 hate나 offensive일 가능성이 높았다고 보고한다. 주석자 간 일치도(Krippendorff's alpha)는 편견 3분류 0.492, 혐오 3분류 0.496이다.

연예 뉴스 댓글이라는 출처 특성상 표적은 대부분 연예인 등 공인 개인이며, 정치·사회 뉴스 댓글과는 표적 분포가 다르다.

분류 시 시사점: BEEP!의 예시를 참고할 때는 연예인 개인을 향한 공격이 많다는 점을 감안해, 개인 대상 모욕도 혐오로 보는 서비스 기준에서 `profanity` 등 공격 방식 category의 근거로 주로 활용한다.

## 혐오 표현 축: hate의 정의
tags: hate_definition, protected_attribute, severe_insult
categories: gender, age, identity, profanity
level: label_scheme

논문은 한국어에 사회적으로 합의된 혐오 표현 정의가 부족하다고 보고 YouTube, Facebook, Twitter의 혐오 표현 정책을 참고해 정의를 세웠다. hate에는 두 경우가 들어간다. 첫째, 다음 속성을 근거로 개인이나 집단에 대한 증오를 명시적으로 드러내는 경우다. 속성 목록은 생물학적 성, 젠더, 성적 지향, 성 정체성, 연령, 외모, 사회적 지위, 종교, 병역, 질병이나 장애, 민족, 출신 국가다. 둘째, 개인이나 집단을 심하게 모욕하거나 공격하는 경우로, 성희롱, 굴욕 주기, 비하가 포함된다.

저장소의 영문 가이드라인은 여기에 더해, 모욕은 상대의 사회적 지위를 심각하게 해칠 수 있는 표현을 뜻하고, 불쾌한 소문이나 사실을 퍼뜨리는 것, 나쁜 의도로 만든 신조어도 포함될 수 있다고 설명한다. 동시에 비속어가 들어 있다는 사실만으로 항상 이 범주가 되지는 않는다고 명시한다.

즉 BEEP!의 hate는 보호 속성 기반 증오와 속성과 무관한 심한 개인 모욕을 함께 포함한다. 이는 집단 혐오와 개인 대상 모욕을 모두 혐오로 보는 이 서비스와 같은 방향이다.

분류 시 시사점: 속성 기반 증오는 해당 속성 category(성별 `gender`, 연령 `age`, 종교·장애·민족·국적·성적 지향 `identity`)로, 속성과 무관한 심한 모욕은 `profanity` 또는 `other`로 분류하되 욕설 단어 존재만으로 판정하지 않는다.

## 혐오 표현 축: offensive와 none의 경계
tags: offensive_definition, sarcasm, rudeness, borderline
categories: profanity
level: label_scheme

논문은 Davidson 등(2017)의 논의를 따라 무례하거나 공격적인 댓글이 모두 hate는 아니라고 보고, hate에는 못 미치지만 개인이나 집단에게 질적으로 다른 방식으로 불쾌감을 주는 댓글을 offensive로 따로 분류했다. 경계는 세 가지다. 반어나 수사적 질문으로 비꼬는 경우, 의견을 비윤리적이거나 무례하고 거칠거나 교양 없는 방식으로 말하는 경우, 그리고 표현의 자유로 볼 여지를 남기면서 개인이나 집단을 암시적으로 공격하는 경우다. 이 경계에 해당하지 않으면 none이다.

영문 가이드라인은 offensive에 hate 수준은 아닌 비속어, 고인에 대한 농담 같은 비윤리적 표현, 확인되지 않은 소문 전달이 들어갈 수 있다고 덧붙인다. 라벨 분포는 hate 25.11%, offensive 32.66%, none 41.80%로 비교적 고르다.

BEEP!은 hate와 offensive를 구분하지만, 이 서비스는 개인이나 집단을 향한 모욕·욕설도 혐오로 판정한다. 따라서 BEEP!의 offensive 중 표적을 향한 비속어나 조롱은 서비스 기준에서는 혐오에 해당할 수 있다. 반면 표적 없는 거친 말투나 단순한 비꼼은 서비스의 공통 판정 문턱을 넘지 못할 수 있다.

분류 시 시사점: BEEP!의 offensive 사례는 표적을 향한 욕설·멸칭이 있으면 `profanity`로 혐오 판정하고, 대상 없는 거친 표현이나 가벼운 비꼼뿐이면 `unclassified` 또는 `no_target` 여부를 따로 판단한다.

## 사회적 편견 축: gender, others, none
tags: social_bias, gender_bias, stereotype
categories: gender, identity, age
level: label_scheme

사회적 편견은 특정한 사회적 특성을 가진 사람이나 집단에 대한 선입견적 평가 또는 편견으로 정의된다. 논문이 예로 드는 특성은 성별, 정치 성향, 종교, 외모, 연령, 장애, 인종 등이다. 연예 뉴스에서 공인이 마주하는 고정관념이 주로 성별과 얽혀 있다는 점을 반영해, 라벨을 gender(성별 관련 편견), others(그 밖의 편견), none(편견 없음) 세 가지로 나누고, 성별 편견 유무만 보는 이진 버전도 함께 제공한다. 성별 이진 라벨의 일치도는 0.767로 3분류보다 높다.

영문 가이드라인에 따르면 gender에는 성역할, 성적 지향, 성 정체성, 성별 관련 행위에 대한 편견이 들어간다. others는 성별 이외의 사회적 편견으로, 인종, 출신 배경, 국적, 민족, 정치 성향, 피부색, 종교, 장애, 연령, 외모, 재산, 직업, 그리고 한국 특유의 병역 미필 여부까지 포함한다.

편견 라벨은 혐오 정도와 별개의 축이다. 편견이 있어도 표현이 정중하면 none일 수 있고, 편견 없이 욕설만 있는 hate도 있다. 서비스에서는 편견이 드러나는 속성이 category 선택의 근거가 된다.

분류 시 시사점: 성역할 고정관념은 `gender`, 성적 지향·성 정체성은 `identity`로 나누고, others 계열은 속성에 따라 `identity`·`age`·정치 category·`other`로 옮기되 편견 표현만으로는 혐오 여부를 확정하지 않고 판정 문턱을 따로 확인한다.
