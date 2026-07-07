# 혐오표현 정의 Corpus 수집 대상

| 항목 | 값 |
| --- | --- |
| 버전 | v0.1.0 |
| 작성일시 | 2026-07-08 08:44:59 KST |

## 문서 목적

이 문서는 `hate_speech_definitions` vector collection에 넣을 혐오표현 정의, 판단 기준, 보호 속성, 심각도 평가 기준 문서 후보를 정리한다.

목표는 댓글과 스크립트 분석 시 유사 혐오표현 예시뿐 아니라, 규범적 정의와 판단 기준을 함께 검색할 수 있게 하는 것이다.

## 수집 대상 기준

MVP seed corpus는 다음 기준을 우선한다.

- 공식 또는 준공식 기관이 공개한 문서
- 혐오표현 정의, 보호 속성, 심각도 판단 기준, 온라인 맥락의 대응 기준을 포함한 문서
- URL, 발행 기관, 발행일 또는 개정일을 metadata로 고정할 수 있는 문서
- 한국어 분석에 직접 도움이 되거나 한국어로 정규화 가능한 문서
- 단순 뉴스, 블로그 해설, paywall 논문은 MVP seed에서 제외

## 권장 Seed 구성

MVP의 첫 corpus version은 다음 7개 출처로 시작한다.

| 우선순위 | 출처 | 역할 | 수집 판단 |
| --- | --- | --- | --- |
| A | [국가인권위원회 혐오표현 리포트](https://www.humanrights.go.kr/site/program/board/basicboard/view?boardid=7604691&boardtypeid=17&menuid=001003001003004&pagesize=10&searchcategory=%EA%B8%B0%ED%83%80%EB%B0%9C%EA%B0%84%EC%9E%90%EB%A3%8C) | 국내 혐오표현 개념과 한국어 용어 기준 | 포함 |
| A | [KISO 혐오표현 자율정책 가이드라인](https://www.kiso.or.kr/%EC%A0%95%EB%B3%B4%EC%84%BC%ED%84%B0/kiso-%EC%A0%95%EC%B1%85/guideline/) | 인터넷서비스 적용 정의, 특정 속성, 차별 조장, 폭력 선동 기준 | 포함 |
| A | [지방정부 혐오표현 대응 안내서](https://www.gg.go.kr/humanrights/bbs/boardView.do?bIdx=110902905&bsIdx=785&menuId=3646) | 국내 실무 대응, 수준 판단, 구체 사례, 대응 원칙 | 포함 |
| A | [UN Strategy and Plan of Action on Hate Speech](https://digitallibrary.un.org/record/3889290) | 국제 기준, 혐오표현 대응 원칙, UN 문서 metadata 기준 | 포함 |
| A | [UN Detailed Guidance on Addressing Hate Speech](https://digitallibrary.un.org/record/3889286/files/UN_Strategy_and_PoA_on_Hate_Speech_Guidance_on_Addressing_in_field.pdf) | 3단계 심각도, Rabat threshold test, 비례 대응 기준 | 포함 |
| A | [OHCHR Rabat Threshold Test](https://www.ohchr.org/en/stories/2020/05/threshold-test-hate-speech-now-available-32-languages) | 맥락, 발화자, 의도, 내용, 전파 범위, 위해 가능성 평가 기준 | 포함 |
| A | [YouTube Hate Speech Policy](https://support.google.com/youtube/answer/2801939?hl=en) | YouTube 댓글 분석에 맞는 보호 속성 및 플랫폼 정책 기준 | 포함 |

## 보조 후보

다음 출처는 MVP seed 이후 보강 대상으로 둔다.

| 우선순위 | 출처 | 역할 | 수집 판단 |
| --- | --- | --- | --- |
| B | [Council of Europe CM/Rec(2022)16](https://www.coe.int/en/web/combating-hate-speech/recommendation-on-combating-hate-speech) | 혐오표현의 넓은 정의, 심각도 계층, 비례 대응 기준 | 보강 포함 |
| B | [CERD General Recommendation No. 35](https://www.refworld.org/legal/general/cerd/2013/101142) | 인종, 민족, 국적 기반 혐오표현 판단 기준 | 보강 포함 |
| B | [Meta Hateful Conduct Policy](https://transparency.meta.com/policies/community-standards/hateful-conduct/) | 플랫폼 정책 비교 기준 | 보강 후보 |
| B | [X Hateful Conduct Policy](https://help.x.com/en/rules-and-policies/hateful-conduct-policy) | 플랫폼 정책 비교 기준 | 보강 후보 |
| C | [TikTok 광고 정책의 차별, 괴롭힘, 따돌림 항목](https://ads.tiktok.com/help/article/discrimination-harassment-bullying) | 보호 속성과 금지 유형 비교 기준 | 일반 커뮤니티 정책 확인 후 보류 |

## 제외 기준

MVP seed에는 다음 자료를 넣지 않는다.

- 뉴스 기사
- Wikipedia 또는 2차 요약 문서
- 원문 접근이 불가능한 paywall 논문
- 혐오표현 정의가 아니라 사례 논평만 제공하는 글
- 특정 정치 사건에 대한 논평
- 실제 혐오표현 raw post 모음

실제 혐오표현 사례는 `hate_speech_examples` collection의 대상이며, 이 문서의 `hate_speech_definitions` collection과 분리한다.

## Corpus Version 제안

초기 version:

```text
definition-corpus-2026-07-08-v0.1
```

version 변경 기준:

- seed source 추가 또는 삭제: minor 증가
- source 원문 개정 반영: minor 증가
- metadata 오탈자 수정: patch 증가
- chunking 정책 변경: minor 증가
- embedding model 변경: corpus version은 유지하고 analysis run의 embedding model metadata로 구분

## Metadata Schema

각 source document는 다음 metadata를 가진다.

| 필드 | 설명 |
| --- | --- |
| `source_id` | 내부 source 식별자 |
| `title` | 문서 제목 |
| `publisher` | 발행 기관 |
| `source_url` | 원문 URL |
| `published_at` | 발행일 |
| `revised_at` | 개정일 또는 확인 가능한 최신 수정일 |
| `last_checked_at` | corpus 생성 시 확인일 |
| `language` | 원문 언어 |
| `document_type` | report, guideline, policy, treaty_body_guidance 등 |
| `priority` | A, B, C |
| `corpus_version` | corpus version |
| `license_status` | 사용 가능 여부 확인 상태 |

각 chunk는 다음 metadata를 가진다.

| 필드 | 설명 |
| --- | --- |
| `chunk_id` | 내부 chunk 식별자 |
| `source_id` | source document 식별자 |
| `section_title` | 원문 섹션 제목 |
| `chunk_text` | 검색 대상 텍스트 |
| `normalized_language` | 검색용 정규화 언어 |
| `protected_attributes` | 언급된 보호 속성 |
| `severity_factors` | 심각도 판단 요소 |
| `retrieval_tags` | definition, protected_attribute, severity, platform_policy 등 |

## Chunking 정책

- 원문 구조가 있는 문서는 제목, 조항, 절, 문답 단위로 먼저 나눈다.
- 한 chunk는 한 판단 기준 또는 한 정의를 중심으로 구성한다.
- 너무 긴 섹션은 300~700 token 수준으로 나눈다.
- overlap은 최소화한다.
- 영어 원문은 원문 metadata를 보존하고, 한국어 검색을 위해 별도 한국어 정규화 chunk를 만들 수 있다.
- 기계 번역 또는 요약 chunk는 원문을 대체하지 않고 `normalized_language=ko`로 표시한다.

## 저작권과 사용 정책

source가 공개되어 있어도 본문 저장, 재배포, embedding 저장 가능 여부는 별도 확인이 필요하다.

MVP 구현 전까지는 다음 원칙을 둔다.

- source URL과 metadata는 저장한다.
- 본문 chunk 저장은 license 또는 내부 사용 가능 여부 확인 후 수행한다.
- 보고서에는 긴 원문을 노출하지 않고 짧은 근거 요약과 source title, source URL만 표시한다.
- corpus 원문을 export 파일에 포함하지 않는다.

## 구현 전 확인 사항

- 국가인권위원회 PDF의 본문 저장과 embedding 사용 가능 범위
- KISO 가이드라인 본문 저장과 embedding 사용 가능 범위
- 영어 문서의 한국어 정규화 chunk 생성 방식
- platform policy를 최종 판단 기준으로 사용할지, 참고 기준으로만 사용할지
- source 개정 여부를 주기적으로 확인할지, 수동으로만 갱신할지

## 권장 결론

MVP에서는 국내 기준 3개, 국제 기준 3개, YouTube 정책 1개로 `definition-corpus-2026-07-08-v0.1`을 만든다.

이 corpus는 혐오표현 여부를 단독으로 결정하는 규칙 엔진이 아니라, LLM 분류가 참고할 정의, 보호 속성, 심각도 판단 기준, 플랫폼 맥락을 제공하는 검색 기반 근거 자료로 사용한다.
