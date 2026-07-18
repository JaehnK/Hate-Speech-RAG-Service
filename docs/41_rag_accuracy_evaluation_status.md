# RAG 정확도 평가셋·결과 현황

| 항목 | 값 |
| --- | --- |
| 기준일 | 2026-07-18 KST |
| 대상 | `category-rag-v0.3.1`, three-vector RAG |
| 결론 | 현재 저장소에는 운영 정확도를 주장할 수 있는 실제 YouTube gold test set이 없다. 다만 레거시 작업공간에는 공개 라벨셋 기반 평가 자산이 남아 있다. |

## 1. 현재 보유한 평가 자료

| 자료 | 경로 | 용도 | 정확도 주장 가능 여부 |
| --- | --- | --- | --- |
| 합성 smoke gold 5건 | `experiments/gold_labels/synthetic_smoke_5.jsonl` | evaluator, prompt contract, 반복 실행 경로 확인 | 불가 |
| sample input 50건 | `experiments/sample_inputs/comments_50.jsonl` | 실험 runner 입력 예시 | gold label 없음 |
| live RAG smoke outputs | `experiments/outputs/live_rag_*.jsonl` | 과거 prompt·threshold 회귀 증적 | 불가 |
| live E2E evidence | `experiments/outputs/live_e2e_evidence.json` | 실제 API 경로와 report 생성 증적 | 정확도 평가 아님 |
| legacy UNSMILE valid | `legacy/hateSpeechRAG/data/raw/korean_unsmile_dataset/unsmile_valid_v1.0.tsv` | 공개 한국어 혐오표현 라벨셋 기반 회귀 평가 후보 | 제한적 가능 |
| legacy UNSMILE 평가 결과 | `legacy/hateSpeechRAG/scripts/hate_speech_evaluation_20250918_183926.json` | 과거 RAG 평가 지표 증적 | 현재 모델 직접 성능 주장 불가 |

`synthetic_smoke_5.jsonl`에서 1.000이 나오더라도 이는 “평가 코드와 회귀 경로가 동작한다”는 뜻이지, YouTube 댓글 분석 정확도가 100%라는 뜻이 아니다.

레거시의 UNSMILE 평가는 공개 라벨셋 기준의 재현 가능한 성능 점검 후보로 볼 수 있다. 하지만 운영 서비스가 분석하는 YouTube 댓글·답글·자막의 분포와 다르므로, 그 결과만으로 실제 YouTube 분석 정확도를 대표한다고 말하면 안 된다. 레거시 자산의 위치와 사용 판단은 `docs/42_legacy_evaluation_inventory.md`에 기록한다.

## 2. 이미 있는 평가 도구

실험 실행:

```bash
uv run python -m experiments.run_rag_experiment \
  --input-path REAL_INPUTS.jsonl \
  --output-path experiments/outputs/rag_results.jsonl \
  --variant three_vector_rag \
  --repeat 3
```

평가:

```bash
uv run python -m experiments.evaluate_results \
  --results-path experiments/outputs/rag_results.jsonl \
  --gold-path REAL_GOLD.jsonl
```

비교 대상 variant:

| variant | taxonomy | authoritative | examples | 목적 |
| --- | ---: | ---: | ---: | --- |
| `haiku_only` | 0 | 0 | 0 | RAG 없는 LLM baseline |
| `definitions_only` | 4 | 4 | 0 | 기준 문서만 사용 |
| `examples_only` | 0 | 0 | 6 | 유사 사례만 사용 |
| `three_vector_rag` | 4 | 4 | 6 | 현재 production 의도 구조 |

`dual_rag`는 과거 이름 호환 alias로만 남긴다. 새 결과 파일에는 `three_vector_rag`를 기록한다.

## 3. 실제 gold test set 요구사항

운영 품질을 말하려면 별도 gold set을 만들어야 한다.

| 요구사항 | 기준 |
| --- | --- |
| 원천 | 실제 YouTube 댓글·답글·공개 자막 세그먼트 |
| 개인정보 | 작성자명, channel id, URL, 직접 식별자 제거 |
| 표본 구성 | 정상/혐오/경계 사례를 모두 포함하고 댓글과 자막을 분리 기록 |
| 라벨링 | 최소 2인 독립 라벨링 후 불일치 조정 |
| 단위 | `item_id`, `source_type`, `text`, gold label을 같은 row id로 연결 |
| 보관 | 원문이 민감하면 Git 제외 경로에 보관하고 hash·집계 결과만 문서화 |

최소 MVP gate는 다음 정도가 적절하다.

| split | 최소 수량 | 용도 |
| --- | ---: | --- |
| pilot | 50 | label guideline 교정, category 충돌 확인 |
| validation | 200 | prompt/retrieval threshold 조정 |
| test | 300 | 배포 전 최종 고정 평가 |

test split은 prompt, taxonomy, retrieval 설정을 고른 뒤에만 사용한다. test 결과를 보고 prompt를 다시 고치면 같은 test set으로 품질을 주장하지 않는다.

## 4. Gold JSONL schema

입력 파일:

```json
{"item_id":"yt-001","source_type":"comment","text":"익명화된 댓글 원문"}
```

gold label 파일:

```json
{"item_id":"yt-001","is_hate_speech":true,"categories":["gender"],"target_group":"여성","hate_type":"모욕/비하","rationale":"성별을 근거로 집단을 비하함","adjudication":"resolved"}
```

권장 추가 필드:

| 필드 | 설명 |
| --- | --- |
| `source_domain` | comment, reply, script 등 분석 원천 |
| `difficulty` | clear, borderline, context_dependent |
| `annotator_a`, `annotator_b` | 원 라벨 보존이 필요한 경우 Git 제외 파일에만 저장 |
| `disagreement_reason` | 조정 시 주요 불일치 이유 |

## 5. 보고해야 하는 결과

최소 결과표:

| 지표 | 이유 |
| --- | --- |
| coverage | 실패·누락을 제외한 평가 비율 |
| binary accuracy, precision, recall, F1 | 혐오/비혐오 기본 성능 |
| category micro precision, recall, F1 | multi-label category 성능 |
| category별 confusion | 정치/정체성/욕설 경계 오류 확인 |
| repeat stability | 같은 입력 반복 실행 안정성 |
| failure rate, retry rate, cost | 운영 가능성 |

현재 evaluator는 coverage, binary accuracy, category micro precision/recall/F1, repeat stability를 계산한다. category별 confusion과 비용 summary는 후속 보강 대상이다.

## 6. 현재 공개 가능한 표현

가능:

- “평가 runner와 evaluator는 준비되어 있다.”
- “합성 smoke set으로 실행 경로와 validator 회귀를 확인했다.”
- “실제 YouTube gold set 기반 정확도 평가는 아직 수행 전이다.”

불가:

- “RAG 정확도는 1.000이다.”
- “Three-vector 구조가 실제 정확도를 개선했다.”
- “현재 결과가 YouTube 댓글 전체를 대표한다.”

three-vector RAG가 정확도를 개선했는지는 같은 gold set에서 `haiku_only`, `definitions_only`, `examples_only`, `three_vector_rag`를 비교한 뒤에만 말할 수 있다.
