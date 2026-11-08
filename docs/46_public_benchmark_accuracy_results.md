# 공개 벤치마크 정확도 평가 결과

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-08 KST |
| 대상 | `category-rag-v0.3.1`, three-vector RAG, `claude-haiku-4-5-20251001`, temperature 0 |
| corpus | 운영 VM `hsr_chroma_data` 사본: taxonomy 23, authoritative 8, examples 172,157 |
| gold | K-HATERS test 499건, BEEP dev 471건 (공개 데이터셋 원작자의 사람 라벨) |
| 비용 | Anthropic + Upstage 약 $16 (smoke 포함) |
| 결론 | 같은 입력에서 three-vector RAG는 RAG 미적용 대비 binary F1을 0.601 → 0.805로 올렸고 McNemar p < 0.0001이다. 개선의 대부분은 example 검색에서 나오며, 정의 문서를 더한 효과는 통계적으로 확인되지 않았다. |

## 1. 평가셋

`experiments.build_benchmark_gold`로 생성한다. example collection은 train split으로만 만들었으므로 test/dev split은 검색 corpus와 겹치지 않는다. train에 같은 문장이 있는 row(K-HATERS 3건)는 추가로 제외했다.

| 셋 | 원천 | 건수 | 혐오 비율 | 샘플링 | corpus와의 관계 |
| --- | --- | ---: | ---: | --- | --- |
| K-HATERS test | `humane-lab/K-HATERS` test | 499 | 79% | category별 최소 50건 보장 후 층화 | 같은 데이터셋 train이 examples에 들어 있음 (in-distribution) |
| BEEP dev | `beep-korean-hate-speech/labeled/dev.tsv` | 471 | 68% | 전수 | license tier가 `commercial_ok`가 아니라 corpus에 없음 (out-of-distribution) |

K-HATERS는 희소 category(age·gender·identity)를 평가하려고 최소 건수를 보장했다. 따라서 혐오 비율이 원본 분포와 다르고, binary 지표는 실제 YouTube 댓글 분포를 대표하지 않는다.

benchmark 라벨 체계는 `gender/age/identity/profanity/other`뿐이다. evaluator는 모델이 낸 정치 계열 category와 `no_target`을 `other`로 접어서 채점한다.

## 2. 결과

95% bootstrap 구간(1,000회), McNemar 검정은 `three_vector_rag` 대비 binary 정오 기준(정확 이항 검정)이다.

### 합산 970건

| variant | binary acc | binary F1 | category macro F1 | McNemar p |
| --- | ---: | ---: | ---: | ---: |
| `haiku_only` | 0.573 [0.543, 0.604] | 0.601 [0.565, 0.634] | 0.441 | < 0.0001 |
| `definitions_only` | 0.623 [0.594, 0.653] | 0.667 [0.634, 0.699] | 0.439 | < 0.0001 |
| `examples_only` | 0.736 [0.709, 0.766] | 0.794 [0.769, 0.819] | 0.521 | 0.105 |
| `three_vector_rag` | **0.749** [0.724, 0.779] | **0.805** [0.781, 0.830] | **0.523** | — |

### 셋별

| variant | K-HATERS acc | K-HATERS F1 | BEEP acc | BEEP F1 |
| --- | ---: | ---: | ---: | ---: |
| `haiku_only` | 0.647 | 0.722 | 0.495 | 0.414 |
| `definitions_only` | 0.739 | 0.810 | 0.499 | 0.427 |
| `examples_only` | 0.788 | 0.857 | 0.682 | 0.701 |
| `three_vector_rag` | 0.810 | 0.872 | 0.686 | 0.704 |

`three_vector_rag` 세부:

| 셋 | binary precision | binary recall | 평균 input tokens |
| --- | ---: | ---: | ---: |
| K-HATERS | 0.926 | 0.825 | 3,826 |
| BEEP | 0.989 | 0.547 | 3,358 |
| 합산 | 0.947 | 0.700 | 3,599 |

합산 category별 F1: gender 0.75, age 0.66, other 0.43, identity 0.42, profanity 0.36.

## 3. 해석

1. RAG 효과는 유의하다. 합산 binary F1 +0.204, 정확도 +17.6%p이며 두 셋 모두 McNemar p < 0.0001이다.
2. 구성요소는 각각 효과가 있지만 더해지지는 않는다. baseline 대비 McNemar 결과는 다음과 같다.

   | 비교 | 합산 acc 변화 | 합산 p | K-HATERS p | BEEP p |
   | --- | ---: | ---: | ---: | ---: |
   | `definitions_only` vs `haiku_only` | +5.0%p | < 0.0001 | < 0.0001 | 0.86 |
   | `examples_only` vs `haiku_only` | +16.3%p | < 0.0001 | < 0.0001 | < 0.0001 |
   | `three_vector_rag` vs `examples_only` | +1.3%p | 0.10 | 0.10 | 0.81 |

   정의 문서는 단독으로 유의한 개선을 주지만 corpus 밖 BEEP에서는 효과가 없다. example 검색 위에 정의 문서를 더한 추가 개선은 확인되지 않았다.
3. corpus 밖 데이터에서도 효과가 유지된다. BEEP는 검색 corpus에 없는 데이터셋인데도 F1 0.414 → 0.704로 올랐다.
4. 주된 오류는 놓침(false negative)이다. precision은 0.93~0.99로 높지만 BEEP recall은 0.55다. BEEP와 K-HATERS는 대상 없는 욕설·공격적 표현(`offensive`)도 혐오로 라벨링하는데, 모델은 이를 혐오로 보지 않는 경향이 있다. `profanity` F1 0.36이 같은 원인을 보여준다. 이는 서비스 taxonomy와 benchmark 라벨 정의의 차이이기도 하므로, 기준을 맞출지는 별도 결정이 필요하다.
5. `identity`와 `other`는 F1 0.4대로 낮다. 대상 집단 분류는 binary 판정보다 신뢰도가 낮다.

## 4. 한계

- 공개 benchmark 성능이며 실제 YouTube 댓글·자막 정확도가 아니다. 분포, 길이, 맥락(영상·부모 댓글)이 다르다.
- 반복 실행(`--repeat`)을 하지 않아 안정성은 측정하지 않았다. temperature 0이지만 비결정성은 남는다.
- category 채점은 benchmark 라벨로 접은 결과다. 정치 계열 세부 category 정확도는 이 평가로 알 수 없다.
- K-HATERS는 example corpus와 같은 데이터셋이라 `examples_only` 계열에 유리하다. BEEP 결과를 함께 봐야 한다.

## 5. 재현

```bash
uv run python -m experiments.build_benchmark_gold --dataset k-haters --split test \
  --sample-size 500 --min-per-category 50 \
  --input-output-path experiments/outputs/benchmark/k_haters_test_500.inputs.jsonl \
  --gold-output-path experiments/outputs/benchmark/k_haters_test_500.gold.jsonl
uv run python -m experiments.build_benchmark_gold --dataset beep --split validation \
  --input-output-path experiments/outputs/benchmark/beep_dev.inputs.jsonl \
  --gold-output-path experiments/outputs/benchmark/beep_dev.gold.jsonl

uv run python -m experiments.run_rag_experiment --persist-directory .chroma-prod \
  --input-path experiments/outputs/benchmark/beep_dev.inputs.jsonl \
  --output-path experiments/outputs/benchmark/beep_dev.results.jsonl --concurrency 8 --resume

uv run python -m experiments.evaluate_results \
  --results-path experiments/outputs/benchmark/beep_dev.results.jsonl \
  --gold-path experiments/outputs/benchmark/beep_dev.gold.jsonl \
  --json-output-path experiments/outputs/benchmark/beep_dev.eval.json
```

`.chroma-prod`는 운영 VM의 `hsr_chroma_data` volume을 복사한 것이다. 원문이 들어 있는 `experiments/outputs/`와 `.chroma*/`는 Git에 커밋하지 않는다.

실행 중 발견해 수정한 문제:

- `haiku_only`는 Chroma가 `n_results=0`을 거부해서 항상 실패했다. retriever가 k=0 collection을 건너뛰도록 고쳤다.
- runner에 retry가 없어 Upstage 429가 "all RAG vector stores are unavailable"로 기록됐다. worker와 같은 retry·gate와 query embedding cache를 추가했다.
- Anthropic 크레딧 부족(400)이 "요청 거부"로 표시됐다. `LLM_BILLING_ERROR`로 매핑했다.
