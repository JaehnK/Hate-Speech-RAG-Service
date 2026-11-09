# 프롬프트 v0.6.2 · taxonomy v0.5.1 · 규범 corpus 평가 결과

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-09 KST |
| 대상 | `category-rag-v0.6.2`, taxonomy v0.5.1, 규범·기준 문서 58 chunk, `claude-haiku-5-5` (effort low) |
| 비교 기준 | 이전 운영 구성 `category-rag-v0.3.1`, taxonomy v0.3.0, `claude-haiku-4-5-20251001` (docs/46) |
| 튜닝셋(dev) | K-HATERS validation 500 + BEEP train 500 = 1,000건. 모든 프롬프트·taxonomy 선택은 여기서만 했다 |
| 평가셋(test) | K-HATERS test 499 + BEEP dev 471 = 970건. 최종 구성을 정한 뒤 한 번만 사용했다 |
| 채점 | category는 taxonomy v0.5 체계(`other` → `profanity` 통합)로 정답과 예측을 같이 바꿔 채점(`--merge-other`) |
| 결론 | 정확도는 동등 이상(F1 0.804 → 0.818, precision 유의 개선)이고, 비용은 댓글 1,000개당 $6.13 → $1.45(약 76% 절감). 혐오 판정의 94%가 규범·기준 문서를 근거로 인용한다. Sonnet 5.5는 비용 17배에 유의한 향상이 없었다. |

## 1. 경위: 최신 모델에서 정확도가 떨어진 원인

Claude 5 세대 모델을 기존 프롬프트(v0.3.1)로 test셋에 돌리자 정확도가 크게 떨어졌다(Haiku 5.5 F1 0.633, Sonnet 5.5 0.674, 기존 Haiku 4.5 0.804). precision은 0.96~0.98로 높고 recall만 0.47~0.51로 낮아, 판정 기준을 좁게 적용한 것으로 보였다.

놓친 사례를 보니 대부분 개인 조롱·모욕이었고, 모델은 "공격적이지만 보호 속성 집단을 향하지 않은 표현(Offensive)"이라 혐오가 아니라는 근거를 댔다. 원인은 판정 기준이 문서마다 달랐던 데 있다.

| 출처 | 개인 모욕·조롱은 혐오인가 |
| --- | --- |
| 서비스 taxonomy `profanity` 카드 | 예 |
| 서비스 taxonomy `hate_threshold` 카드 | 아니오(정체성 근거와 "심각한 모욕" 요구) |
| authoritative collection의 K-HATERS README | 아니오(offensive와 hate를 구분) |
| 프롬프트 | 기준을 명시하지 않고 authoritative를 "primary external standard"로 지정 |
| 정답 매핑(offensive → 혐오) | 예 |

Haiku 4.5는 이 지시를 덜 따라 넓은 기준의 정답과 맞았고, 지시를 충실히 따르는 5 세대 모델은 좁게 판정했다.

## 2. 튜닝 과정 (dev 1,000건, Haiku 5.5)

| 버전 | 변경 | precision | recall | F1 |
| --- | --- | ---: | ---: | ---: |
| v0.3.1 | 기존 프롬프트 | 0.977 | 0.549 | 0.703 |
| v0.4.0 | 프롬프트에 서비스 판정 기준(집단 혐오 + 사람을 향한 모욕) 명시 | 0.949 | 0.698 | 0.805 |
| v0.4.1 | 규범 문서는 라벨 해석용이고 판정을 좁히지 않는다고 우선순위 명시 | 0.950 | 0.711 | 0.813 |
| v0.5.0 | 판정 기준을 taxonomy `hate_threshold`로 옮기고 판정 규칙 card 고정 | 0.936 | 0.768 | 0.844 |
| v0.6.1 | 규범 corpus + 유사 사례 유도 검색 | 0.938 | 0.760 | 0.840 |
| v0.6.2 + taxonomy v0.5.0 | category 통합(`other` → `profanity`) | 0.912 | 0.773 | 0.837 |
| **v0.6.2 + taxonomy v0.5.1** | 모욕 기준을 "깎아내리거나 망신 주려는"으로 좁히고 가벼운 감상·농담 제외 | 0.945 | 0.741 | 0.831 |

비교 기준인 Haiku 4.5 + v0.3.1은 dev에서 precision 0.940, recall 0.740, F1 0.828이다.

- v0.5.0: 판정 기준 card가 검색 상위 4건에 드는 비율이 78%뿐이어서, 정의를 taxonomy에 두려면 card 고정이 필요했다.
- v0.6.2 + taxonomy v0.5.0: 통합한 `profanity` 정의에 "욕설 없는 조롱·비꼼"이 들어가 "잘생겼는데 얼굴 아깝다" 같은 감상까지 혐오로 판정했다(오탐 18건 증가). v0.5.1에서 문구를 좁혀 precision을 되돌렸다.

### 검색 층별 효과 (dev, v0.5.0)

K-HATERS README(authoritative)를 빼도 혐오 여부 F1 차이는 −0.000 [−0.012, +0.011]이었다. category별로는 `profanity`만 +0.047 [+0.007, +0.085] 개선됐다. docs/46에서 "정의 문서가 정치 category를 개선한다(+0.09)"고 한 효과는 taxonomy card와 README를 묶어 잰 것이고, README 단독 효과는 없었다.

### 규범 문서 검색 품질 (dev 혐오 300건, LLM 없이 측정)

| 방식 | category 일치율 | 심각도 수준 일치율 |
| --- | ---: | ---: |
| 댓글로 직접 검색(v0.6.0) | 37.8% | 35.8% |
| 문서마다 댓글형 적용 예 추가 | 30.3% | 29.2% |
| 유사 사례 category로 유도(v0.6.1) | 54.9% | 45.5% |

적용 예 추가는 모델이 만든 예시가 조각마다 비슷해져 오히려 나빠졌으므로 채택하지 않았다. `experiments/normative_retrieval_probe.py`로 재현한다.

## 3. 최종 결과 (test 970건)

| 구성 | 정확도 | precision | recall | F1 [95% CI] | category macro F1 | 근거 인용 | 댓글 1,000개당 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 이전 운영 Haiku 4.5 + v0.3.1 | 0.748 | 0.947 | 0.698 | 0.804 [0.779, 0.829] | 0.597 | 없음 | $6.13 |
| **Haiku 5.5 + v0.6.2** | 0.767 | 0.964 | 0.711 | 0.818 [0.795, 0.841] | 0.600 | 94% (498/528) | $1.45 |
| **Jev + Haiku 5.5** | 0.767 | 0.964 | 0.711 | 0.818 | 0.600 | 94% | $1.25 |
| Sonnet 5.5 + v0.6.2 | 0.779 | 0.965 | 0.728 | 0.830 | 0.611 | 97% (525/540) | $24.46 |

paired bootstrap 95% 구간:

| 비교 | 정확도 | precision | recall | F1 | category macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Haiku 5.5 − 이전 운영 | +0.019 [−0.003, +0.041] | **+0.017 [+0.001, +0.034]** | +0.013 [−0.016, +0.041] | +0.014 [−0.005, +0.035] | +0.003 [−0.029, +0.031] |
| Sonnet 5.5 − Haiku 5.5 | +0.012 [−0.005, +0.031] | +0.001 [−0.012, +0.013] | +0.017 [−0.004, +0.041] | +0.011 [−0.004, +0.028] | +0.011 [−0.015, +0.036] |

- Haiku 5.5와 이전 운영의 McNemar p = 0.12, Sonnet과 Haiku 5.5는 p = 0.23.
- Jev(threshold 0.07, docs/47에서 튜닝셋으로 고정)는 135건(13.9%)에서 LLM을 생략했고, 그중 Haiku 5.5가 혐오로 맞혔을 사례는 0건이라 지표가 같다.
- 비용은 실측 평균 토큰(Haiku 5.5 입력 8,978 · 출력 1,100, Haiku 4.5 3,597 · 507, Sonnet 8,978 · 650)과 단가로 계산했다. 규범 문서가 들어가 입력은 약 2.5배가 됐지만 단가가 낮아 전체 비용은 줄었다.
- 이 결과로 분석 방식 선택지는 절약(Jev + Haiku 5.5)과 기본(Haiku 5.5) 두 개로 정했다.

### 데이터셋별·정의별 재채점

| 채점 | 이전 운영 F1 | Haiku 5.5 F1 | Sonnet 5.5 F1 |
| --- | ---: | ---: | ---: |
| K-HATERS (검색 corpus와 같은 데이터셋) | 0.871 | 0.882 | 0.898 |
| BEEP (corpus에 없는 데이터셋) | 0.704 | 0.725 | 0.728 |
| 엄격 기준(offensive를 비혐오로) | 0.733 | 0.742 | 0.737 |
| 엄격 기준(offensive 사례 제외, 648건) | 0.889 | 0.906 | 0.909 |

순서와 결론은 데이터셋과 혐오 정의를 바꿔도 같다. Haiku 5.5와 이전 운영의 차이는 모든 경우 유의하지 않고, Sonnet은 K-HATERS에서만 이전 운영보다 유의하게 높다(McNemar p = 0.035). BEEP에서 Haiku 5.5의 precision은 1.000이고 recall은 0.568이다. BEEP는 약한 공격적 표현까지 넓게 라벨링하기 때문이다.

### category 점수가 오르지 않는 이유

1. 정답이 혐오인 716건 중 207건(29%)을 혐오로 판정하지 않아, category 점수는 혐오 판정 recall에 묶인다.
2. 서비스 taxonomy는 표적 category와 `profanity`를 함께 붙이지만, 정답 매핑은 표적이 없을 때만 `profanity`다(정답의 93%가 라벨 1개). 표적을 맞히고 욕설·모욕을 함께 붙인 114건이 `profanity` 오탐으로 계산된다.
3. 정치 라벨은 K-HATERS에만 있어 BEEP 댓글의 정치 판정은 모두 오답이 되고, BEEP의 `others` 편견은 외모·나이 등이 섞인 채 `identity`로 매핑된다.

공개 benchmark의 category 점수는 라벨 체계 차이로 과소평가되어 있다. 서비스 taxonomy 기준 정답셋이 필요하다(docs/48).

## 4. 반복 일관성

5 세대 모델은 temperature를 고정할 수 없다. dev 200건을 3회 반복한 결과는 측정 후 기록한다.

## 5. 한계

- 공개 benchmark 성능이며 실제 YouTube 댓글 정확도가 아니다. 실제 YouTube 정답셋은 아직 없다.
- 정답의 혐오 정의(offensive 포함)와 category 매핑은 서비스가 정한 것이다. 3절의 재채점으로 결론이 정의에 따라 바뀌지 않음을 확인했다.
- 근거 인용률은 인용 여부만 센 것이며, 인용한 조항이 적절한지는 표본 확인 수준이다.
- 국제 기준·플랫폼 정책·데이터셋 논문 카드 일부는 에이전트가 원문을 확인해 작성했고 형식 검사만 자동화되어 있다.

## 6. 재현

```bash
B=experiments/outputs/benchmark
# dev store: 운영 사본에 taxonomy v0.5.1과 규범 corpus 적재
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-dev --reset --embedding-provider upstage
uv run python -m app.analysis.normative_corpus --persist-directory .chroma-dev --embedding-provider upstage

LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-dev \
  --variant three_vector_rag --prompt-version category-rag-v0.6.2 \
  --input-path $B/combined.inputs.jsonl --output-path $B/test.claude-haiku-5-5.v062-t051.results.jsonl \
  --concurrency 12 --embedding-cache $B/test.query_vectors.json --resume

uv run python -m experiments.evaluate_results --merge-other \
  --results-path $B/test.claude-haiku-5-5.v062-t051.results.jsonl --gold-path $B/combined.gold.v2.jsonl

uv run python -m experiments.simulate_jev_cascade --merge-other \
  --tuning $B/k_haters_val_500.jev.jsonl $B/k_haters_val_500.gold.jsonl \
  --tuning $B/beep_train_500.jev.jsonl $B/beep_train_500.gold.jsonl \
  --test $B/combined.jev.jsonl $B/combined.gold.v2.jsonl $B/test.claude-haiku-5-5.v062-t051.results.jsonl
```
