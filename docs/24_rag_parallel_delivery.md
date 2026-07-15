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

## Phase 3. Job 내부 bounded parallelism

- 브랜치: `feat/rag-intra-job-parallelism`
- worker process 수명의 classifier pool과 RAG step 수명의 bounded `ThreadPoolExecutor`를 구현했다.
- executor는 최대 동시성만큼만 future를 유지하고 완료될 때마다 다음 item 하나를 제출한다.
- provider thread는 immutable DTO만 처리하고 결과 DB transaction은 coordinator가 순서대로 실행한다.
- `sequential`과 `parallel` 모드가 같은 checkpoint/persistence 경로를 사용한다.
- SIGTERM/SIGINT stop event 뒤 신규 item 제출을 중단하고 현재 active item을 drain한 뒤 step/job을 즉시 `pending`으로 release한다.
- RAG 설정 surface를 Settings, `.env.example`과 Compose에 추가하고 실행 모드, item concurrency, heartbeat와 request timeout을 runtime에 연결했다. provider gate/retry와 grace 상한 적용은 Phase 4 범위다.
- analysis run의 retriever config에 실제 execution mode와 item concurrency를 기록한다.

검증 결과:

- bounded executor/config/shutdown/pipeline 집중 테스트 21개 통과
- concurrency 4에서 40개 fake I/O가 순차 대비 3배 이상 개선
- Ruff, compileall과 dev/test/prod Compose config 통과
- backend 전체 테스트 87개 통과, PostgreSQL opt-in 테스트 1개 기본 skip

## Phase 4. Provider backpressure와 관측성

- 브랜치: `feat/rag-provider-backpressure`
- worker runtime에 Upstage/Anthropic 전용 `BoundedSemaphore`를 두어 item 동시성과 provider 동시성을 분리했다.
- timeout/transport, 429와 일시적 5xx만 최대 시도 내에서 재시도하고 non-retry 4xx는 즉시 실패한다.
- 429 `Retry-After`를 우선하고, 없으면 0.5초 기반 exponential backoff와 jitter를 사용한다.
- backoff 동안 provider semaphore를 반납해 다른 item 호출을 막지 않는다.
- stop event를 provider/validation retry 전에 확인해 종료 요청 뒤 새 외부 호출을 시작하지 않는다.
- runtime progress를 10건 또는 5초 단위와 step 종료 시 `rag_progress` operation log에 기록한다.
- progress metadata에는 완료/성공/실패/in-flight, concurrency, provider retry, token usage와 elapsed time이 포함된다.
- signal drain에 grace deadline과 provider request timeout을 연결했다.

검증 결과:

- retry/provider gate/progress/shutdown 집중 테스트 26개 통과
- Upstage 429 `Retry-After`, 401 non-retry와 동시 HTTP gate 검증
- Anthropic rate limit `Retry-After` 검증
- Ruff, compileall과 dev/test/prod Compose config 통과
- backend 전체 테스트 94개 통과, PostgreSQL opt-in 테스트 1개 기본 skip

## Phase 5. 배포 전 통합 검증

- 브랜치: `chore/rag-parallel-predeploy-validation`
- 로컬 비밀 설정 파일에 `parallel`, item/Upstage/Anthropic 동시성 2를 적용하고 worker image를 새로 빌드해 재기동했다.
- 실행 중인 worker container에서 동일 설정값과 정상 기동 상태를 확인했다.
- production provider 경로에 합성 comment 2건을 동시에 전달해 Upstage 검색 embedding과 Anthropic 분류를 실제 호출했다.
- 두 item 모두 `claude-haiku-4-5-20251001`로 성공했고 input 3,662/output 445 token, provider retry 0회, 총 2,932ms를 기록했다.
- 공유 개발 PostgreSQL에서 worker와 opt-in 통합 테스트가 경합하지 않도록 테스트 job을 즉시 `running` 상태로 격리했다.
- 테스트 정리는 non-cascade `operation_logs`를 먼저 삭제하도록 보강했으며 수정 브랜치 `test/rag-postgres-worker-isolation`은 병합 후 보존했다.

최종 검증 결과:

- Ruff와 compileall 통과
- dev/test/prod Compose config 통과
- backend 전체 테스트 94개 통과, PostgreSQL opt-in 테스트 1개 기본 skip
- worker 실행 중 실제 PostgreSQL duplicate insert race 테스트 1개 통과
- 실제 provider 병렬 smoke 2/2 성공
- worker image 재빌드와 container 기동 확인

배포 경계:

- 애플리케이션 코드, container image build, runtime 설정과 실제 provider smoke까지 완료했다.
- 외부 배포 환경 반영과 트래픽 전환은 수행하지 않았다.
