# 프롬프트 v0.8.2: 프롬프트 캐싱

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-20 KST |
| 계기 | 입력이 건당 10.7k토큰(v0.5의 2.4배)인데 캐싱을 쓰지 않았다. v0.8.1은 규칙 바로 뒤에 영상 제목·댓글이 와서 매번 같은 앞부분이 712토큰뿐이었다 |
| 대상 | `category-rag-v0.8.2`, taxonomy v0.7.1, `claude-haiku-5-5`. 비교 기준은 `category-rag-v0.8.1` |
| 결론 | 판정 정확도는 같고(binary F1 0.830 → 0.830, McNemar 25:22, p = 0.77) 1,000건 비용이 $1.61 → $1.38(−14%)이다. 절감이 작고 precision이 0.016 내려가 운영에는 올리지 않는다(2026-11-20). 기본값은 v0.8.1 |

## 1. 변경

내용은 v0.8.1과 같고 순서만 바꿨다. 버전마다 같은 부분을 앞에, 입력마다 다른 부분을 뒤에 둔다.

| 위치 | 내용 | 토큰 |
| --- | --- | ---: |
| 앞부분 (캐시) | 지시문·규칙, 허용 category, 출력 JSON 형식(`input_text`는 "그대로 복사" 안내로 바꿈), 고정 카드 `hate_threshold`·`context_exception` | 2,780 |
| `[input]`부터 | 출처 유형, 영상 제목, 입력 문장, 검색된 분류 카드, 규범 문서, 유사 사례 | 약 7,900 |

`AnthropicLlmClient`는 `PROMPT_CACHE_SPLIT`(`\n[input]\n`) 앞을 `cache_control: ephemeral`(5분) 블록으로 보낸다. 모델이 받는 글자는 같고 블록만 둘로 나뉜다. 이전 버전 prompt는 한 글자도 바뀌지 않았다(11개 버전 비교). job metrics와 실험 결과에 `cache_creation_input_tokens`·`cache_read_input_tokens`를 기록하며, 이때 `input_tokens`는 캐시되지 않은 부분만이다.

Haiku 5.5의 최소 캐시 단위는 512토큰이다. 캐시 읽기는 입력 단가의 0.1배, 쓰기는 1.25배다. 한 job 안의 요청은 5분 이내로 이어지므로 첫 요청 뒤로는 계속 읽는다. 캐시는 API 키(조직)별이라 BYOK 사용자마다 따로 쓴다.

## 2. dev 1,000건

| 지표 | v0.8.1 | v0.8.2 |
| --- | ---: | ---: |
| binary F1 | 0.830 | 0.830 |
| precision / recall | 0.950 / 0.737 | 0.934 / 0.747 |
| category macro F1 (평가기 기본 축) | 0.475 | 0.476 |
| 혐오 판정 수 | 542 | 559 |
| v0.8.1만 맞음 : v0.8.2만 맞음 | | 25 : 22 (p = 0.77) |
| 입력 토큰 (전액 / 캐시 읽기) | 10,693 / 0 | 7,893 / 2,780 |
| 출력 토큰 | 1,073 | 1,132 |
| 응답 시간 중앙값 | 5.5초 | 5.1초 |
| 1,000건 비용 (Haiku 5.5 $0.10 / $0.50 per MTok) | $1.61 | $1.38 |

순서만 바꿔도 판정이 조금 흔들린다(47건이 엇갈림). 차이는 유의하지 않지만 혐오 판정이 17건 늘고 precision이 0.016 내려갔다. 출력이 건당 59토큰 늘어 절감분 일부를 깎았다.

## 3. 재현

```bash
set -a && . ./.env && set +a
B=experiments/outputs/benchmark
LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-v081 \
  --variant three_vector_rag --prompt-version category-rag-v0.8.2 \
  --input-path $B/dev.inputs.jsonl --output-path $B/dev.claude-haiku-5-5.v082.results.jsonl \
  --concurrency 6 --embedding-cache $B/dev.query_vectors.json
uv run python -m experiments.evaluate_results --results-path $B/dev.claude-haiku-5-5.v082.results.jsonl --gold-path $B/dev.gold.jsonl
```
