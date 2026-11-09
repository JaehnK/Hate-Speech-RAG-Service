# Jev 1차 필터 cascade 실험

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-09 KST |
| 구조 | TypeSafe Jev(`jev-1.14.0`, noul 질문 `jev-gate-v1`)가 혐오 확률이 threshold 미만인 댓글을 정상으로 확정하고, 나머지는 기존 three-vector RAG + Haiku로 분류 |
| 목적 | 정확도 비열등성을 유지하면서 LLM 호출을 줄일 수 있는지 확인 |
| 비열등성 기준 (사전 고정) | cascade − RAG의 binary F1 차이 95% 구간 하한 > −0.01, recall 손실 ≤ 0.02 |
| 결론 | **기준 충족.** benchmark 970건 중 13.9%가 LLM을 건너뛰고 binary F1 차이 −0.001 [−0.003, 0.000]. 실제 YouTube 댓글 표본에서는 17.4%가 걸러져 분석 비용을 약 17% 줄이고, 걸러진 174건 중 RAG가 혐오로 보는 것은 1건(0.6%)이다. |

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

### 걸러진 댓글 재확인

threshold 0.07에서 걸러진 174건을 three-vector RAG로 다시 분류했다(사람 라벨 대신 기존 파이프라인을 기준으로 삼은 확인). 사전 기준은 "RAG가 혐오로 보는 것이 0~2건"이었다.

- 결과: **174건 중 1건(0.6%)**, 기준 충족. 나머지 173건은 RAG도 정상(`unclassified`)으로 판정했다.
- 그 1건은 실제 혐오다. 정중한 질문 형식 안에 민족 멸칭(`짱께`)이 들어 있고 Jev 점수는 0.05였다. legacy 파이프라인도 혐오로 판정했다.
- 판단: 사전 기준 안의 결과이므로 이 1건을 막는 추가 규칙(멸칭 사전, 실패 사례에 맞춘 Jev 질문)은 넣지 않았다. 1건을 보고 만든 규칙은 검증되지 않은 사후 조정이고, 기준을 통과한 뒤 규칙을 덧대면 사전 검증의 의미가 없어진다. 대신 잔여 누락률(약 0.6%)과 유형(공손한 어조 속 멸칭)을 알려진 위험으로 기록한다.

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
- 절감 폭(약 17%)은 정확도 손실 없이 얻을 수 있는 확실한 이득이지만 크지 않다.
- BYOK 구조상 절감액은 사용자 Anthropic·Upstage 비용에서 생기고, Jev 비용(1,000건당 약 $0.02)과 외부 의존성은 운영자가 진다. 댓글 원문이 TypeSafe로 추가 전송되므로 활성화 전 처리방침에 반영해야 한다.
- 후속 과제(v2): Jev 질문을 실패 사례가 아니라 서비스 taxonomy 정의에서 만든다. taxonomy category와 "해당 없음"을 choice 질문 선택지로 주고 "해당 없음" 확률로 거르면, RAG와 같은 정의를 기준으로 삼게 된다. 별도 실험으로 같은 절차(튜닝셋 threshold, benchmark 비열등성, YouTube 재확인)를 거친다.

## 5-1. 서비스 적용

`JEV_PREFILTER_ENABLED=true`일 때 worker가 각 RAG classifier를 `JevGatedClassifier`(`app/analysis/jev_gate.py`)로 감싼다. 기본값은 off다.

| 설정 | 기본값 | 의미 |
| --- | --- | --- |
| `JEV_PREFILTER_ENABLED` | `false` | gate 사용 여부 |
| `TYPESAFE_API_KEY` | 없음 | 서버 공용 키. 활성화 시 필수 (없으면 설정 검증 실패) |
| `JEV_MODEL` | `jev-1.14.0` | 이 문서에서 검증한 버전으로 고정. `jev-latest`는 쓰지 않는다 |
| `JEV_THRESHOLD` | `0.07` | 이 값 미만이면 LLM 생략 |

- Jev 점수가 threshold 미만이면 retrieval과 LLM 없이 "혐오 아님"으로 저장한다. `rag_context_status=jev_filtered`, `model_name=jev-1.14.0`, `prompt_version=jev-gate-v1`, reasoning에 Jev 점수를 남긴다.
- 웹 보고서와 프론트는 이 항목의 근거를 "Jev 사전 필터로 혐오 아님 판정 (LLM 미사용)"으로 표시한다.
- Jev 호출이 실패하면(재시도 1회 후) 그 item은 그대로 RAG로 보낸다. gate 때문에 item이 실패하는 경우는 없다.
- `analysis_runs.retriever_config.jev_prefilter`에 활성 여부, 모델, threshold, 질문 버전을 기록한다.

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
