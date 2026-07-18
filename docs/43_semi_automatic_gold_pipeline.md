# 반자동 gold 구축 파이프라인

| 항목 | 값 |
| --- | --- |
| 기준일 | 2026-07-18 KST |
| 목적 | 레거시 실제 결과셋을 활용해 현재 three-vector RAG의 검수 큐와 gold 후보를 만든다. |
| 원칙 | 모델 산출값은 정답이 아니라 참고 라벨이다. 자동 합의 row도 최종 gold가 아니라 `auto_candidate`다. |

## 1. 파이프라인

```text
legacy workbook
  → experiment input JSONL
  → current three-vector RAG 재분석
  → legacy/current/(judge) 대조
  → auto_candidate / needs_review 큐 생성
  → 사람이 needs_review 우선 검수
  → 확정 gold JSONL
```

현재 구현된 범위:

| 단계 | 구현 |
| --- | --- |
| legacy workbook 변환 | `experiments.prepare_legacy_gold convert` |
| current RAG 실행 | 기존 `experiments.run_rag_experiment` 사용 |
| legacy/current 대조 큐 | `experiments.prepare_legacy_gold queue` |
| LLM judge | 포맷만 준비, 후속 구현 |
| 사람 검수 UI/툴 | 후속 구현 |

## 2. 변환 명령

실제 댓글 legacy RAG 결과:

```bash
uv run python -m experiments.prepare_legacy_gold convert \
  --source legacy-comments \
  --workbook-path legacy/hateSpeechRAG/scripts/youtube_comments_20250909_111405.xlsx \
  --input-output-path experiments/outputs/legacy_comments.inputs.jsonl \
  --legacy-output-path experiments/outputs/legacy_comments.labels.jsonl
```

실제 자막/스크립트 legacy RAG 결과:

```bash
uv run python -m experiments.prepare_legacy_gold convert \
  --source legacy-scripts \
  --workbook-path legacy/hateSpeechRAG/scripts/scripts.xlsx \
  --input-output-path experiments/outputs/legacy_scripts.inputs.jsonl \
  --legacy-output-path experiments/outputs/legacy_scripts.labels.jsonl
```

실제 댓글 인터코더 결과셋:

```bash
uv run python -m experiments.prepare_legacy_gold convert \
  --source intercoder \
  --workbook-path legacy/YouTubeHateSpeech/ergm/Comment_.xlsx \
  --input-output-path experiments/outputs/legacy_intercoder.inputs.jsonl \
  --legacy-output-path experiments/outputs/legacy_intercoder.labels.jsonl
```

`*.inputs.jsonl`에는 원문 텍스트가 포함된다. 이 파일은 Git에 커밋하지 않는다. `experiments/outputs/`는 `.gitignore` 대상이다.

## 3. 현재 RAG 재분석

예시:

```bash
uv run python -m experiments.run_rag_experiment \
  --input-path experiments/outputs/legacy_comments.inputs.jsonl \
  --output-path experiments/outputs/legacy_comments.current.jsonl \
  --variant three_vector_rag \
  --repeat 1
```

비용을 줄이려면 먼저 `--limit 100`으로 smoke를 실행한다.

## 4. 검수 큐 생성

```bash
uv run python -m experiments.prepare_legacy_gold queue \
  --legacy-label-path experiments/outputs/legacy_comments.labels.jsonl \
  --current-results-path experiments/outputs/legacy_comments.current.jsonl \
  --output-path experiments/outputs/legacy_comments.review_queue.jsonl
```

큐 판정:

| 상태 | 의미 |
| --- | --- |
| `auto_candidate` | legacy와 current가 binary/category 기준으로 일치한 후보 |
| `needs_review` | legacy/current 불일치, current 실패, 또는 legacy에 혐오표현 라벨이 없는 row |

`Comment_.xlsx`의 `FC`는 혐오표현 라벨이 아니므로 해당 row는 기본적으로 `needs_review`가 된다.

## 5. 해석 기준

가능:

- “legacy 결과와 current 결과의 합의/불일치 큐를 만들었다.”
- “불일치 row를 우선 검수할 수 있다.”
- “실제 댓글·자막 분포에서 현재 RAG를 재분석할 수 있다.”

불가:

- “legacy/current 일치율이 정확도다.”
- “`auto_candidate`가 최종 gold다.”
- “legacy RAG 산출값이 사람 정답이다.”

## 6. 다음 단계

1. LLM judge 산출 JSONL을 같은 queue 명령에 붙인다.
   - 검증: `--judge-label-path` 입력 시 judge 불일치 row가 `needs_review`가 된다.
2. `needs_review` 우선순위를 세분화한다.
   - 검증: binary 불일치, category 불일치, 실패, 인터코더-only를 별도 reason으로 집계한다.
3. 사람이 확정한 gold JSONL writer를 추가한다.
   - 검증: evaluator가 요구하는 `item_id`, `is_hate_speech`, `categories` 필드를 만족한다.
