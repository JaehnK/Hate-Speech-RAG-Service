# Gold Labels

실험용 gold label은 실제 YouTube 댓글 또는 script segment에서 별도로 작성한다.

초기 JSONL 필드:

```json
{"item_id":"sample-001","is_hate_speech":false,"categories":["unclassified"],"target_group":null,"hate_type":null,"rationale":"비혐오 일반 의견"}
```

MVP에서는 단일 검토자 small set으로 시작하고, 운영 전에는 2인 이상 라벨링과 불일치 조정을 추가한다.

`synthetic_smoke_5.jsonl`은 평가 코드와 prompt 회귀를 확인하기 위한 합성 smoke set이다. 실제 YouTube 댓글 품질을 대표하지 않으며, 운영 판단 지표로 사용하지 않는다.

실제 품질 검증은 익명화된 YouTube 댓글과 script segment를 2인 이상이 독립 라벨링하고 불일치를 조정한 별도 gold set으로 실행한다.

실제 평가에서는 experiment runner의 `--repeat 3`을 사용하고 evaluator의 `repeat_stability`를 함께 기록한다.

현재 정확도 평가셋·결과 현황과 실제 gold set 요구사항은 `docs/41_rag_accuracy_evaluation_status.md`를 기준으로 한다.

레거시 실제 결과셋을 활용한 반자동 gold 후보 구축 절차는 `docs/43_semi_automatic_gold_pipeline.md`와 `experiments.prepare_legacy_gold`를 기준으로 한다.

## YouTube 정답셋 (2026-11-12)

- `youtube_eval300.labels.jsonl`: 실제 YouTube 영상 3개에서 100건씩 뽑은 300건. `is_hate_speech`(서비스 기준: 집단 혐오 + 개인 공격), `target_scope`(group / individual / none), `categories`.
- `youtube_consistency.labels.jsonl`: 젠슨 황 영상에서 거의 같은 말을 묶은 111건. `group` 필드가 묶음 이름이다. 프롬프트 튜닝에 쓴 세트라 효과 판단에는 쓰지 않는다.
- 라벨은 Claude 한 명이 달았고 사람 검토 전이다. 댓글 본문은 넣지 않고 `experiments.fetch_youtube_comments`로 다시 받는다.
- 채점: `experiments.evaluate_youtube`. 결과와 한계는 `docs/52_v070_youtube_eval.md`.
- `youtube_eval300_ctx.labels.jsonl` (2026-11-13): 같은 300건을 영상 제목을 보고 다시 라벨링했다. 바뀐 7건은 `previous` 필드에 이전 라벨이 있다. 기준은 `docs/53_v071_video_title.md`.
- `youtube_heldout200.labels.jsonl` (2026-11-13): 새 영상 2개에서 100건씩. 모델을 돌리기 전에 라벨링한 효과 판단용 세트다.
