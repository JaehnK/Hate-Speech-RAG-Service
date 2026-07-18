# 벡터스토어 적재 문서 인벤토리

| 항목 | 값 |
| --- | --- |
| 기준일 | 2026-07-18 KST |
| 대상 | Chroma `hate_speech_definitions`, `hate_speech_examples` collection |
| 실행 진입점 | `scripts/bootstrap_corpus.py` |
| source manifest | `data/external/manifests/dataset_sources.yaml` |
| 원칙 | raw dataset 파일과 Chroma persistent directory는 Git에 커밋하지 않는다. 이 문서는 어떤 문서와 row가 vector store에 들어가는지만 추적한다. |

## 1. Bootstrap 순서

`docker compose --profile tools run --rm corpus` 또는 `python -m scripts.bootstrap_corpus`는 아래 순서로 같은 persist directory에 corpus를 만든다.

1. 내부 taxonomy 문서를 `hate_speech_definitions`에 적재한다.
2. manifest에서 definition license gate를 통과한 Markdown 문서를 `hate_speech_definitions`에 추가한다.
3. manifest에서 example license gate를 통과한 dataset row를 `hate_speech_examples`에 적재한다.

`--reset`을 주면 내부 taxonomy 적재와 example 적재 단계에서 대상 collection을 초기화한다. production 전체 적재에서는 `--limit-per-dataset`을 사용하지 않는다.

## 2. `hate_speech_definitions`

정의 collection은 분류 기준, category card, 외부 dataset 문서 chunk를 담는다. 검색 시 상위 8개를 가져와 앞 4개는 `taxonomy_context`, 뒤 4개는 `definition_context` prompt slot에 배치한다.

| source | 적재 단위 | doc id 패턴 | count | 생성 코드 |
| --- | --- | --- | ---: | --- |
| 내부 공통 규칙 | hate threshold, non-hate, political axis 등 rule card | `taxonomy:*:0`, `conflict:exclusive_categories:0` | 10 | `app/analysis/taxonomy.py::build_internal_taxonomy_documents` |
| 내부 category card | 13개 허용 category별 정의·포함·제외·경계·단서 | `category:{category}:0` | 13 | `app/analysis/taxonomy.py::build_internal_taxonomy_documents` |
| K-HATERS 문서 | `README.md`를 heading/paragraph 기준 최대 3,000자로 chunking | `dataset:k-haters:README:{index}:{hash}` | 8 | `app/analysis/definition_ingest.py` |

내부 taxonomy rule card 10건:

| doc id | 역할 |
| --- | --- |
| `taxonomy:allowed_categories:0` | 허용 category code 목록 |
| `taxonomy:hate_threshold:0` | 혐오·공격 판정 threshold |
| `taxonomy:non_hate_rule:0` | 비혐오 출력 규칙 |
| `taxonomy:other_rule:0` | `other` 단독 사용 규칙 |
| `taxonomy:political_axis:0` | 정치 category의 state/non-state와 authority/regime/community 판단 축 |
| `taxonomy:context_exception:0` | 인용·보도·연구·풍자 문맥 예외 |
| `taxonomy:multi_label_rule:0` | 복수 category 선택 규칙 |
| `taxonomy:hate_type:0` | `hate_type` 한국어 요약 규칙 |
| `taxonomy:target_group:0` | `target_group` 한국어 명사구 작성 규칙 |
| `conflict:exclusive_categories:0` | `unclassified`, `other`, `no_target` 충돌 규칙 |

내부 category card 13건:

| doc id | 한국어 이름 |
| --- | --- |
| `category:gender:0` | 성별·젠더 |
| `category:age:0` | 연령 |
| `category:identity:0` | 정체성·소수자 |
| `category:profanity:0` | 욕설·모욕 |
| `category:state_authority:0` | 국가 권위 주체 |
| `category:non_state_authority:0` | 비국가 권위 주체 |
| `category:state_regime:0` | 국가 제도·질서 |
| `category:non_state_regime:0` | 비국가 제도·규칙 |
| `category:state_community:0` | 국가 공동체 |
| `category:non_state_community:0` | 비국가 공동체 |
| `category:no_target:0` | 표적 없는 공격 |
| `category:other:0` | 기타 혐오 |
| `category:unclassified:0` | 비혐오·미분류 |

외부 definition 문서는 manifest의 `corpus_target.definitions=true`이고 license tier가 `commercial_ok`로 정규화되는 source만 적재한다. 현재 이 조건을 통과하는 기본 source는 K-HATERS뿐이다.

### 2.1 현재 한계

현재 definition collection은 내부 taxonomy가 23/31건을 차지한다. 내부 taxonomy는 서비스 출력 형식과 category 경계를 안정화하는 데 필요하지만, 그 자체가 외부 권위 문서는 아니다. 따라서 검색 결과가 내부 taxonomy에 과도하게 치우치면 다음 문제가 생길 수 있다.

| 위험 | 영향 |
| --- | --- |
| 기준 순환 | 우리가 만든 category 정의가 다시 판단 근거로 쓰여 외부 기준과의 거리감을 확인하기 어렵다. |
| 권위 근거 부족 | report에서 “왜 혐오표현인가”를 설명할 때 공신력 있는 기준이나 플랫폼 정책과 연결하기 어렵다. |
| recall 편향 | YouTube 댓글, 정책 위반, 인권·차별 맥락보다 내부 category keyword에 가까운 사례가 우선 검색될 수 있다. |
| 감사 어려움 | 분류 기준 변경 시 외부 기준과 내부 taxonomy 중 무엇이 결과를 움직였는지 분리하기 어렵다. |

따라서 내부 taxonomy는 계속 유지하되, 공식·권위 문서를 별도 source로 추가하고 retrieval 결과에서 내부 taxonomy와 외부 기준 문서의 비율을 통제하는 보강이 필요하다.

### 2.2 공식·권위 문서 후보

아래 문서는 현재 vector store에 올라가지 않는다. license와 이용 조건, chunk 범위, attribution 문구를 확인한 뒤 별도 작업으로 ingest해야 한다.

| 후보 문서 | source URL | 역할 | 적재 상태 |
| --- | --- | --- | --- |
| 국가인권위원회 `혐오표현 예방·대응 가이드라인 마련 실태조사` | `https://www.humanrights.go.kr/base/board/read?boardManagementNo=17&boardNo=7603675` | 한국어 혐오표현 정의, 예방·대응 관점, 차별·인권 맥락 보강 | 후보, 미적재 |
| 국가인권위원회 `혐오표현 리포트` | `https://www.humanrights.go.kr/site/program/board/basicboard/view?boardid=7604691&boardtypeid=17&menuid=001003001003004` | 한국 사회의 혐오표현 범위와 사회적 영향 설명 | 후보, 미적재 |
| YouTube Hate speech policy | `https://support.google.com/youtube/answer/2801939` | YouTube 플랫폼에서 금지하는 보호 속성 기반 폭력·증오 기준 | 후보, 미적재 |
| YouTube Harassment & cyberbullying policies | `https://support.google.com/youtube/answer/2802268` | 개인 대상 모욕, 반복 괴롭힘, 보호 속성 기반 공격의 플랫폼 경계 | 후보, 미적재 |
| OHCHR Rabat Plan of Action / threshold test | `https://www.ohchr.org/en/documents/outcome-documents/rabat-plan-action` | 표현의 자유와 차별·적대·폭력 선동 사이의 높은 threshold 기준 | 후보, 미적재 |

공식 문서를 추가할 때는 원문 전체를 무비판적으로 넣지 않는다. RAG definition source에는 정의, 판단 요건, 보호 속성, 예외·문맥 판단, threshold test처럼 분류에 직접 필요한 절만 chunking한다. 서비스 category code와 직접 맞지 않는 표현은 metadata의 `related_categories`로 연결하되, 원문 의미를 category에 억지로 맞추지 않는다.

### 2.3 보강 시 권장 retrieval 구조

공식 문서를 추가하면 단순히 같은 collection에 섞는 것보다 source type을 구분해야 한다.

| source type | 예 | 권장 역할 |
| --- | --- | --- |
| `internal_taxonomy` | 현재 23개 taxonomy card | 출력 schema, category 경계, conflict rule |
| `authoritative_guideline` | 국가인권위원회, OHCHR | 정의, threshold, 인권·차별 해석 기준 |
| `platform_policy` | YouTube policy | 플랫폼 맥락의 금지 기준과 보호 속성 |
| `dataset_guideline` | K-HATERS README | dataset label 체계와 사례 corpus 설명 |

후속 구현에서는 definition retrieval 결과를 source type별로 균형 있게 가져오는 방식을 검토한다. 예를 들어 taxonomy 3건, authoritative guideline 3건, platform policy 1건, dataset guideline 1건처럼 slot을 나누면 내부 taxonomy가 모든 context를 독점하는 문제를 줄일 수 있다.

## 3. `hate_speech_examples`

예시 collection은 LLM에게 유사 댓글 사례를 제공하기 위한 row 단위 corpus다. 검색 시 최대 6개를 가져오고 `score >= 0.40`인 예시만 prompt와 `similar_cases_used` 후보에 남긴다.

| source | 적재 파일 | split | doc id 패턴 | count | 생성 코드 |
| --- | --- | --- | --- | ---: | --- |
| K-HATERS | `data/external/datasets/k-haters-hf/train.jsonl` | train | `k-haters:train:{index}` | 172,157 | `app/analysis/example_loaders.py::_load_k_haters` |

각 example row는 다음 metadata를 함께 가진다.

| metadata | 내용 |
| --- | --- |
| `source_dataset` | `k-haters` |
| `source_split` | `train` |
| `source_revision` | manifest의 K-HATERS Git revision |
| `license_tier` | `commercial_ok` |
| `raw_labels` | 원천 `label`, `target_label` |
| `mapped_categories` | 서비스 taxonomy로 변환한 category |
| `is_hate_speech` | `label != normal` |
| `target_labels` | K-HATERS target label 목록 |
| `hate_type_labels` | normal이 아닌 경우 원천 label |
| `text_hash` | 원문 text SHA-256 |

공백 text row는 loader에서 제외한다. 현재 live audit 기준 `train.jsonl` 원천 172,158건 중 공백 row 1건이 제외되어 172,157건이 적재된다.

## 4. manifest에는 있으나 기본 vector store에 올라가지 않는 자료

`DEFAULT_DEFINITION_LICENSE_TIERS`와 `DEFAULT_EXAMPLE_LICENSE_TIERS`는 모두 `commercial_ok`만 허용한다. 따라서 아래 dataset은 local에 있어도 production 기본 corpus에는 적재하지 않는다.

| dataset | examples | definitions | 제외 이유 |
| --- | --- | --- | --- |
| UNSMILE | 제외 | 제외 | internal evaluation reference, permission/non-commercial 계열 |
| K-MHaS | 제외 | 제외 | 명시 license 파일 미확인, `license_review_required` |
| KODOLI | 제외 | 제외 | CC-BY-SA 계열, ShareAlike 영향 검토 필요 |
| KOLD | 제외 | 제외 | usage restriction/license review 필요 |
| BEEP | 제외 | 제외 | CC-BY-SA 계열, ShareAlike 영향 검토 필요 |
| AI Hub Text Ethics | 제외 | 제외 | 계정 승인·약관 동의 필요 |

코드상 BEEP, KODOLI loader는 존재하지만 현재 license gate를 통과하지 못하므로 production 기본 적재에는 사용되지 않는다.

## 5. 정합성 체크

배포 전 corpus를 새로 만들 때 아래 값이 맞는지 확인한다.

| 항목 | 기대값 |
| --- | ---: |
| internal taxonomy definitions | 23 |
| external K-HATERS definitions | 8 |
| total `hate_speech_definitions` | 31 |
| total `hate_speech_examples` | 172,157 |

새 dataset이나 definition 문서를 vector store에 넣으려면 다음 네 곳을 함께 갱신한다.

1. `data/external/manifests/dataset_sources.yaml`
2. `data/external/manifests/dataset_inventory.yaml`
3. loader 또는 definition ingest 코드
4. 이 문서의 collection별 표
