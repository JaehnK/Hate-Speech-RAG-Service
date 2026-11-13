# 프롬프트 v0.7.1 · 영상 제목 문맥 (실험)

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-13 KST |
| 계기 | v0.7.0은 댓글 문장만 봐서 "뇌가 없다", "밖에 나오지마라"처럼 영상 속 인물을 향한 말을 판단하지 못했다(docs/52 §5) |
| 대상 | `category-rag-v0.7.1`, taxonomy v0.6.1, `claude-haiku-5-5`. 비교 기준은 `category-rag-v0.7.0`, taxonomy v0.6.0 |
| 결론 | 처음 보는 영상 2개(200건)에서 3분류 정확도 0.730 → 0.775, 집단 혐오 F1 0.626 → 0.708. McNemar p = 0.175라 유의하지 않다. 기존 정답셋은 비슷하고(0.714 → 0.709), 젠슨 황 세트는 크게 좋아졌다(0.829 → 0.928). 운영 기본값은 아직 v0.7.0이다 |

## 1. 변경

| 영역 | 변경 |
| --- | --- |
| 입력 | worker가 job의 최신 영상 제목(`video_metadata_snapshots.title`)을 댓글·자막 분류에 넘긴다. prompt는 v0.7.1에서만 `Video title JSON` 한 줄을 넣는다. 검색 쿼리에는 넣지 않는다 |
| prompt 규칙 | 제목은 입력이 누구를 가리키는지 정하는 데만 쓴다. 제목의 표현이나 주제가 입력을 혐오로 만들지 않고, 제목이 집단을 다룬다는 이유만으로 `group`이 되지 않는다 |
| taxonomy v0.6.1 | `hate_threshold` 카드: 제목이 다루는 집단을 묶어 동물·질병·벌레에 빗대거나 열등성을 일반화하면 `group`, 영상 속 사람의 특정 행동에 대한 분노·욕설은 `individual`, 주제에 대한 반응·관찰·탄식·의견은 모욕이 없으면 비혐오 |

첫 시도(규칙 없이 제목만 추가, 아래 표의 "v0.7.1 초안")는 제목이 집단을 다루면 "또 70대야?", "중국은 이제 차이나 하네" 같은 반응까지 집단 혐오로 끌고 갔다. 위 규칙은 그 결과를 보고 넣었다.

## 2. 정답 기준 변경

`youtube_eval300`은 댓글 문장만 보고 라벨링해서, 중국인 관광객 영상 아래 "배변훈련도 안돼있음" 같은 비인간화를 개인 모욕으로 달았다. 서비스는 영상 아래에서 댓글을 읽으므로 위 기준으로 제목을 보고 다시 라벨링해 `youtube_eval300_ctx.labels.jsonl`로 남겼다. 7건이 바뀌었고 모두 `group`이 됐다(바뀐 항목은 `previous` 필드). 모델 결과를 본 뒤의 재라벨링이라 편향이 있을 수 있어, 효과 판단은 새 세트로 한다.

`youtube_heldout200`: 대구 이슬람 사원 갈등(MBC, UKcGYaewIoQ)과 평론가 조롱 논란(MBC, zEUTKEZ_H2s)에서 `random.seed(20261113)`으로 100건씩. 모델을 돌리기 전에 위 기준으로 라벨링했다(group 39, individual 48, none 113). 라벨은 Claude 한 명이 달았다.

## 3. 결과 (Haiku 5.5)

| 세트 | 지표 | v0.7.0 | v0.7.1 초안 | v0.7.1 |
| --- | --- | ---: | ---: | ---: |
| **새 영상 200건** | 3분류 정확도 | 0.730 | | **0.775** |
| | 집단 혐오 F1 | 0.626 [0.500, 0.729] | | **0.708** [0.592, 0.800] |
| | 공격적 표현 F1 | 0.800 | | 0.809 |
| 기존 정답셋 300건 (제목 기준 재라벨) | 3분류 정확도 | 0.777 | 0.757 | 0.770 |
| | 집단 혐오 F1 | 0.714 | 0.689 | 0.709 |
| | 공격적 표현 F1 | 0.781 | 0.769 | 0.784 |
| 젠슨 황 일관성 111건 × 3 | 3분류 정확도 | 0.829 | 0.928 | 0.928 |
| | 3회 반복 일치율 (3분류) | 0.892 | 0.982 | 0.937 |

- 새 영상 200건에서 v0.7.0만 맞힌 항목은 13건, v0.7.1만 맞힌 항목은 22건이었다(p = 0.175).
- 평론가 영상에서는 집단 혐오 오탐이 14건에서 7건으로 줄었다. 대상이 김준일 개인이라는 것을 제목으로 알게 됐다.
- 이슬람 사원 영상은 비슷했다(정확도 0.77 → 0.79, 오탐 15 → 16).
- 중국인 관광객 영상에서는 집단 혐오 판정이 늘었다(오탐 10 → 21). 대부분 "무식한 인간들", "뇌가 없다", "조류독감이나 걸려라"처럼 영상 속 관광객을 향한 욕을 모델이 국적 집단 혐오로 본 경우다. 정답은 비인간화나 일반화가 없어 `individual`로 뒀지만, 경계가 애매한 사례다. "쎼쎼만 해야지", "혹시 저녁 거리로 사냥???"처럼 명백히 잘못 읽은 경우도 있다.

## 4. 남은 문제

1. 집단을 다루는 영상 아래에서 영상 속 사람에게 하는 욕을 `group`과 `individual` 중 어디로 볼지. 지금 기준은 "비인간화·일반화가 있으면 group"이다. 이 경계가 바뀌면 집단 혐오 비율이 크게 달라진다.
2. 모든 정답은 Claude 한 명이 라벨링했다.
3. 새 영상 세트가 200건이라 차이를 확정하기에 작다.

## 5. 재현

```bash
Y=experiments/outputs/youtube
uv run python -m experiments.fetch_youtube_comments UKcGYaewIoQ zEUTKEZ_H2s --output-path $Y/heldout_pool.inputs.jsonl
# 영상별 random.seed(20261113) 후 random.sample(pool, 100) -> $Y/heldout200.inputs.jsonl
# 기존 세트는 inputs에 video_title을 더한다(fetch_youtube_comments가 이제 함께 저장한다)

# v0.7.1 store: v0.7 store 사본에 taxonomy v0.6.1 적재
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-v071 --embedding-provider upstage --reset

LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-v071 \
  --variant three_vector_rag --prompt-version category-rag-v0.7.1 \
  --input-path $Y/heldout200.inputs.jsonl --output-path $Y/heldout200.claude-haiku-5-5.v071b.results.jsonl \
  --concurrency 5 --embedding-cache $Y/heldout200.query_vectors.json --resume

uv run python -m experiments.evaluate_youtube --results $Y/heldout200.claude-haiku-5-5.v071b.results.jsonl \
  --gold experiments/gold_labels/youtube_heldout200.labels.jsonl
```
