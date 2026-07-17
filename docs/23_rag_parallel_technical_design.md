# Job 내부 RAG 병렬 처리 기술 구현안

## 1. 결정 사항

이 구현은 기존 PostgreSQL polling job의 내부 최적화다. API, job 상태 모델과 Docker service 경계는 바꾸지 않는다.

- 한 worker process가 job 하나를 처음부터 끝까지 소유한다.
- pipeline step은 현재 순서를 유지한다.
- `analyze_comments`, `analyze_script`의 item 분류만 제한된 동시성으로 실행한다.
- RAG 전용 queue, consumer, Docker service와 item lease table은 만들지 않는다.
- 기존 분석 결과 unique constraint를 완료 checkpoint로 사용한다.
- 기존 `job_steps.attempt_count`를 stale 실행 fencing token으로 사용한다.
- provider thread는 DB에 접근하지 않는다. 결과 저장과 진행률 갱신은 coordinator만 수행한다.
- 현재 Chroma 1.5.9의 `query_embeddings`를 사용해 동일 query embedding을 두 collection에 재사용한다.
- 새 Alembic migration은 필요하지 않다.

## 2. 목표 실행 흐름

```text
FastAPI
  POST /api/analysis-jobs
  -> analysis_jobs/job_steps 생성
  -> 202 + job_id

worker
  -> pending job claim
  -> validate/collect/create_run 순차 실행
  -> analyze_comments 진입
     -> step attempt=1 commit
     -> 기존 comment result와 source를 비교해 누락 item iterator 생성
     -> 최대 N개 future만 제출
        -> classifier slot 대여
        -> query text 생성
        -> Upstage query embedding 1회
        -> 같은 vector로 definition/example Chroma 조회
        -> prompt 생성
        -> Anthropic 분류
        -> classifier slot 반환
     -> 완료 DTO를 coordinator가 수신
     -> attempt fencing 확인
     -> 결과 insert + progress 증가를 한 transaction으로 commit
     -> future 하나 완료 시 다음 item 하나 제출
     -> 모든 결과 저장 후 progress reconcile
     -> attempt가 여전히 같을 때 step 완료
  -> analyze_script도 같은 runtime으로 실행
  -> network/report/finalize 순차 실행
```

`RAG_EXECUTION_MODE=sequential`은 동일한 retrieval, checkpoint와 persistence 경로를 사용하되 executor를 거치지 않고 item을 하나씩 실행한다. 따라서 rollback은 코드 경로를 바꾸지 않고 동시성만 제거한다.

## 3. 파일별 변경안

| 파일 | 변경 |
| --- | --- |
| `app/core/config.py` | RAG 실행 모드, item/provider 동시성, 재시도, heartbeat와 종료 grace 설정 추가 |
| `app/analysis/embeddings.py` | `UpstageEmbeddingClient`의 장기 `httpx.Client` 재사용과 `close()` 추가 |
| `app/analysis/vector_store.py` | 외부에서 주입한 Chroma client/collection과 `query_embeddings` 조회 지원 |
| `app/analysis/retriever.py` | 신규 `DualVectorRetriever`; query embedding 1회와 두 collection degraded 조회 담당 |
| `app/analysis/rag_classifier.py` | retriever 주입, provider retry와 validation retry 분리, `close()` 계약 추가 |
| `app/analysis/models.py` | immutable `AnalysisItem`, `AnalysisOutcome`, `RetrievalBundle` DTO 추가 |
| `app/analysis/result_store.py` | 신규 결과 checkpoint 조회, 멱등 insert, progress reconcile와 heartbeat 담당 |
| `app/analysis/executor.py` | 신규 bounded coordinator, classifier pool, shutdown 제어와 실행 통계 담당 |
| `app/analysis/services.py` | 댓글/자막 source query를 DTO iterator로 만들고 공통 coordinator 호출 |
| `app/jobs/progress.py` | 무조건 `+1` API를 제거하고 result insert와 결합된 progress/reconcile API로 교체 |
| `app/jobs/orchestrator.py` | attempt fencing, stale completion 폐기, graceful release 처리 |
| `app/jobs/production_pipeline.py` | ORM `AnalysisRun` 대신 실행 ID와 step context를 analyzer에 전달 |
| `app/jobs/worker.py` | stop event를 job 실행과 RAG coordinator에 전달 |
| `app/worker_main.py` | process 수명의 `RagRuntime`, signal handler와 resource close 구성 |
| `.env.example`, `compose.yaml` | RAG 설정 노출 |
| `docs/10_docker_environment.md` | 설정과 운영 조정 순서 추가 |

`app/db/session.py`의 engine/session factory는 변경하지 않는다. executor thread가 session을 열지 않고 coordinator만 짧은 transaction을 순서대로 수행하므로 RAG 동시성만큼 DB pool을 키울 이유가 없다. web과 worker는 서로 다른 process에서 각자 engine을 가진다.

## 4. Core interface

### 4.1 DTO

ORM object가 thread 경계를 넘지 않도록 다음 DTO만 executor에 전달한다.

```python
@dataclass(frozen=True)
class AnalysisItem:
    source_id: UUID
    source_type: SourceType
    text: str


@dataclass(frozen=True)
class AnalysisOutcome:
    source_id: UUID
    status: Literal["succeeded", "failed"]
    result_values: dict[str, Any]
    embedding_attempts: int
    llm_attempts: int
    usage: dict[str, int]
    elapsed_ms: int


@dataclass(frozen=True)
class StepAttemptContext:
    job_id: UUID
    step_id: UUID
    step_key: str
    run_id: UUID
    expected_attempt: int
```

`StepAttemptContext`는 coordinator에 한 번만 보관하고 모든 item DTO에 반복하지 않는다. 전체 `StepHandler` signature는 바꾸지 않는다. production handler가 orchestrator가 commit한 현재 `JobStep`을 `job_id + step_key`로 읽어 context를 만들고 analyzer에 전달한다.

### 4.2 DualVectorRetriever

```python
class DualVectorRetriever:
    def __init__(
        self,
        embedding_function,
        definition_collection,
        example_collection,
    ) -> None: ...

    def retrieve(
        self,
        query_text: str,
        *,
        definition_n: int,
        example_n: int,
    ) -> RetrievalBundle: ...

    def close(self) -> None: ...
```

구현 순서:

1. `embedding_function.embed_query([query_text])`를 정확히 한 번 호출한다.
2. 반환 vector를 `definition_collection.query(query_embeddings=[vector], ...)`에 전달한다.
3. 같은 vector를 `example_collection.query(query_embeddings=[vector], ...)`에 전달한다.
4. 각 collection query는 독립적으로 예외를 잡는다.
5. 한쪽만 성공하면 기존 `definition_only` 또는 `example_only` 상태를 반환한다.
6. embedding 실패 또는 두 collection 실패는 `ClassificationError`로 정규화한다.

collection별 결과 parsing은 현재 `query_definition_documents`, `query_example_documents`에서 private parser로 분리해 재사용한다. ingest 함수의 `query_texts` 기반 API는 corpus 도구 호환을 위해 유지한다.

### 4.3 Client 수명

`UpstageEmbeddingClient`는 생성자에서 `httpx.Client(timeout=...)`를 한 번 만들고 모든 `embed` 호출에서 재사용한다. 테스트가 fake client를 주입할 수 있도록 `http_client` 인자를 둔다. `close()`는 소유한 client만 닫는다.

`RagRuntime`은 worker process 수명 동안 다음 resource를 소유한다.

```python
class RagRuntime:
    classifier_pool: ClassifierPool
    embedding_gate: BoundedSemaphore
    llm_gate: BoundedSemaphore

    def close(self) -> None: ...
```

classifier는 item마다 생성하지 않는다. parallel mode는 `RAG_ITEM_CONCURRENCY` 수만큼, sequential mode는 하나의 classifier slot을 미리 만들고 `queue.Queue`로 대여·반납한다. 각 slot은 자체 Anthropic client, Upstage HTTP client, Chroma client와 collection handle을 가지므로 thread safety를 가정하지 않는다. slot은 여러 item에서 재사용되고 worker 종료 시 정확히 한 번 닫힌다.

executor는 RAG step 동안만 생성한다. classifier pool과 provider semaphore는 댓글·자막 step 및 다음 job에서도 재사용한다.

### 4.4 Classifier factory

`worker_main.py`의 단일 classifier 생성 코드를 factory로 바꾼다.

```python
def build_classifier() -> RagClassifier:
    embedding = create_embedding_function(..., gate=embedding_gate)
    retriever = build_dual_retriever(
        persist_directory=settings.chroma_persist_directory,
        embedding_function=embedding,
    )
    llm = AnthropicLlmClient(..., gate=llm_gate)
    return RagClassifier(retriever=retriever, llm_client=llm, ...)
```

Langfuse client도 classifier slot별로 만들고 `close()`에서 `flush()`한다. `capture_io=false` 기본값과 secret 비출력 정책은 유지한다.

## 5. Result checkpoint와 transaction

### 5.1 누락 item query

댓글은 다음 조건의 projection만 읽는다.

```sql
SELECT comment.id, comment.text_original, comment.text_display, comment.is_reply
FROM comment_snapshots AS comment
LEFT JOIN comment_analysis_results AS result
  ON result.comment_snapshot_id = comment.id
 AND result.analysis_run_id = :run_id
WHERE comment.job_id = :job_id
  AND result.id IS NULL
ORDER BY comment.collected_at, comment.id
```

자막도 `transcript_segments`와 `script_analysis_results`를 같은 방식으로 비교하고 `segment_index` 순서로 읽는다. SQLAlchemy에서는 ORM entity가 아니라 column tuple/mapping을 조회해 즉시 `AnalysisItem`으로 변환한다.

전체 source를 future 목록으로 만들지 않는다. iterator에서 최대 `RAG_ITEM_CONCURRENCY`개만 꺼낸다.

### 5.2 dialect별 idempotent insert

지원 DB는 SQLite와 PostgreSQL 두 개이므로 `session.bind.dialect.name`에 따라 SQLAlchemy dialect insert를 선택한다.

```python
postgresql.insert(table).on_conflict_do_nothing(
    index_elements=["analysis_run_id", source_column],
).returning(table.c.id, table.c.status)

sqlite.insert(table).on_conflict_do_nothing(
    index_elements=["analysis_run_id", source_column],
).returning(table.c.id, table.c.status)
```

generic pre-check 후 ORM insert 방식은 사용하지 않는다. stale worker와 새 worker 사이의 race를 DB unique constraint로 닫아야 하기 때문이다.

### 5.3 결과 저장 transaction

결과 하나당 다음을 같은 transaction에서 수행한다.

1. `job_steps.id`, `status=running`, `attempt_count=:expected_attempt` 조건으로 heartbeat를 갱신하고 row를 반환받는다.
2. 반환 row가 없으면 `StaleStepExecution`으로 결과를 폐기한다.
3. comment 또는 script result를 `ON CONFLICT DO NOTHING RETURNING`으로 insert한다.
4. insert가 실제 발생한 경우에만 `items_completed`와 성공/실패 counter를 `+1` 한다.
5. conflict이면 counter를 변경하지 않는다.
6. commit 후 jobs API가 새 진행률과 결과를 함께 보게 한다.

step row의 조건부 update가 짧은 row lock 역할을 하므로 stale recovery가 같은 순간에 step 소유권을 바꾸지 못한다. 외부 API 호출 중에는 DB transaction이나 connection을 잡지 않는다.

### 5.4 Progress reconcile

RAG step 시작과 종료에만 source/result count를 다시 계산한다.

```text
items_total     = source count
items_succeeded = result where status=succeeded
items_failed    = result where status=failed
items_completed = succeeded + failed
```

reconcile update도 `step_id`, `status=running`, `expected_attempt` 조건을 사용한다. 매 item마다 전체 `COUNT`를 실행하지 않는다. 기존 `DatabaseJobProgressReporter.advance()`는 제거하고 result store가 progress atomicity를 소유한다.

### 5.5 기존 job 호환

- 결과 row가 없는 legacy running job은 source 전체를 다시 처리한다.
- 결과 row가 일부 존재하면 해당 source만 건너뛴다.
- 기존 counter가 실제 결과와 다르면 step 시작 reconcile이 교정한다.
- 완료된 과거 job은 다시 열지 않으므로 변경되지 않는다.
- schema를 추가하지 않으므로 migration과 데이터 backfill은 없다.

## 6. Bounded coordinator

### 6.1 실행 algorithm

```python
def run(items, context, mode):
    result_store.reconcile(context)
    if mode == "sequential":
        for item in items:
            stop_if_requested(context)
            outcome = classifier_pool.classify(item)
            result_store.persist(context, outcome)
        return result_store.reconcile(context)

    with ThreadPoolExecutor(max_workers=item_concurrency) as executor:
        in_flight = submit_up_to_limit(executor, items)
        while in_flight:
            done = wait(
                in_flight,
                timeout=heartbeat_interval,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                result_store.heartbeat(context)
                continue
            for future in done:
                outcome = normalize_future(future)
                result_store.persist(context, outcome)
                submit_one_if_available(executor, items, in_flight)
            emit_throttled_progress(context, in_flight)
    return result_store.reconcile(context)
```

`executor.map`과 전체 item `submit`은 사용하지 않는다. `in_flight` 크기는 항상 item concurrency 이하이며 source 수가 커져도 future memory가 선형 증가하지 않는다.

### 6.2 예외 정규화

future 예외를 coordinator까지 그대로 전파하지 않는다.

- 정상 분류: `AnalysisOutcome(status="succeeded")`
- 최종 provider/validation 실패: `AnalysisOutcome(status="failed", error_code=...)`
- `KeyboardInterrupt`, `SystemExit`, stop event: item 결과로 저장하지 않고 shutdown 경로로 전파
- 코드 결함에 해당하는 예상 밖 예외: 신규 submit을 중단하고 outstanding future를 정리한 뒤 traceback과 함께 step을 `UNEXPECTED_ERROR`로 실패시킨다. 같은 결함을 모든 item에 반복 적용하지 않는다.

현재와 같이 item 일부 실패는 결과 row의 `failed`로 남기고 optional RAG step 실행 자체는 완료한다. 전체 실패를 step failure로 바꾸는 정책은 이번 성능 변경에 포함하지 않는다.

### 6.3 Comment와 script 경계

댓글과 자막은 같은 `RagRuntime`을 쓰지만 executor는 동시에 열지 않는다.

- 댓글 RAG future가 모두 저장된 뒤 `analyze_comments`를 완료한다.
- 그 다음 자막 RAG executor를 연다.
- 별도 executor 두 개가 provider semaphore를 경쟁하는 구조는 만들지 않는다.
- 자막 보고 순서는 완료 순서가 아니라 `segment_index`를 유지한다.

## 7. Step fencing과 worker 종료

### 7.1 Stale completion fencing

`JobOrchestrator._run_step`은 step 시작 직후 증가시킨 `attempt_count`를 지역 변수로 보관한다. handler 종료 후 ORM object를 직접 수정하지 않고 다음 조건부 update로 step을 완료한다.

```sql
UPDATE job_steps
SET status = :status, metrics = :metrics, finished_at = :now, heartbeat_at = :now
WHERE id = :step_id
  AND status = 'running'
  AND attempt_count = :expected_attempt
```

rowcount가 0이면 이전 stale 실행의 결과다. `stale_step_result_discarded`를 기록하고 해당 `run_job`은 다음 step과 finalize를 실행하지 않고 종료한다.

### 7.2 SIGTERM

`worker_main.py`에서 SIGTERM/SIGINT handler가 `threading.Event`만 설정한다. signal handler 안에서는 DB나 logging I/O를 수행하지 않는다.

RAG coordinator는 다음 동작을 한다.

1. stop event 확인 후 신규 item submit 중단
2. 시작하지 않은 future cancel
3. `RAG_SHUTDOWN_GRACE_SECONDS` 동안 실행 중 future drain
4. 완료 future 결과는 정상 저장
5. 남은 item은 미완료로 둔다.
6. 현재 attempt 조건으로 step과 job을 즉시 `pending`에 되돌린다.
7. worker process resource를 close하고 종료한다.

Python thread는 강제로 종료할 수 없으므로 provider request timeout은 shutdown grace보다 길게 두지 않는다. hard kill은 기존 heartbeat stale recovery가 처리하고, 이미 commit된 결과는 checkpoint query가 건너뛴다.

classifier와 retry wrapper는 provider 응답 직후와 validation/infrastructure retry 직전에 stop event를 확인한다. 종료 요청 뒤 두 번째 validation 호출이나 backoff 재시도를 새로 시작하지 않는다.

## 8. Provider gate와 retry

provider semaphore는 classifier slot보다 바깥의 `RagRuntime`에 하나씩 둔다.

- embedding gate: Upstage HTTP 요청 직전 acquire, 응답 parsing 뒤 release
- LLM gate: Anthropic 요청 직전 acquire, 응답 parsing 뒤 release
- Chroma local query: provider gate 대상이 아니지만 concurrency 4 integration test로 read 안정성을 검증

재시도 대상:

| Provider | 재시도 | 즉시 실패 |
| --- | --- | --- |
| Upstage/httpx | timeout, transport error, 429, 500, 502, 503, 504 | 400, 401, 403, 그 외 4xx |
| Anthropic | connection/timeout, rate limit, internal server error | authentication, permission, bad request |
| Chroma | 일시적 read 오류 1회 | collection 없음, dimension mismatch |

429는 `Retry-After`를 우선하고, 없으면 `min(0.5 × 2^(attempt-1) + jitter, 8)`초를 사용한다. infrastructure 최대 시도는 `RAG_ITEM_MAX_ATTEMPTS`다. LLM JSON/schema validation의 기존 1회 재생성은 이 counter와 분리한다.

semaphore는 실제 HTTP 시도 동안만 점유한다. backoff sleep 중에는 반납해 다른 item을 막지 않는다.

## 9. Runtime 설정

`Settings`에 다음 필드를 추가하고 양의 정수 검증을 적용한다.

| 환경 변수 | 기본값 | 검증/용도 |
| --- | ---: | --- |
| `RAG_EXECUTION_MODE` | `sequential` | `sequential`, `parallel` |
| `RAG_ITEM_CONCURRENCY` | `4` | 1~16, executor/in-flight/classifier slot 수 |
| `RAG_EMBEDDING_CONCURRENCY` | `4` | 1~item concurrency |
| `RAG_LLM_CONCURRENCY` | `2` | 1~item concurrency |
| `RAG_ITEM_MAX_ATTEMPTS` | `3` | 1~5, infrastructure 시도 수 |
| `RAG_HEARTBEAT_INTERVAL_SECONDS` | `30` | 5 이상, 완료 item이 없을 때 heartbeat 간격 |
| `RAG_SHUTDOWN_GRACE_SECONDS` | `30` | 5 이상, SIGTERM drain 상한 |
| `RAG_REQUEST_TIMEOUT_SECONDS` | `30` | 5 이상, Upstage/Anthropic 요청 timeout |

`embedding_concurrency`와 `llm_concurrency`가 item concurrency보다 크면 validation error로 시작을 막는다. worker replica를 늘리면 provider 총 동시성은 `replica 수 × 설정값`이 되므로 운영자는 replica별 값을 나눠야 한다.

compose의 `x-app-environment`에 값을 넣어 web과 worker 설정 parsing을 일치시키되 실제 사용은 worker만 한다. BYOK 기본값은 `RAG_EXECUTION_MODE=parallel`, item/embedding 4, LLM 2다. 사용자별 Anthropic 한도를 알기 전에는 LLM 동시성을 더 높이지 않는다.

## 10. 로그와 API

jobs API 응답 schema는 바꾸지 않는다.

```json
{
  "item_progress": {
    "total": 950,
    "completed": 128,
    "succeeded": 126,
    "failed": 2,
    "percent": 13
  }
}
```

operation log는 매 item마다 만들지 않는다. 10개 완료 또는 5초 중 먼저 도달한 시점과 step 종료 시 `rag_progress` event를 남긴다.

```json
{
  "step_key": "analyze_comments",
  "completed": 128,
  "total": 950,
  "in_flight": 2,
  "item_concurrency": 2,
  "embedding_retries": 1,
  "llm_retries": 0,
  "input_tokens": 12345,
  "output_tokens": 2345,
  "elapsed_ms": 84122
}
```

prompt 원문, API key와 Authorization header는 operation log에 넣지 않는다. Langfuse I/O capture는 기존 opt-in 설정을 유지한다.

## 11. 테스트 설계

### 11.1 Retrieval/client

`tests/test_dual_retriever.py`:

- definition/example 동시 성공에서 embedding 1회
- definition 실패 시 example-only
- example 실패 시 definition-only
- embedding 실패 시 collection query 0회
- 기존 `query_texts` 방식과 결과 ID/거리 순서 동일
- 950개 fixture에서 embedding 호출 950회

`tests/test_embeddings.py`:

- 여러 `embed` 호출에 같은 injected HTTP client 사용
- `close()` 한 번 호출
- 429 `Retry-After`, timeout과 non-retry 401 분기

### 11.2 Persistence/progress

`tests/test_analysis_result_store.py`:

- comment/script result insert와 counter 증가가 한 transaction
- 같은 outcome 두 번 저장 시 result 1개, completed 1
- attempt mismatch면 result/counter 변경 없음
- step 시작·종료 reconcile이 잘못된 legacy counter 교정
- 기존 result가 있는 source를 resume query에서 제외
- item 저장 후 crash fixture에서 나머지 item만 실행

SQLite 단위 테스트와 PostgreSQL integration test를 둘 다 실행한다. PostgreSQL에서는 두 session이 같은 result를 동시에 insert하는 barrier test로 unique/idempotency를 확인한다.

### 11.3 Executor

`tests/test_rag_executor.py`:

- fake classifier active count가 설정값을 넘지 않음
- future 저장 순서가 source 순서와 달라도 progress 단조 증가
- source 100개에서도 in-flight future가 concurrency 이하
- concurrency 1 결과와 concurrency 4 결과가 동일
- 100개 × 50ms fake I/O에서 concurrency 4가 순차 대비 3배 이상 빠름
- item failure가 다른 item 실행을 중단하지 않음
- 모든 result commit 전 다음 pipeline handler 미실행
- stop event 뒤 신규 submit 없음과 누락 item resume

시간 기반 테스트는 CI 부하에 민감하므로 absolute time이 아니라 동일 process의 순차/병렬 비율을 비교하고 충분한 50ms fake latency를 사용한다.

### 11.4 Fencing/recovery

`tests/test_job_pipeline.py`:

- attempt 1 실행 중 recovery 후 attempt 2가 시작되면 attempt 1 finish 폐기
- stale 실행이 job finalize를 수행하지 않음
- graceful shutdown은 즉시 pending 복귀
- hard crash fixture는 stale timeout 뒤 누락 result만 재개
- active coordinator heartbeat는 stale recovery 대상이 아님

### 11.5 전체 gate

- `git diff --check`
- `uv run ruff check .`
- `uv run python -m compileall -q app tests scripts experiments`
- `uv run pytest -q`
- SQLite migration upgrade/downgrade/upgrade
- PostgreSQL migration upgrade/downgrade/upgrade
- `docker compose config --quiet`
- `docker compose -f compose.yaml -f compose.dev.yaml config --quiet`
- `docker compose -f compose.yaml -f compose.test.yaml config --quiet`
- `docker compose -f compose.yaml -f compose.prod.yaml config --quiet`
- fake Compose E2E job/report

schema migration이 없는 단계에서도 기존 migration 왕복을 실행해 모델 변경이 우발적으로 포함되지 않았는지 확인한다.

## 12. 구현 브랜치와 merge 순서

각 단계는 독립 브랜치에서 구현하고 정합성 gate 통과 후 `main`에 `--no-ff` merge한다. 브랜치는 삭제하지 않는다.

### 12.1 `perf/rag-dual-retrieval-reuse`

범위:

- `DualVectorRetriever`
- query embedding 1회 재사용
- Upstage/Chroma/Anthropic client 생명주기
- retrieval/client 테스트

merge gate:

- item당 embedding 1회
- 기존 retrieval 결과와 prompt contract 동일
- 전체 backend 회귀 통과

### 12.2 `feat/rag-item-checkpoints`

범위:

- DTO와 result store
- dialect별 idempotent insert
- progress atomic update/reconcile
- resume query
- attempt fencing

merge gate:

- SQLite/PostgreSQL 중복 insert race 통과
- crash/resume와 stale fencing 통과
- jobs/report API contract 동일

### 12.3 `feat/rag-intra-job-parallelism`

범위:

- `RagRuntime`, classifier pool과 bounded coordinator
- sequential/parallel 모드
- signal/shutdown 처리
- 설정/Compose 연결

merge gate:

- max in-flight 제한
- concurrency 4 fake I/O 3배 이상 개선
- 다음 pipeline step 진입 barrier
- 전체 Compose/fake E2E 통과

### 12.4 `feat/rag-provider-backpressure`

범위:

- provider semaphore
- retry/backoff/Retry-After
- 주기 progress log와 usage 집계
- production smoke runbook

merge gate:

- 429/5xx/timeout/non-retry 오류 matrix 통과
- retry 외 provider 호출 증가 없음
- secret scan 통과

## 13. Rollout

1. 12.1과 12.2를 `RAG_EXECUTION_MODE=sequential`로 배포한다.
2. 기존 job 하나와 100개 fake fixture에서 embedding 호출 수, 결과, progress를 비교한다.
3. 12.3을 배포하되 production은 계속 sequential로 둔다.
4. 작은 production job을 concurrency 2로 실행한다.
5. 429 비율, p95 item latency, Anthropic/Upstage 호출 수, token usage와 DB 오류를 확인한다.
6. 이상이 없으면 일반 job에 concurrency 2를 적용한다.
7. 950개 규모 job에서 concurrency 4를 별도 검증한 뒤 상향 여부를 결정한다.

rollback은 worker env의 `RAG_EXECUTION_MODE=sequential` 변경과 worker 재시작으로 수행한다. 이미 저장된 item 결과는 재사용하므로 완료 item을 다시 호출하지 않는다.

## 14. 완료 기준

- production dual retrieval의 query embedding이 retry 제외 item당 한 번이다.
- HTTP/Chroma/Anthropic client가 item마다 재생성되지 않는다.
- RAG 이외 pipeline step은 기존 순서와 동작을 유지한다.
- item concurrency와 provider concurrency 상한을 넘지 않는다.
- 중복 완료, stale worker, worker 재시작에도 결과와 progress가 정확하다.
- jobs/report API와 prompt/provenance contract가 바뀌지 않는다.
- sequential rollback과 누락 item resume가 검증된다.
- 모든 단계별 merge gate와 배포 전 전체 gate가 통과한다.
