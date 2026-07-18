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
