# 상세 Taxonomy v0.3 적용 기록

## 작업 범위

- 브랜치: `feat/detailed-taxonomy-v03`
- taxonomy version: `v0.3.0`
- definition corpus version: `definition-corpus-2026-07-16-v0.3`
- 목표: 13개 category의 정의만 있던 내부 card를 실제 판정에 필요한 포함·제외·경계·검색 단서까지 확장하고, 화면·문서·validator·vector corpus를 같은 계약으로 맞춘다.

## 구현 순서

1. `app/analysis/taxonomy.py`의 허용 code와 운영 문서를 대조했다.
2. 13개 category마다 한국어 이름, 정의, 포함 기준 3개, 제외 기준 3개, 인접 category 경계, 검색 cue와 복수 선택 여부를 구조화했다.
3. 공통 hate threshold, 인용·풍자 예외, 정치적 2축, 복수 선택, `hate_type`, `target_group`을 포함해 내부 규칙 card를 5개에서 10개로 확장했다.
4. `no_target`이 표적 category와 충돌하거나 `target_group`을 가진 경우 validator가 재시도하도록 했다.
5. 새 run의 `analysis_config.retriever_config.taxonomy_version`에 실제 taxonomy version을 저장하도록 했다.
6. `/rag-methodology`에 13개 category의 포함 기준과 제외·경계를 공개하고 사회과학·재현 섹션 번호를 재정렬했다.
7. `docs/11`, `docs/12`, `docs/13`, `docs/19`의 corpus와 판정 계약을 코드 기준으로 동기화했다.
8. corpus reset 과정에서 발견한 K-HATERS 공백-only row 1건을 loader에서 제외하고 regression test를 추가했다.
9. production Upstage embedding 재생성을 시작했으나 legacy Embed 종료와 Embed 2 가격 정책을 확인한 뒤 전체 적재를 중단했다.
10. vector store 재생성은 Embed 2 model ID·품질 평가·blue/green 전환안이 확정되는 후속 작업으로 보류했다.

## 판정 구조

### 공통 문턱

열등성·무가치 일반화, 비인간화, 배제·차별, 위협·폭력, 제거·억압 선동, 심각한 직접 모욕 중 하나 이상이 있어야 혐오 category를 선택한다. 불쾌함, 반대, 사실 서술, 정책·행위 비판만으로는 혐오로 분류하지 않는다.

### Category 집합

- 보호 속성·표현 방식: `gender`, `age`, `identity`, `profanity`
- 정치적 표적 2축: `state/non_state × authority/regime/community`
- 표적·잔여 판단: `no_target`, `other`, `unclassified`

`profanity`는 표현 방식이므로 다른 표적 category와 복수 선택할 수 있다. `no_target`은 `profanity` 외 표적 category와 함께 쓸 수 없고 `target_group`은 null이어야 한다. `other`와 `unclassified`는 항상 단독이다.

## Corpus 마이그레이션 보류

처음에는 collection을 reset했으나, 현재 `solar-embedding-1-large`가 속한 Embed 서비스가 2026-08-31 UTC 종료 예정임을 확인해 legacy 전체 재생성을 중단했다. Embed 2는 2026-07-20 UTC까지 무료이고 이후 1M token당 USD 0.02로, legacy USD 0.10의 5분의 1이다(VAT 별도).

새 모델의 vector는 legacy vector와 같은 공간으로 간주할 수 없으므로 기존 collection에 혼합하지 않는다. 후속 작업에서 정확한 Embed 2 API model ID를 공식 Console 문서로 확정하고, 고정 query 평가와 별도 collection 전량 재색인 후 blue/green 전환한다.

이전 analysis run은 당시 저장된 prompt/corpus 설정을 보존한다. 새 run부터 `definition-corpus-2026-07-16-v0.3`과 `retriever_config.taxonomy_version=v0.3.0`을 기록한다.

## 검증 기준

- 허용 category 13개와 구조화 card key가 정확히 일치한다.
- 내부 문서는 규칙 10개 + category 13개로 총 23개다.
- 모든 category chunk에 정의, 포함 기준, 제외 기준, 경계 규칙, 판단 단서가 존재한다.
- `no_target` 충돌 payload는 실패하고 `no_target + profanity + null target`은 통과한다.
- 방법론 화면에 새 corpus version, 공통 threshold와 13개 상세 card가 표시된다.
- Ruff, backend 전체 test, frontend 전체 test와 production build가 통과한다.
- Embed 2 전환 전에는 legacy 전체 적재를 재개하지 않는다.

## 검증 결과

- Ruff: 통과
- taxonomy/validator/document/loader 집중 test: `20 passed`
- backend 전체 test: `99 passed, 1 skipped`
- frontend test: `11 passed`
- frontend production build: 통과
- Upstage 가격·종료 일정: 공식 API 가격표와 교차 확인, 방법론 화면에 출처 링크 포함
- legacy Chroma 전체 재생성: 중단·보류. Embed 2 전환 후 별도 검증 예정
