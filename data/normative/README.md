# 규범·기준 문서 corpus

`hate_speech_authoritative` collection에 적재하는 외부 기준 문서다. 혐오 여부의 판정 기준은 내부 taxonomy(`hate_threshold`)가 정하고, 이 corpus는 판정 근거를 대고 경계 사례를 설명하는 데 쓴다.

## 파일 형식

파일 하나가 출처 하나다. 맨 위 front matter에 출처 metadata를 두고, `## ` 제목마다 한 chunk로 적재한다.

```markdown
---
source_id: kr-network-act-44-7
title: 정보통신망 이용촉진 및 정보보호 등에 관한 법률 제44조의7
publisher: 국회 (국가법령정보센터 제공)
source_url: https://www.law.go.kr/...
source_type: official_standard
license_basis: public_domain_statute
language: ko
version: 2026.1.6 개정, 2026.7.7 시행
retrieved_at: 2026-11-09
---

## 제44조의7 제1항 제2호의2: 차별·증오 조장 정보
tags: protected_attribute, incitement, dignity
categories: identity, gender, age
level: incitement

본문...
```

- chunk 첫 줄들의 `tags:`, `categories:`, `level:`은 metadata이고 본문에 포함하지 않는다.
- `categories`는 서비스 category code(`gender, age, identity, profanity, state_authority, ...`)만 쓴다. 해당 없으면 비운다.
- 한 chunk는 300~1,200자 정도로, 한 가지 기준이나 정의만 다룬다.

## source_type

| 값 | 의미 | 예 |
| --- | --- | --- |
| `official_standard` | 국내 법령·심의규정 원문 | 정보통신망법, 방미심위 정보통신심의규정 |
| `official_guideline` | 국가기관 발간 보고서·안내서 | 국가인권위원회 연구보고서·안내서 |
| `international_summary` | 국제·해외 기준의 직접 작성 요약 | Rabat Plan, UN 전략, 해외 법제 |
| `platform_summary` | 플랫폼 정책의 직접 작성 요약 | YouTube 증오 표현·괴롭힘 정책 |
| `dataset_guideline` | 공개 데이터셋 라벨 기준 | K-HATERS, KOLD, BEEP 논문·README |

## level

| 값 | 의미 |
| --- | --- |
| `incitement` | 처벌 대상 수준: 폭력·차별 선동, 증오 조장 |
| `group_hate` | 집단 혐오: 속성을 이유로 한 비하·멸시·차별 표시 |
| `offensive` | 공격적 표현: 개인·집단을 향한 모욕·욕설·조롱 |
| `context_rule` | 판단 방법: 맥락, 예외, 경계, 심각도 판단 요소 |
| `label_scheme` | 데이터셋 라벨 정의 |

## license_basis

| 값 | 근거 |
| --- | --- |
| `public_domain_statute` | 법령·규칙 원문. 저작권법 제7조상 보호받지 않는 저작물 |
| `public_work` | 국가기관 공표 저작물(저작권법 제24조의2). 판정에 필요한 부분만 발췌·요약 |
| `own_summary` | 원문을 복제하지 않고 직접 작성한 요약. 출처 표기 |
| `cc_by_4.0` | CC BY 4.0 문서. 출처 표기 |
| `excerpt_quotation` | 원 저작권 유지 문서의 짧은 인용·요약(저작권법 제28조) |

비영리 연구 목적의 개인 프로젝트 기준이다. 상업화하면 `public_work`·`excerpt_quotation`의 이용 범위를 다시 확인한다.
