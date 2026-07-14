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
