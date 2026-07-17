# 댓글 RAG 근거 UI와 한·영 corpus 사전 감사

## 작업 계약

| 항목 | 값 |
| --- | --- |
| 작업일 | 2026-07-17 |
| 브랜치 | `feat/comment-evidence-corpus-audit` |
| UI 대상 | 보고서의 `전체 혐오 댓글` card |
| 감사 대상 | production Chroma 정의·사례 collection, source manifest·loader, 공개 sample citation |
| 감사 방식 | 읽기 전용 전수 metadata·본문 집계 및 DB citation ID 대조 |

이번 작업은 한·영 버전의 구현 계획을 먼저 확정하지 않는다. UI 번역과 영어 입력 분석은 요구되는 corpus가 다르므로, 현재 적재 문서가 어느 범위까지 적합한지 먼저 판정한다.

## 댓글 근거 UI

댓글 분석 API는 이미 다음 값을 반환하고 있었지만 frontend type과 card가 사용하지 않았다.

- `reasoning`
- `target_group`, `hate_type`
- `rag_context_status`
- `similar_cases_used`
- `definition_docs_used`

DB/API 변경 없이 `article.case-card` 내부를 native `details/summary`로 구성했다. 댓글 영역을 클릭하면 분석 사유, 공격 대상, 표현 유형, RAG 문맥 상태와 결과에 기록된 문서 ID를 확인할 수 있다. keyboard와 screen reader가 기본 toggle semantics를 사용할 수 있고, mobile에서는 3열 metadata를 1열로 바꾼다.

문서 ID는 현재 모델 JSON 응답에 저장된 값이다. 검색 후보의 canonical snapshot이 아니므로 UI는 이를 “기록된 인용”으로 표현하고, 유사 사례가 법적·최종 판단 근거가 아니라는 경계를 함께 표시한다.

## live vector store 전수 결과

### 정의 collection

| 항목 | 결과 |
| --- | --- |
| 전체 | 31건 |
| 내부 taxonomy | 23건(공통 규칙 10, category card 13) |
| K-HATERS README chunk | 8건 |
| 중복 chunk hash | 0건 |
| 길이 | 최소 71, 중앙값 372, 최대 1,215자 |
| metadata language | `ko` 31건 |
| 실제 문자 | 한국어+category code 혼합 23건, 영문-only 8건 |
| collection metadata | `hnsw:space=cosine`만 존재 |

13개 taxonomy는 모두 내부 정의 card와 공통 규칙에 연결되어 있다. 정의·포함·제외·경계·cue가 있어 한국어 판정 규칙의 골격으로는 적절하다.

하지만 K-HATERS README 8건은 영문인데 loader가 `language=ko`, `normalized_language=ko`로 기록한다. 또한 README는 dataset 설명과 상위 label 소개이며 세부 한국어 annotation guideline 원문은 아니다. 이를 한국어 정의 근거로 동일 취급하는 것은 부정확하다.

### 사례 collection

| 항목 | 결과 |
| --- | --- |
| 전체 | 172,157건 |
| source | K-HATERS 100% |
| split | train 100% |
| license tier | `commercial_ok` 100% |
| 고유 text hash | 172,120개 |
| 중복 row | 37건 |
| 빈 row | 0건 |
| 5자 미만 | 9건 |
| 길이 | 최소 2, 중앙값 42, p95 163, 최대 417자 |
| 실제 문자 | 한글 포함 166,308, 한글·영문 혼합 5,810, 영문-only 9, 기타 30 |

raw label 분포:

- `normal` 46,643
- `offensive` 70,466
- `l1_hate` 19,537
- `l2_hate` 35,511

현재 mapped category 분포:

- `unclassified` 46,643
- `profanity` 70,466
- `other` 48,792
- `gender` 3,728
- `age` 1,765
- `identity` 900

서비스의 정치 6분류, `no_target`에는 직접 매핑된 사례가 없다. 이 category는 내부 definition 검색과 LLM 판단에만 의존한다.

## 발견한 핵심 불일치

### 1. K-HATERS target label mapping

실제 target label은 다음과 같다.

| label | 건수 |
| --- | ---: |
| `individual` | 46,751 |
| `political` | 31,091 |
| `region` | 15,168 |
| `others` | 14,811 |
| `job` | 6,569 |
| `gender` | 3,728 |
| `age` | 1,765 |
| `disabled` | 1,484 |
| `religion` | 900 |

loader는 `disability`와 `race`를 찾지만 실제 값은 `disabled`와 `region`이다. 그 결과 `identity` 900건은 사실상 religion만 반영하며 disabled 1,484건과 region 15,168건은 보호 속성 사례로 매핑되지 않는다. `political`은 31,091건이지만 국가/비국가와 authority/regime/community 축 정보가 없어 6개 정치 category로 직접 변환할 수 없다.

### 2. 단일 source·domain 편향

사례는 2021년 한국 Naver hard-news 댓글인 K-HATERS 하나뿐이다. YouTube 댓글·대댓글·자막, 최신 은어, 영어권 문화와 담론을 대표하지 않는다. train split만 retrieval에 사용하고 validation/test를 holdout한 점과 CC-BY 4.0 source만 허용한 점은 적절하다.

### 3. citation 무결성

공개 sample의 성공 댓글 708건을 현재 collection ID와 대조했다.

| 항목 | 결과 |
| --- | ---: |
| 사례 인용 | 801개, 고유 ID 709개 |
| 정의 인용 | 1,069개, 고유 ID 24개 |
| 사례 인용 없음 | 302개 결과 |
| 정의 인용 없음 | 50개 결과 |
| 잘못된 collection type | definition ID가 사례 인용에 8회 기록 |
| 존재하지 않는 definition ID | 1회 기록 |

현재 validator는 두 필드가 list인지만 검사하고 doc ID가 실제 retrieved subset인지 확인하지 않는다. 따라서 화면 공개는 가능하지만 연구 재현성이나 감사용 canonical evidence로 간주하면 안 된다.

### 4. provenance와 attribution

K-HATERS는 CC-BY 4.0으로 상업적 사용이 가능하지만 적절한 저자·논문·license attribution이 필요하다. source manifest와 내부 문서에는 기록돼 있으나 public methodology/report 화면에는 명시적인 attribution surface가 없다.

Embed 2 전환 당시 model과 차원을 확인했지만 현재 두 Chroma collection metadata에는 cosine space만 남아 있다. `analysis_runs`에는 provider/model/version이 기록되지만 collection 자체의 embedding fingerprint는 부족하다.

## 적합성 판정

| 목표 | 판정 | 이유 |
| --- | --- | --- |
| 현재 한국어 PoC/portfolio | 조건부 적합 | 상세 내부 taxonomy, 대규모 한국어 사례, 허용 license는 장점. label·domain·citation 한계 공개 필요 |
| 한국어 production 품질 주장 | 아직 부적합 | 독립 gold 평가, source 다양성, mapping 수정과 citation 검증 미완료 |
| UI의 한국어/영어 전환 | corpus와 독립적으로 진행 가능 | 메뉴·설명·결과 label 번역 문제이며 입력 판정 corpus를 바꾸지 않음 |
| 영어 입력 혐오표현 분석 | 부적합 | 영어 사례는 9건뿐이고 영어 taxonomy·문화 경계·평가셋이 없음 |
| 동일 collection에서 한·영 혼합 검색 | 권장하지 않음 | 언어 metadata 오류와 source 불균형 때문에 retrieval 결과의 비교 가능성이 낮음 |

## 한·영 구현 계획 작성 전 gate

1. `한·영 UI`와 `영어 입력 분석`을 별도 scope와 release gate로 나눈다.
2. 외부 definition의 언어를 실제 감지·기록하고, 영문 README를 한국어 guideline로 취급하지 않는다.
3. K-HATERS의 `disabled`, `region` mapping을 재정의하고 정치 label은 2축 판정용 gold/bridge schema를 별도로 만든다.
4. 모델 출력 citation을 실제 retrieved subset과 대조해 canonical ID·source·distance를 애플리케이션이 저장한다.
5. collection metadata에 embedding provider/model, passage alias, dimension, corpus version/hash를 기록하고 startup에서 검증한다.
6. public methodology 또는 report에 K-HATERS attribution을 노출한다.
7. 영어 분석을 범위에 넣는 경우 영어권 hate-speech 정의와 YouTube형 사례를 license 검토 후 별도 language collection에 적재한다.
8. 한국어·영어별 독립 gold set으로 retrieval recall@k, binary/category F1, reasoning 언어, citation precision을 평가한다.

이 gate가 해결되기 전에는 영어 분석 기능을 UI 번역과 함께 한 번에 구현하지 않는다. 이번 작업은 vector store를 수정하거나 재색인하지 않았으며, 후속 계획은 위 판정을 입력으로 사용해야 한다.

## 검증 결과

- frontend: 7 files, 18 tests 통과
- TypeScript와 Vite production build 통과
- report API 집중 backend: 3 tests 통과
- Ruff, `compileall`, `git diff --check` 통과
- dev/test/prod Compose config 통과
- 공개 sample의 좋아요 순 12번째 혐오 댓글 API: reasoning·RAG 상태·definition citation 반환 확인
- 실행 중 frontend source: `분석 근거 보기` 반영 확인
- production Chroma와 DB는 읽기 전용으로 감사했으며 count·document·metadata·분석 결과를 수정하지 않음
