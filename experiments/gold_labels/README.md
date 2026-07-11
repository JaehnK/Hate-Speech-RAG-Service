# Gold Labels

실험용 gold label은 실제 YouTube 댓글 또는 script segment에서 별도로 작성한다.

초기 JSONL 필드:

```json
{"item_id":"sample-001","is_hate_speech":false,"categories":["unclassified"],"target_group":null,"hate_type":null,"rationale":"비혐오 일반 의견"}
```

MVP에서는 단일 검토자 small set으로 시작하고, 운영 전에는 2인 이상 라벨링과 불일치 조정을 추가한다.
