# Upstage Embed 2 백그라운드 재색인

## 실행 기준

- 브랜치: `feat/upstage-embed2-migration`
- document model: `embedding-passage`
- query model: `embedding-query`
- endpoint: `https://api.upstage.ai/v1/embeddings`
- vector dimensions: 4096
- distance: cosine
- 대상 collection: `hate_speech_definitions`, `hate_speech_examples`
- 실행 container: `hatespeechraw-embed2-reindex`

실제 API key로 query/passage alias와 endpoint가 각각 HTTP 200, 4096차원 vector를 반환하는 것을 확인한 뒤 설정을 변경했다.

## 작업 순서

1. runtime worker를 정지한다.
2. Embed 2 기본 model과 endpoint를 코드, Compose, 환경 예시에 반영한다.
3. embedding/config 회귀 테스트와 live query/passage smoke를 통과시킨다.
4. corpus image를 새 설정으로 build한다.
5. detached one-shot container가 두 collection을 reset하고 전체 corpus를 재색인한다.
6. 완료 후 container exit code와 JSON summary, collection count, metadata model, query smoke를 검증한다.
7. 검증이 끝난 뒤에만 worker를 새 이미지로 재기동하고 branch를 `main`에 병합한다.

## 상태 확인

```bash
docker ps -a --filter name=hatespeechraw-embed2-reindex
docker logs --tail=100 hatespeechraw-embed2-reindex
```

`Exited (0)`과 bootstrap JSON summary가 확인되기 전에는 완료로 판단하지 않는다. 실패 시 container log를 기준으로 원인을 수정하고 collection을 다시 reset한다.

