# 프롬프트 v0.8.0 · taxonomy v0.7.0 · 6개 category (실험)

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-13 KST |
| 계기 | 정치 6개 category(state/non_state × authority/regime/community)는 공개 정답이 "정치" 하나라 채점된 적이 없고, 체제(regime)는 거의 쓰이지 않았다. 권력 기준은 전한길처럼 직책 없는 정치 주체를, 인물 기준은 조인성·김제동처럼 정치 발언을 하는 연예인을 설명하지 못했다 |
| 대상 | `category-rag-v0.8.0`, taxonomy v0.7.0, `claude-haiku-5-5`. 비교 기준은 v0.7.0(taxonomy v0.6.0)과 v0.7.1(taxonomy v0.6.1) |
| 결론 | 집단/개인 판정은 v0.7.1과 같은 수준이고, 정치 분류는 나아졌다(dev 정치 F1 0.522 → 0.575, 정치 연예인 영상의 `political_actor` F1 0.03 → 0.44, 경계 문장 0.36 → 0.94). 운영 기본값은 아직 v0.7.0이다 |

## 1. 변경

| 영역 | 변경 |
| --- | --- |
| category | `gender`, `age`, `identity`, `political_actor`, `political_camp`, `profanity` + `unclassified` |
| `political_actor` | 이름을 대거나 특정할 수 있는 정치 주체: 현직·전직 정치인, 정당, 국가기관, 언론, 정치 평론가·유튜버·활동가. 직책·권력 유무는 따지지 않는다. 연예인·방송인은 정치적 발언·활동 때문에 공격받을 때만 해당하고, 연기·외모·사생활로 공격받으면 `profanity`만 쓴다 |
| `political_camp` | 이름 없는 다수 시민을 정치 성향으로 묶은 지지층·진영(개딸, 1찍, 좌빨, 일베충 등). `target_scope`는 항상 group |
| 이전 code | `state_authority`·`non_state_authority`·`state_regime`·`non_state_regime` → `political_actor`, `non_state_community` → `political_camp`, `state_community` → `identity`, `no_target`·`other` → `profanity` (`V07_CATEGORY_MAP`). 유사 사례 label도 이 표로 바꿔 보여 준다 |
| `target_scope` | 유지. 정치인 한 명을 이름으로 공격하면 individual, 조직 전체나 진영이면 group. 제목·댓글의 집단 속성(국적·연령·성별·종교·진영)으로 정한 사람들을 "인간들", "것들", "-들"로 묶어 모욕하면 group, 출연자 몇 명을 가리키면 individual |
| 문서 수 | 규칙 9개 + category 7개 = 16개(이전 21개) |

v0.8.0은 taxonomy v0.7.0이 적재된 store가 필요하다. 이전 prompt는 이 store와 함께 쓰지 않는다. 저장된 결과의 이전 code는 화면에서 "(이전 분류)" 이름으로 그대로 보인다.

## 2. 평가 데이터

| 세트 | 구성 | 라벨 |
| --- | --- | --- |
| `youtube_eval300_v08` | 기존 300건, 제목 기준 라벨에 "복수로 묶으면 group"을 적용(3건 변경, `previous` 필드) | group 74, individual 43, none 183 |
| `youtube_heldout200` | 이슬람 사원·평론가 영상(docs/53) | 그대로 |
| `youtube_celeb200` (신규) | "좌파 발언에 난리난 조인성 SNS"(Rg5EQRHCWi8), "난민 수용 외치던 정우성 프랑스 사태에 재조명"(zqFBTGlxvag)에서 `random.seed(20261114)`로 100건씩. 모델 실행 전에 라벨링 | group 26, individual 81, none 93. `political_actor` 75, `political_camp` 25 |
| `political_boundary` (신규, 합성) | 김제동·조인성·전한길·정당·기관·진영 경계 문장 18개와 가상의 영상 제목. 본문을 저장소에 둔다 | 3회 반복 |

라벨은 모두 Claude 한 명이 달았다.

## 3. 결과 (Haiku 5.5)

| 세트 | 지표 | v0.7.0 | v0.7.1 | v0.8.0 |
| --- | --- | ---: | ---: | ---: |
| dev 1,000 | binary F1 | 0.823 | | 0.826 (McNemar 21:25, p = 0.66) |
| | category macro F1 (5축) | 0.575 | | 0.582 |
| | 정치 F1 | 0.522 | | **0.575** |
| 새 영상 200 (docs/53) | 집단 혐오 F1 | 0.626 | 0.708 | **0.717** |
| | 3분류 정확도 | 0.730 | 0.775 | **0.785** |
| 기존 300 (v08 라벨) | 집단 혐오 F1 | 0.713 | **0.730** | 0.690 |
| | 3분류 정확도 | 0.773 | **0.780** | 0.760 |
| 정치 연예인 200 | 집단 혐오 F1 | | 0.667 | 0.677 |
| | `political_actor` F1 | | 0.026 | **0.440** |
| | `political_camp` F1 | | 0.745 | 0.727 |
| 경계 문장 18 × 3 | `political_actor` F1 | | 0.364 | **0.941** |
| | 3분류 정확도 / 반복 일치율 | | 0.944 / 1.00 | 0.944 / 1.00 |

- v0.7.1의 `political_actor` 점수는 이전 code를 표로 바꿔 채점했다. v0.7.1은 연예인을 정치 주체로 보지 않아 거의 `profanity`로만 분류했다.
- 집단/개인 판정의 차이는 모두 신뢰구간 안이다. 기존 300건에서는 v0.8.0이 조금 낮고 새 영상 200건에서는 조금 높다.
- 정치 연예인 영상에서 놓친 `political_actor` 51건은 대부분 "무식해서 그래", "대가리가 비어서", "비굴한"처럼 정치 발언을 제목으로만 알 수 있는 짧은 욕이다. 모델은 `profanity`만 붙였다. 집단/개인 판정(individual)은 맞았다. 이 댓글을 정치 발언 때문에 하는 공격으로 볼지는 라벨 기준의 문제이기도 하다.

## 4. 남은 문제

1. 제목으로만 정치적 맥락이 드러나는 짧은 욕을 `political_actor`로 볼지.
2. 직업 집단(딴따라, 평론가들)에 대한 공격의 `target_scope`가 정의에 없다. 이번 라벨은 정치 평론가 집단은 group, 연예인 직업군은 individual로 달았다.
3. 라벨은 한 명(Claude)이 달았다.

## 5. 재현

```bash
Y=experiments/outputs/youtube; G=experiments/gold_labels
uv run python -m experiments.fetch_youtube_comments Rg5EQRHCWi8 zqFBTGlxvag --output-path $Y/celeb_pool.inputs.jsonl
# 영상별 random.seed(20261114) 후 random.sample(pool, 100) -> $Y/celeb200.inputs.jsonl

# v0.8 store: v0.7.1 store 사본에 taxonomy v0.7.0 적재(16 docs)
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-v08 --embedding-provider upstage --reset

LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-v08 \
  --variant three_vector_rag --prompt-version category-rag-v0.8.0 \
  --input-path $Y/celeb200.inputs.jsonl --output-path $Y/celeb200.claude-haiku-5-5.v080.results.jsonl \
  --concurrency 4 --embedding-cache $Y/celeb200.query_vectors.json --resume
# 경계 세트: --input-path $G/political_boundary.jsonl --repeat 3

uv run python -m experiments.evaluate_youtube --results $Y/celeb200.claude-haiku-5-5.v080.results.jsonl \
  --gold $G/youtube_celeb200.labels.jsonl
uv run python -m experiments.evaluate_results --results-path experiments/outputs/benchmark/dev.claude-haiku-5-5.v080.results.jsonl \
  --gold-path experiments/outputs/benchmark/dev.gold.jsonl --merge-other
```
