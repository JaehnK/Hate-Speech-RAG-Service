# Jev 1차 필터 cascade 실험

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-09 KST |
| 구조 | TypeSafe Jev(`jev-1.14.0`, noul 질문 `jev-gate-v1`)가 혐오 확률이 threshold 미만인 댓글을 정상으로 확정하고, 나머지는 기존 three-vector RAG + Haiku로 분류 |
| 목적 | 정확도 비열등성을 유지하면서 LLM 호출을 줄일 수 있는지 확인 |
| 비열등성 기준 (사전 고정) | cascade − RAG의 binary F1 차이 95% 구간 하한 > −0.01, recall 손실 ≤ 0.02 |
| 결론 | **기준 충족.** benchmark 970건 중 13.9%가 LLM을 건너뛰고 binary F1 차이 −0.001 [−0.003, 0.000]. 실제 YouTube 댓글 표본에서는 17.4%가 걸러져 분석 비용을 약 17% 줄인다. |

## 1. 방법

Jev는 생성형 LLM이 아니라 yes/no 질문에 확률을 돌려주는 결정 모델이다. 질문은 욕설·모욕도 "yes"에 포함하도록 넓게 잡았다. 그래서 cascade는 한 방향으로만 Jev를 믿는다. 확실히 정상인 댓글만 정상으로 확정하고, 애매한 것은 모두 RAG로 보낸다.

> Is this Korean online comment hate speech or offensive/abusive language (attacking or insulting a person or group, including profanity)?

threshold는 test를 보지 않고 튜닝셋에서 정했다.

- 튜닝셋: K-HATERS validation 500건(test와 같은 층화 방식)과 BEEP train 500건. BEEP는 검색 corpus에 없다.
- 규칙: 0.01 간격에서 "정답 혐오 중 걸러지는 비율(leakage)"이 2% 이하인 가장 큰 값을 고른다. leakage는 recall 손실의 상한이다. cascade는 걸러진 혐오 중 RAG가 원래 맞혔을 것만 잃기 때문이다.
- 결과: **threshold 0.07**(Jev p < 0.07이면 LLM 생략). 튜닝셋에서 leakage 1.7%, 필터율 11.5%였다.

test는 기존 three-vector RAG 결과(docs/46, 970건)를 그대로 쓰고, 걸러진 item만 정상으로 바꿔 시뮬레이션했다. LLM은 새로 호출하지 않는다.

## 2. 결과 (benchmark 970건)

| 지표 | three-vector RAG | Jev cascade | 차이 [95% paired bootstrap] |
| --- | ---: | ---: | ---: |
| binary 정확도 | 0.7485 | 0.7474 | −0.001 [−0.003, 0.000] |
| binary precision | 0.947 | 0.947 | −0.000 |
| binary recall | 0.698 | 0.697 | −0.001 [−0.004, 0.000] |
| binary F1 | 0.804 | 0.803 | −0.001 [−0.003, 0.000] |
| category macro F1 | 0.493 | 0.493 | −0.001 [−0.002, 0.000] |

- LLM 생략 135건(13.9%). McNemar: RAG만 맞힌 1건, cascade만 맞힌 0건(p = 1.0).
- 걸러진 정답 혐오는 17건(test leakage 2.4%)이지만 그중 16건은 RAG도 놓친 것이었다. 실제 손실은 RAG가 맞힌 혐오 1건이다. 걸러진 item 중 RAG가 오탐한 것은 없었다.
- benchmark는 혐오 비율이 68~79%라 필터율이 낮게 나온다.

## 3. 실제 YouTube 댓글에서의 필터율

legacy 수집 YouTube 댓글 21,987건에서 1,000건을 무작위 추출(seed 20261109)해 Jev 점수를 받았다. 사람 라벨이 없으므로 정확도가 아니라 필터율만 본다.

| threshold | 필터율 | legacy 파이프라인이 혐오로 본 댓글 중 걸러진 비율 |
| --- | ---: | ---: |
| 0.05 | 10.7% | 0.0% |
| **0.07 (채택)** | **17.4%** | 0.8% |
| 0.10 | 26.7% | 0.8% |

legacy 라벨 기준 혐오 비율은 12.5%지만 Jev가 확실한 정상으로 보는 댓글은 17% 정도다. 넓은 질문과 보수적 threshold 때문이다. 0.10 행은 참고용이며 threshold를 바꾸려면 YouTube gold set으로 다시 검증해야 한다.

## 4. 비용

| 항목 | 건당 |
| --- | ---: |
| three-vector RAG (Haiku 입력 약 3,600 · 출력 약 510 토큰 + Upstage 임베딩) | 약 $0.006 |
| Jev (입력 약 340 토큰, $0.042 / 1M) | 약 $0.00002 |

YouTube 필터율 17.4%를 적용하면 댓글 1,000건당 약 $1을 아끼고 Jev 비용은 약 $0.02다. 지연은 RAG로 가는 item마다 Jev 호출 약 0.2초가 더해진다.

## 5. 한계와 판단

- 정확도는 공개 benchmark 기준이다. YouTube 표본은 필터율만 측정했고 걸러진 댓글의 정답은 확인하지 않았다.
- threshold 규칙을 정하기 전에 test의 threshold별 leakage 표를 한 번 출력했다. threshold 자체는 튜닝셋 규칙으로만 정했다.
- Jev 모델 버전(`jev-latest`)이 바뀌면 점수 분포가 달라질 수 있으므로 서비스에 넣으려면 버전 고정과 재검증이 필요하다.
- 절감 폭(약 17%)은 정확도 손실 없이 얻을 수 있는 확실한 이득이지만 크지 않다. 서비스 적용은 feature flag(기본 off)로 넣고, 걸러진 item은 보고서에 "Jev 필터로 정상 판정"으로 표시하는 방식을 권장한다.

## 6. 재현

```bash
B=experiments/outputs/benchmark
uv run python -m experiments.build_benchmark_gold --dataset k-haters --split validation \
  --sample-size 500 --min-per-category 50 \
  --input-output-path $B/k_haters_val_500.inputs.jsonl --gold-output-path $B/k_haters_val_500.gold.jsonl
uv run python -m experiments.build_benchmark_gold --dataset beep --split train --sample-size 500 \
  --input-output-path $B/beep_train_500.inputs.jsonl --gold-output-path $B/beep_train_500.gold.jsonl

for n in k_haters_val_500 beep_train_500 k_haters_test_500 beep_dev; do
  uv run python -m experiments.run_jev_scores --input-path $B/$n.inputs.jsonl \
    --output-path $B/$n.jev.jsonl --concurrency 8 --resume
done

uv run python -m experiments.simulate_jev_cascade \
  --tuning $B/k_haters_val_500.jev.jsonl $B/k_haters_val_500.gold.jsonl \
  --tuning $B/beep_train_500.jev.jsonl $B/beep_train_500.gold.jsonl \
  --test $B/k_haters_test_500.jev.jsonl $B/k_haters_test_500.gold.v2.jsonl $B/k_haters_test_500.results.v2.jsonl \
  --test $B/beep_dev.jev.jsonl $B/beep_dev.gold.jsonl $B/beep_dev.results.v2.jsonl \
  --json-output-path $B/jev_cascade.eval.json
```

`TYPESAFE_API_KEY`가 `.env`에 있어야 한다. Jev 점수 수집 비용은 2,970건에 $0.05 미만이다.
