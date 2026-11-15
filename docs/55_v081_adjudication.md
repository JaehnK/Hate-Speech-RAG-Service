# 2인 라벨 조정과 프롬프트 v0.8.1 · taxonomy v0.7.1

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-15 KST |
| 계기 | 지금까지의 YouTube 정답셋은 Claude 혼자 라벨링했고, 모델 점수는 "Claude 기준을 얼마나 따라 하느냐"였다 |
| 데이터 | heldout200·eval300·celeb200에서 200건 층화 추출(Claude 기준 group 70, individual 60, none 70). 사람은 Claude 라벨을 보지 않고 라벨링 |
| 결론 | 사람과 Claude의 판정 일치도 κ = 0.385. 불일치는 몇 가지 원칙 차이에 몰려 있었다. 원칙을 합의해 조정한 정답에서 v0.8.1은 κ 0.53 → 0.70(정확도 0.685 → 0.805, McNemar 7:31, p = 0.0001). 다만 규칙을 같은 200건에서 만들었으므로 독립 세트 검증 전까지 낙관적인 수치다 |

## 1. 사람 vs Claude

| | 판정 정확도 | 판정 κ | 혐오 여부 κ |
| --- | ---: | ---: | ---: |
| 사람 vs Claude | 0.585 | 0.385 | 0.305 |

사람은 혐오 아님을 21건, Claude는 70건 골랐다. 범주 κ는 성별·연령·정체성·욕설 0.62~0.70, 정치 행위자 0.25, 정치 진영 0.36.

## 2. 합의한 원칙

| | 원칙 | 결정 |
| --- | --- | --- |
| A1 | 모욕 없는 불만·비판·퇴진 요구("그냥 내려와라", "실망이다") | 혐오 아님 |
| A2 | 욕설 없는 조롱·비꼼("제정신은 아닌듯", "어유 쪽팔려") | 개인 공격 |
| A3 | 멸칭 없는 근거 없는 부정적 일반화("테러리스트 이미지", "돌진 사고는 거의 다 60~70대") | 집단 혐오 |
| A4 | 이름 있는 사람 + 진영 멸칭("좌파 새끼") | 집단 + 정치 진영 (기존 규칙) |
| A5 | 한 사람을 나이·출신 멸칭으로 욕함("노친네") | 개인 + 연령/정체성 범주 |
| A6 | 여러 사람을 복수로 욕함("쓰레기들", "니들") | 집단 |
| A7 | 제목이 다루는 집단의 구성원 여럿(관광객)을 향한 욕 | 집단 + 정체성 |
| 기타 | 성씨("믿거조")·직업(배우, 평론가) 집단에 대한 부정적 일반화 | 집단 + 욕설 |

개별 20건은 항목별로 합의했다. 둘 다 같은 판정이었지만 위 원칙과 어긋나는 6건(A5·A6)은 v0.8.1 결과를 본 뒤 원칙에 맞춰 고쳤다. 영상 속 연예인을 정치와 무관한 말로 욕한 경우(P1, 10건)는 욕설만으로 둔다(2026-11-15 확정). 정치 논란 영상이어도 댓글에 정치 발언·진영 언급이 없으면 `political_actor`가 아니다. 이 문구는 v0.8.1 실행 뒤 `political_actor` 카드에 넣었으므로 위 결과에는 반영되지 않았다.

## 3. 변경

- taxonomy v0.7.1: `hate_threshold` 카드에 A1~A7과 성씨·직업 집단 규칙을 넣었다. `age`·`identity`·`profanity` 카드의 포함 기준에 "멸칭이 없어도 근거 없는 부정적 일반화"를 더했다.
- prompt v0.8.1: v0.8.0에서 영상 제목 규칙만 바꿨다. "제목이 집단을 다룬다는 이유만으로 group이 되지 않는다"를 빼고, 제목이 다루는 집단의 구성원 여럿을 향한 모욕은 group으로 한다.

## 4. 결과 (조정 정답 200건, Haiku 5.5)

| | 판정 정확도 | 판정 κ | 혐오 여부 κ | 집단 F1 | 개인 F1 | 혐오 아님 F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 사람 (조정 전) | 0.780 | 0.651 | 0.612 | 0.859 | 0.743 | 0.667 |
| Claude (조정 전) | 0.735 | 0.603 | 0.613 | 0.762 | 0.719 | 0.714 |
| v0.7.0 (150건) | 0.620 | 0.427 | 0.458 | 0.646 | 0.582 | 0.617 |
| v0.7.1 | 0.675 | 0.515 | 0.465 | 0.739 | 0.649 | 0.612 |
| v0.8.0 | 0.685 | 0.530 | 0.520 | 0.733 | 0.656 | 0.650 |
| **v0.8.1** | **0.805** | **0.701** | **0.661** | **0.852** | **0.787** | **0.745** |

원칙별로 v0.8.1은 A2(조롱) 4 → 10/10, A5 2 → 6/6, A6 1 → 3/3을 맞혔다. 정치 행위자 F1은 0.49 → 0.37로 떨어졌다. 진영 멸칭으로 욕한 이름 있는 인물에 정치 진영만 붙이고 정치 행위자를 빼는 경우가 많다.

## 5. 한계

1. 규칙을 이 200건에서 만들고 같은 200건으로 쟀다. 독립 세트(새 영상) 검증이 필요하다.
2. dev 1,000건 회귀 확인을 하지 않았다. A2·A3로 혐오 판정이 넓어져 precision이 떨어질 수 있다.
3. 조정은 사람 1명과 Claude가 했다.

## 6. 재현

```bash
A=experiments/outputs/annotation
uv run python -m experiments.build_annotation_sample            # 표본과 라벨링 페이지
cp -a .chroma-v08 .chroma-v081
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-v081 --embedding-provider upstage --reset
LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-v081 \
  --variant three_vector_rag --prompt-version category-rag-v0.8.1 \
  --input-path $A/sample200.inputs.jsonl --output-path $A/sample200.claude-haiku-5-5.v081.results.jsonl --concurrency 6
uv run python -m experiments.score_annotation --sample $A/sample_20261115.jsonl \
  --human experiments/gold_labels/youtube_adjudicated200.labels.jsonl \
  --results "v081=$A/sample200.claude-haiku-5-5.v081.results.jsonl"
```
