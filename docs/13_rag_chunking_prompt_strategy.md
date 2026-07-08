# RAG 청킹 및 프롬프트 전략

| 항목 | 값 |
| --- | --- |
| 버전 | v0.1.0 |
| 작성일시 | 2026-07-09 01:10:12 KST |

## 문서 목적

이 문서는 혐오 카테고리 중심 RAG 분류기의 corpus 청킹, vector collection 구성, retrieval 전략, 프롬프트 판단 절차를 정의한다.

구현 목표는 FastAPI 서비스 구현 전에 RAG 입출력 계약을 고정하는 것이다.

## 기본 방향

- RAG는 단순 혐오/비혐오 판단이 아니라 `categories` 선택을 보강한다.
- `hate_speech_examples`와 `hate_speech_definitions`는 다른 종류의 근거이므로 분리한다.
- prompt는 검색된 사례에 끌려가지 않고 taxonomy 규칙을 먼저 따른다.
- 공개 데모 또는 상업 가능성이 있는 환경에서는 license tier에 따라 corpus를 제한한다.
- raw dataset과 vector store는 git에 커밋하지 않는다.

## Vector Collections

MVP는 다음 두 collection을 기본으로 사용한다.

| collection | 역할 | 주요 입력 |
| --- | --- | --- |
| `hate_speech_examples` | 입력 문장과 유사한 한국어 댓글 사례 검색 | 공개 데이터셋의 라벨된 row |
| `hate_speech_definitions` | 정의, 라벨 기준, 카테고리 판단 규칙 검색 | 내부 taxonomy, 공식 문서, annotation guideline |

운영 환경이 Redis vector search로 바뀌더라도 위 logical collection 이름은 유지한다.

## License Tier

ingest 대상은 license tier로 먼저 필터링한다.

| tier | 의미 | 기본 사용 |
| --- | --- | --- |
| `commercial_ok` | 상업/공개 서비스 사용 가능성이 높음 | 허용 |
| `sharealike_review` | CC-BY-SA 등 공유 조건 검토 필요 | 포트폴리오/내부 PoC 허용, 상업 전 검토 |
| `license_review_required` | 명시 라이선스 부족 또는 제한 문구 있음 | 기본 제외 |
| `permission_required` | 상업 사용 또는 파생 사용에 사전 허가 필요 | 제외 |
| `internal_eval_only` | 평가/비공개 실험용 | retrieval corpus 제외 |

초기 권장값:

| dataset | tier | examples | definitions |
| --- | --- | --- | --- |
| `k-haters` | `commercial_ok` | 포함 | label 설명 포함 |
| `beep` | `sharealike_review` | 선택 포함 | annotation guideline 포함 |
| `kodoli` | `sharealike_review` | 선택 포함 | guideline/label 설명 포함 |
| `k-mhas` | `license_review_required` | 제외 | label 설명만 검토 |
| `kold` | `license_review_required` | 제외 | target group 구조만 검토 |
| `unsmile` | `permission_required` | 제외 | 내부 평가용 |
| `ai-hub-text-ethics` | `permission_required` | 제외 | 제외 |

## Examples Corpus Chunking

### 기본 단위

`hate_speech_examples`는 청킹하지 않는다.

```text
1 dataset row = 1 vector document
```

이유:

- 예시 corpus의 목적은 유사한 짧은 댓글 사례 검색이다.
- row를 쪼개면 라벨과 문맥이 분리된다.
- 여러 row를 합치면 label purity가 떨어진다.

### 사용 split

| split | 용도 |
| --- | --- |
| train | retrieval corpus |
| validation | prompt regression/evaluation |
| test | 최종 평가 또는 보류 |
| unlabeled | retrieval corpus 제외 |

split이 없는 데이터셋은 deterministic split을 만든다.

권장 split:

```text
train 80%, validation 10%, test 10%
seed = 20260709
```

### Example Document Schema

각 example document는 다음 형태로 정규화한다.

| 필드 | 설명 |
| --- | --- |
| `doc_id` | `{dataset}:{split}:{source_id_or_index}` |
| `text` | embedding 대상 텍스트 |
| `source_dataset` | dataset ID |
| `source_split` | train, validation, test |
| `source_revision` | Git commit, Hugging Face revision, checksum 등 |
| `license_tier` | license filter 결과 |
| `raw_labels` | 원본 라벨 |
| `mapped_categories` | `12_category_taxonomy.md` 기준 변환 라벨 |
| `is_hate_speech` | 변환된 혐오 여부 |
| `target_labels` | 원본 target label 또는 변환 target |
| `hate_type_labels` | 원본 offensive type 또는 변환 type |
| `text_hash` | 원문 추적용 hash |

보고서에는 기본적으로 example 원문을 노출하지 않는다.

`similar_cases_used`에는 `doc_id`, `source_dataset`, `mapped_categories`, `score`만 저장한다.

### Dataset Mapping

초기 mapping은 보수적으로 둔다.

| dataset | 원본 라벨 | mapping |
| --- | --- | --- |
| `k-haters` | `target_label=gender` | `gender` |
| `k-haters` | `target_label=age` | `age` |
| `k-haters` | `target_label=race`, `religion`, `disability` | `identity` |
| `k-haters` | `target_label=politics` | 정치 카테고리 후보, 세부 분류는 prompt 판단 |
| `k-haters` | `label=Offensive` | `profanity` 또는 `other` 후보 |
| `beep` | `bias=gender` | `gender` |
| `beep` | `hate=hate` | `is_hate_speech=true` |
| `beep` | `hate=offensive` | `profanity` 또는 `other` 후보 |
| `kodoli` | `offensiveness=offensive` | `is_hate_speech=true` 후보 |

정치 카테고리 6종은 dataset label만으로 확정하지 않는다.

`state_authority`, `non_state_authority`, `state_regime`, `non_state_regime`, `state_community`, `non_state_community`는 prompt가 대상 유형과 행위자 성격을 판단해 결정한다.

## Definitions Corpus Chunking

### 우선순위

`hate_speech_definitions`는 다음 순서로 구성한다.

1. 내부 taxonomy 문서
2. 내부 카테고리 판단 카드
3. dataset annotation guideline과 label description
4. 국내 공식/준공식 혐오표현 문서
5. 국제 기준과 플랫폼 정책
6. 논문 초록, 라벨 체계 설명, 저자가 공개한 summary

### Internal Taxonomy Cards

내부 문서는 다음 chunk를 반드시 만든다.

| chunk | 내용 |
| --- | --- |
| `taxonomy:allowed_categories` | 허용 카테고리 전체 목록 |
| `taxonomy:non_hate_rule` | 비혐오와 `unclassified` 규칙 |
| `taxonomy:other_rule` | `other` 독점 사용 규칙 |
| `taxonomy:political_axis` | authority/regime/community와 state/non-state 축 |
| `category:{category}` | 카테고리별 정의, 포함 기준, 제외 기준 |
| `conflict:{rule}` | 충돌 또는 우선순위 규칙 |

내부 taxonomy card는 prompt에 고정 규칙으로도 들어가고, vector retrieval에도 들어간다.

### External Definition Chunking

공식 문서와 guideline은 의미 단위로 나눈다.

| 문서 유형 | chunk 기준 | 크기 |
| --- | --- | --- |
| 조항/가이드라인 | 제목, 조항, 항목 단위 | 150~500 token |
| 긴 설명형 문서 | 문단 묶음 | 300~700 token |
| annotation guideline | 판단 기준 또는 예외 규칙 단위 | 150~500 token |
| 논문 | 초록, 라벨 체계, annotation 설명 | 150~500 token |
| platform policy | 보호 속성, 금지 행위, 예외 단위 | 150~500 token |

overlap은 기본 0으로 둔다.

긴 설명형 문서만 50~80 token overlap을 허용한다.

### Language Policy

| 원문 언어 | 처리 |
| --- | --- |
| 한국어 | 원문 chunk를 그대로 사용 |
| 영어 | 원문 chunk 보존, 한국어 정규화 chunk를 별도 생성 가능 |
| 기계 번역 | 원문 대체 금지, `normalized_language=ko`로 표시 |

한국어 댓글 검색 품질을 위해 영어 문서는 한국어 정규화 summary chunk를 함께 둘 수 있다.

단, summary chunk는 내부 작성물로 표시한다.

### Definition Document Schema

| 필드 | 설명 |
| --- | --- |
| `doc_id` | `{source_id}:{section_id}:{chunk_index}` |
| `source_id` | source manifest ID |
| `source_title` | 문서 제목 |
| `source_url` | 원문 URL |
| `publisher` | 발행 기관 |
| `document_type` | taxonomy_card, guideline, policy, paper_summary 등 |
| `language` | 원문 언어 |
| `normalized_language` | 검색용 언어 |
| `license_tier` | license filter 결과 |
| `retrieval_tags` | category, definition, political_axis, protected_attribute 등 |
| `related_categories` | 연결된 taxonomy category |
| `chunk_hash` | chunk text hash |

## Retrieval Strategy

### Query

댓글과 스크립트 세그먼트는 동일한 분류기를 사용한다.

검색 query는 다음을 합친 짧은 문자열이다.

```text
{input_text}
source_type={comment|reply|script_segment}
context_hint={optional}
```

스크립트 세그먼트는 이전/다음 문장을 context로 줄 수 있지만, classification 대상은 현재 segment로 제한한다.

### Retriever Slots

prompt에는 검색 결과를 슬롯별로 분리해 넣는다.

| 슬롯 | collection | 기본 k | 역할 |
| --- | --- | --- | --- |
| `taxonomy_context` | `hate_speech_definitions` | 4 | 카테고리 규칙 |
| `definition_context` | `hate_speech_definitions` | 4 | 외부 정의/판단 기준 |
| `example_context` | `hate_speech_examples` | 6 | 유사 한국어 사례 |

`taxonomy_context`는 관련 카테고리 card를 우선 검색한다.

필요하면 `taxonomy:allowed_categories`, `taxonomy:non_hate_rule`, `taxonomy:political_axis`는 검색 없이 항상 prompt에 넣는다.

### Reranking

초기 구현은 단순 reranking으로 충분하다.

정책:

- 동일 dataset example은 최대 3개까지 사용한다.
- 동일 mapped category example은 최대 3개까지 사용한다.
- `commercial_ok` tier를 우선한다.
- `sharealike_review` tier는 설정으로 포함 여부를 제어한다.
- score가 낮은 결과는 prompt에 넣지 않고 `rag_context_status`에 반영한다.

score threshold는 Chroma smoke test 후 정한다.

초기값은 문서화만 하고 코드에서는 config로 둔다.

## Prompt Strategy

### Prompt Version

초기 prompt version:

```text
category-rag-v0.1.0
```

prompt version이 바뀌면 analysis run에 기록한다.

### Prompt Inputs

| 입력 | 설명 |
| --- | --- |
| `taxonomy_version` | `12_category_taxonomy.md` 버전 |
| `allowed_categories` | 허용 category code 목록 |
| `input_text` | 분석 대상 텍스트 |
| `source_type` | comment, reply, script_segment |
| `taxonomy_context` | 내부 taxonomy 검색 결과 |
| `definition_context` | 외부 정의 문서 검색 결과 |
| `example_context` | 유사 예시 검색 결과 |

### 판단 순서

LLM은 다음 순서를 따라야 한다.

1. 입력이 혐오표현 또는 공격적 표현인지 판단한다.
2. 비혐오이면 `is_hate_speech=false`, `categories=["unclassified"]`를 반환한다.
3. 혐오이면 보호 속성 기반 카테고리를 먼저 검토한다.
4. 정치적 대상이 있으면 대상 유형을 `authority`, `regime`, `community` 중 하나로 판단한다.
5. 정치적 대상이 있으면 행위자 성격을 `state`, `non_state` 중 하나로 판단한다.
6. 두 정치 축을 결합해 정치 혐오 카테고리 6종 중 하나를 선택한다.
7. 욕설, 모욕, 비하, 위협, 선동 등 `hate_type`을 판단한다.
8. 공격 대상이 명확하면 `target_group`을 작성한다.
9. `other`, `unclassified`의 독점 규칙을 검증한다.

### 금지되는 Prompt 가정

다음 문장은 prompt에 넣지 않는다.

```text
주어질 문장은 모두 혐오표현으로 분류된 것으로...
```

전체 댓글과 전체 스크립트 세그먼트를 분석하므로 입력이 혐오표현이라고 가정하면 안 된다.

### Output Schema

분류 결과는 다음 JSON shape를 따른다.

```json
{
  "input_text": "분석 대상 텍스트",
  "is_hate_speech": true,
  "categories": ["non_state_community", "profanity"],
  "target_group": "정치 지지층",
  "hate_type": "모욕/비하",
  "reasoning": "카테고리 선택 근거 요약",
  "similar_cases_used": [
    {
      "doc_id": "k-haters:train:123",
      "source_dataset": "k-haters",
      "mapped_categories": ["profanity"],
      "score": 0.82
    }
  ],
  "definition_docs_used": [
    {
      "doc_id": "taxonomy:political_axis:0",
      "source_id": "internal_taxonomy",
      "retrieval_tags": ["political_axis"]
    }
  ]
}
```

`reasoning`은 보고서용 요약 근거다.

chain-of-thought 또는 장문의 내부 추론을 저장하지 않는다.

### Validation Rules

LLM 응답은 저장 전에 검증한다.

| 규칙 | 실패 처리 |
| --- | --- |
| `categories`는 허용 목록에만 속한다 | retry |
| `is_hate_speech=false`이면 `categories=["unclassified"]` | retry |
| `is_hate_speech=true`이면 `unclassified` 금지 | retry |
| `other`는 다른 category와 동시 사용 금지 | retry |
| `target_group=null`이면 구체 대상 카테고리 근거 확인 | warning 또는 retry |
| JSON parsing 실패 | retry |

retry는 1회만 수행한다.

2회 실패하면 해당 item은 `failed`로 저장하고 raw response를 마스킹해 보관한다.

## Report Exposure Policy

보고서에는 다음을 표시한다.

- category distribution
- target group distribution
- hate type distribution
- 대표 사례의 원문 또는 부분 원문
- 사용된 definition source title과 URL
- 사용된 example source dataset과 category

보고서에는 다음을 기본 표시하지 않는다.

- 외부 dataset example 원문
- full prompt
- 긴 definition 원문
- raw LLM response

## Smoke Test

ingest 후 다음 테스트를 수행한다.

1. `hate_speech_examples` count가 예상 row 수와 일치한다.
2. `hate_speech_definitions`에 내부 taxonomy card가 모두 들어 있다.
3. 정치 관련 query가 정치 axis chunk를 검색한다.
4. 보호 속성 query가 관련 category card를 검색한다.
5. 비혐오 query에서 example retrieval이 과도하게 혐오 사례만 반환하지 않는다.
6. prompt output이 validation rules를 통과한다.
7. 같은 input을 3회 실행했을 때 category가 안정적으로 나온다.

## 구현 순서

1. source manifest에 license tier를 확정한다.
2. dataset별 canonical loader를 만든다.
3. taxonomy mapping table을 만든다.
4. `hate_speech_examples`용 document builder를 만든다.
5. internal taxonomy card generator를 만든다.
6. external definition chunk builder를 만든다.
7. Chroma ingest script를 만든다.
8. retrieval smoke test를 작성한다.
9. prompt template과 output validator를 작성한다.
10. RAG 단독 regression test를 작성한다.

## 보류 사항

- Redis vector search 전환 시 score normalization 기준
- `sharealike_review` tier를 public demo에 포함할지
- `K-MHaS`, `KOLD` 상업/공개 서비스 사용 가능 여부
- AI Hub 데이터의 embedding/RAG 사용 가능 여부
- 정치 카테고리 gold dataset의 초기 라벨링 규모
