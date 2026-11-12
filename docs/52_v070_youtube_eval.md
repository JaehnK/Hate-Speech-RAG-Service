# 프롬프트 v0.7.0 · taxonomy v0.6.0 · YouTube 평가셋

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-11-12 KST |
| 계기 | 첫 운영 리포트(YTN 젠슨 황 영상, 1,261건)의 판정이 흔들리고, "혐오표현 31.2%"가 개인 모욕까지 세고 있었다 |
| 대상 | `category-rag-v0.7.0`, taxonomy v0.6.0, `claude-haiku-5-5` (effort low). 비교 기준은 `category-rag-v0.6.2`, taxonomy v0.5.1 |
| 평가 데이터 | YouTube 정답셋 300건(다른 영상 3개 × 100), 젠슨 황 영상 일관성 세트 111건 × 3회, 기존 dev 1,000건 |
| 결론 | 보고서가 집단 대상 혐오와 개인 대상 모욕·욕설을 나눠 센다. 같은 말의 판정이 덜 갈리고(일관성 세트 정확도 0.739 → 0.838), 집단 혐오 F1이 0.688 → 0.733이 됐다. dev 정확도는 그대로다(F1 0.824 → 0.823, McNemar 22:22). Sonnet 5.5의 v0.6.2 결과와 비슷한 수준이라 모델은 Haiku를 유지한다. |

## 1. 운영 리포트에서 드러난 문제

젠슨 황 불륜 보도 영상의 결과 1,261건을 전부 읽었다.

- **같은 말, 다른 판정.** "쓰레기네"는 혐오, "쓰레기네 엔비디아 계속 빠지겠네"는 정상이었다. "섹슨 황"은 혐오, "섹슨황 ㄷㄷㄷ"는 정상이었다. "남자네 황햄"은 `gender`+`profanity`, "남자네"는 정상이었다. 인물을 비꼬는 댓글 수백 개의 경계가 거의 무작위였다.
- **성별 단어만으로 `gender`.** "오메... 여자가 많았구나", "와이프는 이혼하면 돈방석.."이 성별 혐오로 잡혔다.
- **동음이의어.** "정부(情婦)가 있고 첩들이 있을 뿐"이 `state_authority`(정부·공직자 공격)로 잡혔다.
- **집계.** 혐오 393건 중 299건이 `profanity`였고, 대부분 특정 개인을 향한 욕이었다. 보고서는 이것을 모두 "혐오표현"으로 셌다.
- 진짜 집단 혐오("중국인은 스파이", "왕서방", "게이보단 불륜남이 좋아", "기혼녀는 직장 관두게해야해")는 대부분 잡혔고, Jev가 거른 145건에는 혐오가 없었다.

dev F1 0.82는 "공격적 표현인지"를 재는 점수였다(정답이 offensive를 혐오로 매핑, docs/49). 서비스 기준(`hate_threshold` 카드)도 처음부터 둘을 합쳐 정의했다. 반면 사용자는 "혐오표현 비율"을 집단 혐오로 읽는다.

## 2. 변경

| 영역 | 변경 |
| --- | --- |
| 출력 | `target_scope`: `group`(보호 속성·정치 진영·조직 전체를 겨냥하거나, 개인을 공격하면서 집단 속성을 멸칭·비하 근거로 씀), `individual`(집단 속성과 무관한 개인 공격, 대상 없는 욕설), `none`(비혐오). 검증기가 판정과 맞지 않으면 재시도시킨다 |
| `hate_threshold` | 공인 이름 말장난·스캔들 농담은 해당하지 않음을 명시하고 `target_scope` 정의를 넣었다. `is_hate_speech`의 범위(집단 혐오 + 개인 공격)는 그대로라 기존 정답셋과 비교할 수 있다 |
| `gender`·`age` | 성별·나이 단어가 나오지만 집단을 비하·일반화하지 않는 서술(특정 인물의 연애·나이 언급)을 제외 기준에 넣었다 |
| `profanity` | 이름 말장난, 스캔들 농담, 관상 품평, 행동 평가어(바람둥이 등)처럼 욕설·멸칭·인격 비하가 없는 놀림을 제외 기준에 넣었다 |
| 문맥 예외 | 뜻이 여러 개인 단어는 문맥상 뜻으로 판단한다 |
| 보고서 | "혐오표현 (집단 대상)"과 "모욕·욕설 (개인 대상)" 비율을 나눠 보여 주고, 댓글마다 "집단 혐오"/"모욕·욕설" 표시를 붙인다(웹, HTML, Excel). v0.7 이전 결과는 category로 추정한다(대상 category가 있으면 group). 이 추정은 이름으로 지목된 정치인 모욕도 group으로 세므로 집단 혐오를 과대 집계한다. 기존 리포트는 다시 만들기 전까지 예전 화면 그대로다 |

규칙에 든 예시(바람둥이, 정부/情婦)는 젠슨 황 영상에서 나왔다. 그래서 그 영상의 일관성 세트는 튜닝용으로만 보고, 효과는 다른 영상의 정답셋으로 판단한다.

## 3. 평가 데이터

| 세트 | 구성 | 라벨 |
| --- | --- | --- |
| `youtube_eval300` | 고령 운전자 사고(MBC), 외국인·다문화 발언(SBS), 해외 중국인 관광객(쇼츠) 영상에서 무작위 100건씩 | group 64, individual 51, none 185 |
| `youtube_consistency` | 젠슨 황 영상에서 거의 같은 말을 17개 묶음으로 모은 111건. 3회 반복 | group 19, individual 15, none 77 |

- 라벨은 Claude(Opus 5.5)가 혼자 달았고 사람 검토를 거치지 않았다. 2인 독립 라벨링과 조정 전까지는 예비 정답이다.
- 분류기처럼 댓글 문장만 보고 판정했다. 영상 속 인물을 가리키는 "뇌가 없다"류는 individual이다.
- 댓글 본문은 저장소에 넣지 않는다. `experiments.fetch_youtube_comments`로 다시 받고, 라벨만 `experiments/gold_labels/youtube_*.labels.jsonl`에 item_id(`yt:{video}:{comment}`)로 남긴다. 댓글이 지워지면 그 항목은 빠진다.

## 4. 결과 (Haiku 5.5)

### YouTube 정답셋 300건

| 지표 | v0.6.2 | v0.7.0 |
| --- | ---: | ---: |
| 공격적 표현 F1 (`is_hate_speech`) | 0.786 [0.727, 0.838] | 0.787 [0.726, 0.839] |
| 공격적 표현 precision / recall | 0.711 / 0.878 | 0.719 / 0.870 |
| **집단 혐오 F1** (`target_scope=group`) | 0.688 [0.597, 0.766] | **0.733** [0.651, 0.805] |
| 집단 혐오 precision / recall | 0.581 / 0.844 | 0.608 / 0.922 |
| 3분류(group/individual/none) 정확도 | 0.767 | 0.787 |

v0.6.2는 `target_scope`가 없어 category로 추정했다.

### 젠슨 황 일관성 세트 111건 × 3회

| 지표 | v0.6.2 | v0.7.0 |
| --- | ---: | ---: |
| 공격적 표현 정확도 | 0.739 | **0.838** |
| 공격적 표현 precision | 0.542 | 0.690 |
| 3분류 정확도 | 0.730 | 0.829 |
| 같은 묶음 안 판정 일치율 | 0.841 | 0.877 |
| 3회 반복 판정 일치율 (혐오 여부 / 3분류) | 0.928 / 0.919 | 0.910 / 0.892 |

말장난(존슨황·섹슨황·칩/첩), "바람둥이"류, 감탄사 묶음은 v0.7에서 모두 정상으로 일관되게 판정됐다. 성별 단어만 있는 묶음은 21회 중 11회가 여전히 `gender`였다.

### dev 1,000건 (기존 정답, 회귀 확인)

| 지표 | v0.6.2 | v0.7.0 |
| --- | ---: | ---: |
| binary F1 | 0.824 [0.800, 0.847] | 0.823 [0.797, 0.845] |
| category macro F1 | 0.581 | 0.575 |
| McNemar (v0.6.2만 맞음 : v0.7만 맞음) | | 22 : 22, p = 1.0 |

### 참고: Sonnet 5.5 + v0.6.2

정답셋 300건 중 232건(나머지는 일시적 결제 오류로 실패)에서 공격적 표현 F1 0.784, 집단 혐오 F1 0.737이었다. 일관성 세트에서는 반복 일치율이 0.964로 Haiku보다 높았지만, 정확도(0.721)와 묶음 안 일치율(0.741)은 낮았다. Haiku + v0.7이 Sonnet + v0.6.2와 같은 수준이므로, 흔들림은 모델보다 정의 문제였다. 비용을 고려해 Sonnet + v0.7은 돌리지 않았다.

## 5. 남은 문제

1. **정책 의견을 차별로 판정한다.** v0.7의 집단 혐오 오탐 대부분이 "70살 이상은 면허증 압수해라", "중국인 무비자 입국 금지시켜야지", "다문화면 복지혜택 다 주는 것도 문제"처럼 멸칭 없이 제도를 말하는 의견이다. taxonomy는 "연령·정체성을 이유로 권리 배제를 주장"을 혐오에 넣고 있어, 모델이 규칙을 따른 결과다. 정답 라벨은 이것을 정상으로 봤다. 어디에 선을 그을지는 서비스가 정할 일이다.
2. **영상 문맥이 없다.** "말미잘은 뇌가 없어요~", "발로 두구 차삐라", "밖에 나오지마라"는 영상 속 인물을 향한 말인데, 분류기는 문장만 봐서 정상으로 판정했다. 영상 제목을 입력에 넣는 방안을 검토할 만하다.
3. **성별 단어만 있는 서술**은 여전히 절반 정도 `gender`로 잡힌다.
4. 정답셋은 한 명(Claude)이 라벨링했다.

## 6. 재현

```bash
Y=experiments/outputs/youtube
uv run python -m experiments.fetch_youtube_comments 1lXorc7Mr0A --output-path $Y/jensen.inputs.jsonl
uv run python -m experiments.fetch_youtube_comments nHfZn9WSGZo cdKLuuhoKls kxcOmBGQ-HQ --output-path $Y/eval_pool.inputs.jsonl
# eval300: 영상별 random.seed(20261112) 후 random.sample(pool, 100). 라벨 item_id로 입력을 다시 뽑아도 된다.

# v0.7 store: 운영 사본에 taxonomy v0.6.0 적재
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-v07 --embedding-provider upstage --reset

LLM_MODEL=claude-haiku-5-5 uv run python -m experiments.run_rag_experiment --persist-directory .chroma-v07 \
  --variant three_vector_rag --prompt-version category-rag-v0.7.0 \
  --input-path $Y/eval300.inputs.jsonl --output-path $Y/eval300.claude-haiku-5-5.v070.results.jsonl \
  --concurrency 6 --embedding-cache $Y/eval300.query_vectors.json --resume
# 일관성 세트는 --input-path $Y/consistency.inputs.jsonl --repeat 3

uv run python -m experiments.evaluate_youtube --results $Y/eval300.claude-haiku-5-5.v070.results.jsonl \
  --gold experiments/gold_labels/youtube_eval300.labels.jsonl
```
