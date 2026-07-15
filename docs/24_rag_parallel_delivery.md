# RAG 병렬 처리 구현 기록

## Phase 1. Dual retrieval 재사용

- 브랜치: `perf/rag-dual-retrieval-reuse`
- 동일 retrieval query를 Upstage에서 한 번만 embedding하고 같은 vector를 definition/example Chroma collection에 전달했다.
- `DualVectorRetriever`가 Chroma client와 두 collection handle을 classifier 생명주기 동안 재사용한다.
- `UpstageEmbeddingClient`가 장기 `httpx.Client`를 재사용하고 명시적으로 닫도록 변경했다.
- `RagClassifier.close()`가 retriever, Anthropic client와 observability resource를 정리하고 worker 종료 경로에 연결됐다.
- 기존 collection별 degraded mode, retrieval 결과 parsing과 prompt/output 계약을 유지했다.

검증 기준:

- dual collection 조회당 query embedding 1회
- definition/example 한쪽 장애 시 나머지 결과 유지
- Ruff, compileall, retrieval/RAG/embedding 회귀와 backend 전체 테스트 통과

검증 결과:

- retrieval/RAG/embedding 집중 테스트 14개 통과
- Ruff와 compileall 통과
- backend 전체 테스트 79개 통과
