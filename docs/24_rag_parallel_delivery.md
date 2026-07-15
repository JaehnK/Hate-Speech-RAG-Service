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

## Phase 2. Item checkpoint와 attempt fencing

- 브랜치: `feat/rag-item-checkpoints`
- 기존 comment/script 결과 unique constraint를 이용한 SQLite/PostgreSQL `ON CONFLICT DO NOTHING` 저장을 추가했다.
- 결과가 실제 insert된 경우에만 같은 transaction에서 성공/실패 progress counter를 증가시킨다.
- step 시작·종료 reconcile이 실제 결과 row에서 legacy counter를 복구한다.
- 기존 결과가 있는 source는 classifier 호출 전에 제외해 worker 재시작 시 누락 item만 재개한다.
- result 저장과 step 완료에 `job_steps.attempt_count` fencing을 적용했다.
- 이전 attempt가 늦게 끝나면 결과, step 완료와 job finalize를 덮어쓰지 않는다.
- 기존 별도 `DatabaseJobProgressReporter`는 result store에 통합했다.

검증 결과:

- checkpoint/progress/pipeline 집중 테스트 11개 통과
- PostgreSQL 동시 duplicate insert race 통과
- Ruff와 compileall 통과
- backend 전체 테스트 82개 통과, PostgreSQL opt-in 테스트 1개 기본 skip
