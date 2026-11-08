# 공개 벤치마크 정확도 평가 결과

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-08 KST |
| 대상 | `category-rag-v0.3.1`, three-vector RAG, `claude-haiku-4-5-20251001`, temperature 0 |
| corpus | 운영 VM `hsr_chroma_data` 사본(taxonomy 23, authoritative 8, examples 172,157)에 K-HATERS category 재매핑 적용 |
| gold | K-HATERS test 499건, BEEP dev 471건 (공개 데이터셋 원작자의 사람 라벨) |
| 비용 | Anthropic + Upstage 약 $25 (smoke·재실행 포함) |
| 결론 | three-vector RAG는 RAG 미적용 대비 정확도 0.573 → 0.748, binary F1 0.601 → 0.804 (McNemar p < 0.0001). 혐오 여부 개선은 example 검색이 주도하고, 정의 문서는 정치 category 분류를 유의하게 개선한다(F1 +0.09). |

## 1. 평가셋

`experiments.build_benchmark_gold`로 생성한다. example collection은 train split으로만 만들었으므로 test/dev split은 검색 corpus와 겹치지 않는다. train에 같은 문장이 있는 row(K-HATERS 3건)는 추가로 제외했다.

| 셋 | 원천 | 건수 | 혐오 비율 | 샘플링 | corpus와의 관계 |
| --- | --- | ---: | ---: | --- | --- |
| K-HATERS test | `humane-lab/K-HATERS` test | 499 | 79% | category별 최소 50건 보장 후 층화 | 같은 데이터셋 train이 examples에 있음 (in-distribution) |
| BEEP dev | `beep-korean-hate-speech/labeled/dev.tsv` | 471 | 68% | 전수 | license tier가 `commercial_ok`가 아니라 corpus에 없음 (out-of-distribution) |

K-HATERS는 희소 category를 평가하려고 최소 건수를 보장했다. 따라서 혐오 비율이 원본과 다르고, binary 지표는 실제 YouTube 댓글 분포를 대표하지 않는다.

채점 label space는 `gender/age/identity/profanity/other`와 K-HATERS의 `political`이다. evaluator는 모델의 정치 계열 6개 category를 `political`로, `no_target`을 `other`로 접어서 채점한다. K-HATERS의 `region`·`religion`·`disabled` 대상은 identity card 정의에 따라 `identity`로 채점한다.

## 2. 결과

95% bootstrap 구간(1,000회)이고, McNemar 검정은 `three_vector_rag` 대비 binary 정오 기준의 정확 이항 검정이다.

### 합산 970건

| variant | binary acc | binary F1 | category macro F1 | McNemar p |
| --- | ---: | ---: | ---: | ---: |
| `haiku_only` | 0.573 [0.543, 0.604] | 0.601 [0.565, 0.634] | 0.390 | < 0.0001 |
| `definitions_only` | 0.623 [0.594, 0.653] | 0.667 [0.634, 0.699] | 0.397 | < 0.0001 |
| `examples_only` | 0.739 [0.711, 0.768] | 0.795 [0.768, 0.820] | 0.484 | 0.26 |
| `three_vector_rag` | **0.748** [0.722, 0.778] | **0.804** [0.779, 0.829] | **0.493** [0.460, 0.522] | — |

### 셋별

| variant | K-HATERS acc | K-HATERS F1 | K-HATERS macro F1 | BEEP acc | BEEP F1 | BEEP macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `haiku_only` | 0.647 | 0.722 | 0.439 | 0.495 | 0.414 | 0.250 |
| `definitions_only` | 0.739 | 0.810 | 0.451 | 0.499 | 0.427 | 0.259 |
| `examples_only` | 0.792 | 0.858 | 0.551 | 0.684 | 0.704 | 0.350 |
| `three_vector_rag` | 0.808 | 0.871 | 0.556 | 0.686 | 0.704 | 0.352 |

`three_vector_rag` 합산: binary precision 0.947, recall 0.698. category F1은 gender 0.75, age 0.67, political 0.57, identity 0.51, profanity 0.37, other 0.08.

## 3. 해석

1. **RAG 효과는 유의하다.** 합산 정확도 +17.5%p, binary F1 +0.203이고 두 셋 모두 McNemar p < 0.0001이다. 검색 corpus에 없는 BEEP에서도 F1 0.414 → 0.704로 오른다.
2. **구성요소의 효과는 판정 단계마다 다르다.** 합산 기준 paired 비교 결과는 다음과 같다.

   | 비교 | 지표 | 차이 | 판단 |
   | --- | --- | ---: | --- |
   | `definitions_only` vs `haiku_only` | 정확도 | +5.0%p | 유의 (p < 0.0001). 단 BEEP 단독은 p = 0.86 |
   | `examples_only` vs `haiku_only` | 정확도 | +16.6%p | 유의 (p < 0.0001) |
   | `three_vector_rag` vs `examples_only` | 정확도 | +0.9%p | 유의하지 않음 (p = 0.26) |
   | `three_vector_rag` vs `examples_only` | political F1 | +0.091 [+0.016, +0.172] | 유의 |
   | `three_vector_rag` vs `examples_only` | category macro F1 | +0.010 [−0.016, +0.037] | 유의하지 않음 |

   혐오 여부 판정은 example 검색이 사실상 전부 설명한다. 정의 문서(taxonomy·authoritative)는 example 위에 더했을 때 정치 계열 category 판정만 유의하게 개선한다. 정치 category는 state/non-state × authority/regime/community 축 정의가 있어야 고를 수 있다는 설계 의도와 맞는다.
3. **주된 오류는 놓침이다.** precision은 0.95로 높지만 recall은 0.70이고 BEEP recall은 0.55다. 두 benchmark는 대상 없는 욕설·공격적 표현(`offensive`)도 혐오로 라벨링하는데, 모델은 이를 혐오로 보지 않는 경향이 있다(`profanity` F1 0.37). 서비스 taxonomy와 benchmark 라벨 정의의 차이이기도 하므로, 기준을 맞출지는 별도 결정이 필요하다.
4. **`other`는 거의 맞히지 못한다**(F1 0.08, support 61). benchmark의 `other`는 직업·개인 등 잔여 대상이라 모델의 `other` 판정 기준과 다르다.

## 4. K-HATERS category 매핑 버그와 corpus 재매핑

평가 중 K-HATERS loader가 실제 데이터와 다른 라벨 이름을 기대하는 것을 발견했다. loader는 `race`·`disability`를 `identity`로 매핑했지만 데이터의 실제 라벨은 `region`·`disabled`였고 `race`는 없었다. 그래서 지역·장애 혐오가 `other`로 떨어졌다. 정치 대상도 `other`로 들어갔는데, taxonomy는 `other`를 정치·보호 속성 외 대상으로 정의한다.

- loader 수정: `region`·`religion`·`disabled` → `identity`. 정치 대상은 6개 세부 category를 데이터에서 복원할 수 없으므로 category를 비운다.
- corpus 재매핑: `scripts.remap_example_categories`로 저장된 label metadata에서 재계산하며, 재임베딩은 하지 않는다. 운영 사본에서 172,157건 중 44,024건이 바뀌었다(`other` → 빈 값 27,663건, `other` → `identity` 15,894건, 복수 대상에 `identity` 추가 467건).

같은 gold로 재매핑 전후를 비교한 결과(합산, paired bootstrap 95% 구간):

| variant | 지표 | 재매핑 전 → 후 | 차이 |
| --- | --- | --- | ---: |
| `examples_only` | political F1 | 0.14 → 0.48 | +0.336 [+0.230, +0.441] |
| `examples_only` | category macro F1 | 0.386 → 0.484 | +0.096 [+0.072, +0.121] |
| `three_vector_rag` | identity F1 | 0.45 → 0.51 | +0.064 [+0.013, +0.119] |
| `three_vector_rag` | category macro F1 | 0.470 → 0.493 | +0.023 [+0.009, +0.039] |
| `three_vector_rag` | binary F1 | 0.805 → 0.804 | 변화 없음 |

잘못된 `other` 라벨이 붙은 example이 모델을 정치 category에서 멀어지게 하고 있었다. 재매핑 전에는 정의 문서가 이 오류를 상당 부분 상쇄해서, three-vector와 examples-only의 political F1 차이가 +0.43으로 과대 측정됐다. 위 2절의 수치는 재매핑 후 기준이다.

운영 VM 적용 상태: 2026-11-08 현재 패치 코드가 VM `/tmp/hsr-remap`에 올라가 있고, worker 정지·백업·적용은 운영자 실행 대기 중이다.

## 5. 한계

- 공개 benchmark 성능이며 실제 YouTube 댓글·자막 정확도가 아니다. 분포, 길이, 맥락(영상·부모 댓글)이 다르다.
- 반복 실행(`--repeat`)을 하지 않아 안정성은 측정하지 않았다.
- `political`은 6개 세부 category를 하나로 묶은 채점이다. state/non-state 축과 대상 유형의 정확도는 이 평가로 알 수 없다.
- K-HATERS는 example corpus와 같은 데이터셋이라 example 계열에 유리하다. BEEP 결과를 함께 봐야 한다.

## 6. 재현

```bash
uv run python -m experiments.build_benchmark_gold --dataset k-haters --split test \
  --sample-size 500 --min-per-category 50 \
  --input-output-path experiments/outputs/benchmark/k_haters_test_500.inputs.jsonl \
  --gold-output-path experiments/outputs/benchmark/k_haters_test_500.gold.jsonl
uv run python -m experiments.build_benchmark_gold --dataset beep --split validation \
  --input-output-path experiments/outputs/benchmark/beep_dev.inputs.jsonl \
  --gold-output-path experiments/outputs/benchmark/beep_dev.gold.jsonl

uv run python -m scripts.remap_example_categories --persist-directory .chroma-prod --apply

uv run python -m experiments.run_rag_experiment --persist-directory .chroma-prod \
  --input-path experiments/outputs/benchmark/beep_dev.inputs.jsonl \
  --output-path experiments/outputs/benchmark/beep_dev.results.jsonl --concurrency 8 --resume

uv run python -m experiments.evaluate_results \
  --results-path experiments/outputs/benchmark/beep_dev.results.jsonl \
  --gold-path experiments/outputs/benchmark/beep_dev.gold.jsonl \
  --json-output-path experiments/outputs/benchmark/beep_dev.eval.json
```

현재 builder로 K-HATERS gold를 다시 만들면 매핑 수정 때문에 primary category가 달라져 표본이 바뀐다. 이 문서의 K-HATERS 수치는 최초 499건 item id를 유지하고 수정된 매핑으로 정답만 재생성한 결과다. `.chroma-prod`는 운영 VM volume 사본이고, 원문이 들어 있는 `experiments/outputs/`와 `.chroma*/`는 Git에 커밋하지 않는다.

실행 중 발견해 수정한 문제:

- `haiku_only`는 Chroma가 `n_results=0`을 거부해서 항상 실패했다. retriever가 k=0 collection을 건너뛰도록 고쳤다.
- runner에 retry가 없어 Upstage 429가 "all RAG vector stores are unavailable"로 기록됐다. worker와 같은 retry·gate와 query embedding cache를 추가했다.
- Anthropic 크레딧 부족(400)이 "요청 거부"로 표시됐다. `LLM_BILLING_ERROR`로 매핑했다.
- K-HATERS 대상 라벨 매핑 오류(4절).
