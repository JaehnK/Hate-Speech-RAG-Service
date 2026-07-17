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
- 시작 시각: 2026-07-16 21:44 KST
- 설정 commit: `1bd9c2f`
- 완료 시각: 2026-07-16 23시대 KST
- 현재 상태: `Exited (0)`, collection 및 실제 RAG 호출 검증 완료

실제 API key로 query/passage alias와 endpoint가 각각 HTTP 200, 4096차원 vector를 반환하는 것을 확인한 뒤 설정을 변경했다.

## 완료 증적

재색인 container의 최종 summary는 다음과 같다.

```json
{
  "embedding_provider": "upstage",
  "embedding_model": "embedding",
  "internal_definition_count": 23,
  "external_definitions_loaded": 8,
  "definition_collection_count": 31,
  "examples_loaded": 172157,
  "example_collection_count": 172157,
  "limited": false
}
```

collection metadata에는 document model `embedding-passage`, query model `embedding-query`, dimensions 4096, definition corpus version `definition-corpus-2026-07-16-v0.3`가 기록됐다.

검색 smoke 결과:

- `정당 지지자 전체를 제거해야 한다` → `category:non_state_community:0`가 최상위
- `국적과 민족을 이유로 집단을 추방하자는 표현` → `category:identity:0`가 최상위
- `대상 없이 단독으로 사용된 심한 욕설` → `category:no_target:0`가 최상위

실제 분류 통합 smoke는 definition 8건, similarity gate를 통과한 example 4건을 사용해 `rag_context_status=complete`를 기록했다. Anthropic 응답은 첫 시도에 output schema 검증을 통과했고 한국어 reasoning을 반환했다.

## 최종 회귀 검증

- Python lint: 통과
- backend: 99 passed, 1 skipped
- frontend: 11 passed
- frontend production build: 통과
- worker: 새 image로 재기동, `EMBEDDING_MODEL=embedding`과 새 endpoint 확인
- service smoke: backend `/health`와 frontend `/rag-methodology` 응답 확인

## 작업 순서

1. runtime worker를 정지한다.
2. Embed 2 기본 model과 endpoint를 코드, Compose, 환경 예시에 반영한다.
3. embedding/config 회귀 테스트와 live query/passage smoke를 통과시킨다.
4. corpus image를 새 설정으로 build한다.
5. detached one-shot container가 두 collection을 reset하고 전체 corpus를 재색인한다.
6. 완료 후 container exit code와 JSON summary, collection count, metadata model, query smoke를 검증한다.
7. 실제 LLM을 포함한 RAG 분류 smoke와 전체 회귀 테스트를 통과시킨다.
8. 검증이 끝난 뒤에만 worker를 새 이미지로 재기동하고 branch를 `main`에 병합한다.

## 상태 확인

```bash
docker ps -a --filter name=hatespeechraw-embed2-reindex
docker logs --tail=100 hatespeechraw-embed2-reindex
```

완료 판정은 `Exited (0)`, bootstrap JSON summary, collection metadata/count, 검색 smoke, 실제 RAG 분류 smoke를 모두 요구한다. 실패 시 container log를 기준으로 원인을 수정하고 collection을 다시 reset한다.
