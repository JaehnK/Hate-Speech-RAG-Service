# Job 내부 RAG 병렬 처리 계획

## 범위

API가 생성한 job은 지금처럼 background worker가 비동기로 처리한다. 한 worker가 job 하나를 계속 소유하고 pipeline step은 순서대로 실행한다. 그 안에서 `analyze_comments`와 `analyze_script` 두 RAG step만 item 단위로 제한된 병렬 실행을 한다.

```text
API request
  -> analysis job 생성 후 즉시 job_id 반환
  -> worker가 job 하나를 점유
     -> 수집 및 준비 step 순차 실행
     -> analyze_comments
        -> 댓글/답글 RAG 호출 N개를 bounded parallel 실행
        -> 모든 item이 terminal이면 다음 step
     -> analyze_script
        -> 자막 segment RAG 호출 N개를 bounded parallel 실행
        -> 모든 item이 terminal이면 다음 step
     -> network/report/finalize step 순차 실행
```

여기서 내부 비동기 처리는 별도 job이나 별도 queue를 뜻하지 않는다. 현재 Anthropic, Chroma, Upstage adapter가 동기식이므로 구현은 worker process 안의 bounded `ThreadPoolExecutor`를 사용한다. provider adapter가 비동기 client로 바뀌어도 아래 item 저장과 진행률 계약은 유지한다.

## 하지 않는 것

- pipeline step끼리 병렬 실행하지 않는다.
- 여러 worker가 같은 job의 RAG item을 나눠 처리하지 않는다.
- RAG 전용 queue, consumer 또는 별도 Docker service를 만들지 않는다.
- 수집, network, report 생성에는 executor를 적용하지 않는다.
- 전체 item을 무제한으로 submit하지 않는다.

## 현재 기준선과 제약

현재 `CommentAnalyzer`와 `ScriptAnalyzer`는 source item을 순차 분류하고, worker가 가진 SQLAlchemy `Session` 하나에 결과를 모아 step 마지막에 flush한다. 진행률은 별도 transaction에서 item 완료 event마다 `+ 1` 한다.

이 loop만 thread로 감싸면 다음 문제가 생긴다.

- thread 사이에서 SQLAlchemy `Session`이나 ORM instance를 공유할 수 없다.
- worker가 중단되면 step 마지막에 commit되지 않은 완료 결과를 모두 다시 호출한다.
- 중복 완료 event가 발생하면 진행률이 실제 item 수보다 커질 수 있다.
- Upstage embedding과 Anthropic generation이 동시에 급증해 429가 발생할 수 있다.

따라서 외부 RAG 호출과 DB 저장을 분리하고, 기존 결과 테이블을 item checkpoint로 사용한다.

production dual retrieval은 같은 query text를 definition과 example collection에 각각 `query_texts`로 전달하므로 item 하나당 query embedding을 두 번 생성한다. Upstage client는 embedding 요청마다 새 `httpx.Client`를 만들고, collection 조회도 매번 새 Chroma `PersistentClient`를 만든다. 병렬화 전에 이 중복과 연결 생성 비용을 제거해야 한다.

## 확정 설계

### 1. Job과 step 소유권

- 기존 worker가 job 하나를 점유하는 정책을 유지한다.
- RAG executor는 `analyze_comments` 또는 `analyze_script`가 실행되는 동안에만 존재한다.
- 해당 step의 모든 future가 terminal 상태가 되고 결과 저장까지 끝나야 다음 pipeline step으로 이동한다.
- worker 종료 요청이 오면 신규 item 제출을 중단하고, grace period 뒤 미완료 future를 취소한 다음 outer job의 stale recovery에 맡긴다.
- RAG step 완료 시 시작할 때 읽은 `attempt_count`가 현재 값과 같은지 확인한다. stale recovery 뒤 살아난 이전 실행자가 새 실행의 step 상태를 덮어쓰지 못하게 한다.

### 2. 실행 대상과 checkpoint

새 item ledger나 lease table은 만들지 않는다. 이미 존재하는 결과 테이블의 unique constraint를 checkpoint로 사용한다.

- 댓글/답글: `UNIQUE (analysis_run_id, comment_snapshot_id)`
- 자막: `UNIQUE (analysis_run_id, transcript_segment_id)`

step 시작 또는 재시작 시 source item 전체와 기존 결과의 source ID를 비교한다. 결과가 없는 item만 executor에 제출한다. 성공과 최종 실패 결과는 모두 terminal checkpoint이며, infrastructure 재시도는 결과를 저장하기 전에 item 내부에서 수행한다.

worker crash 직전에 외부 호출이 끝났지만 결과가 저장되지 않았다면 그 item의 provider 호출은 다시 발생할 수 있다. 실행 보장은 **at-least-once 외부 호출 + exactly-once 결과 반영**이다.

### 3. Dual retrieval과 client 생명주기

- source text와 source type에서 retrieval query를 한 번 만든다.
- query embedding을 한 번 생성하고 동일 vector를 definition과 example collection의 `query_embeddings`에 전달한다.
- 한 collection 조회만 실패하면 다른 collection 결과를 사용하는 현재 degraded mode를 유지한다.
- embedding 자체가 실패하면 두 collection을 모두 조회할 수 없으므로 item retrieval 실패로 기록한다.
- 순차 모드는 classifier 하나가 Anthropic client, Upstage `httpx.Client`, Chroma client와 두 collection handle을 계속 재사용한다.
- 병렬 모드는 executor thread마다 classifier와 client 묶음을 한 번 만들고 여러 item에 재사용한다.
- executor 종료 시 thread별 close hook에서 HTTP client와 관측성 resource를 정리한다.
- thread safety가 검증되지 않은 client를 process global singleton으로 공유하지 않는다.

동시성 도입 전 기준으로 item 950개는 retrieval query embedding 요청이 약 1,900번 발생한다. 동일 embedding을 재사용하면 retry를 제외하고 950번으로 줄어야 한다. 여러 item의 embedding micro-batch는 이 단계의 측정 결과에서 HTTP overhead가 여전히 유의미할 때만 후속 최적화로 추가한다.

### 4. Thread와 transaction 경계

- worker의 기존 `Session`, `AnalysisRun`, `CommentSnapshot`, `TranscriptSegment` ORM instance를 executor에 전달하지 않는다.
- coordinator가 `run_id`, `source_id`, 원문, source type만 immutable DTO로 만든다.
- executor thread마다 별도 classifier를 생성하고 외부 retrieval·generation만 실행한다.
- 완료 future는 ORM과 무관한 결과 DTO를 반환한다.
- coordinator는 `session_factory`로 짧은 transaction을 열어 결과 row 하나를 `ON CONFLICT DO NOTHING`으로 insert한다.
- 실제 insert된 경우에만 같은 transaction에서 성공 또는 실패 진행 counter를 증가시킨다.
- unique 충돌은 이미 저장된 동일 item 완료로 처리하고 진행률을 중복 반영하지 않는다.
- DB connection을 잡은 채 외부 API 응답을 기다리지 않는다.
- 보고서의 자막 순서는 future 완료 순서가 아니라 기존 `segment_index`로 정렬한다.

### 5. 진행률과 heartbeat

jobs API의 `items_total`, `items_completed`, `items_succeeded`, `items_failed` 계약은 유지한다. 병렬 모드에서는 완료 event를 무조건 더하지 않고 source와 결과 테이블을 기준으로 projection한다.

- `items_total`: 해당 RAG step의 source item 수
- `items_completed`: 저장된 결과 row 수
- `items_succeeded`: `status = succeeded` 결과 수
- `items_failed`: `status = failed` 결과 수

각 item transaction의 조건부 counter 증가로 out-of-order 완료에도 값이 역행하거나 전체 수를 넘지 않는다. step 시작과 종료 시 결과 테이블의 실제 row를 집계해 projection을 재조정한다. item마다 전체 `COUNT` query를 반복하지 않는다.

coordinator는 item 완료 여부와 별개로 주기적으로 `job_steps.heartbeat_at`을 갱신한다. 모든 provider 호출이 오래 걸리는 상황도 active job으로 인식해야 하기 때문이다. operation log는 item마다 쓰지 않고 일정 item 수 또는 시간 간격으로 묶어 기록한다.

### 6. 제한된 동시성과 backpressure

초기 설정은 다음과 같이 둔다.

| 설정 | 초기값 | 의미 |
| --- | ---: | --- |
| `RAG_EXECUTION_MODE` | `sequential` | rollout 중 `sequential` 또는 `parallel` 선택 |
| `RAG_ITEM_CONCURRENCY` | `2` | RAG step 하나의 최대 동시 item 수 |
| `RAG_EMBEDDING_CONCURRENCY` | `2` | Upstage embedding 최대 동시 호출 수 |
| `RAG_LLM_CONCURRENCY` | `2` | Anthropic generation 최대 동시 호출 수 |
| `RAG_ITEM_MAX_ATTEMPTS` | `3` | 일시적 infrastructure 오류의 최대 시도 수 |

executor에는 최대 동시 실행 수만큼만 item을 제출하고, 하나가 끝날 때 다음 item을 넣는다. provider별 semaphore는 item 동시성보다 작게 설정할 수 있다. 429의 `Retry-After`와 일시적 5xx·timeout만 지수 backoff와 jitter로 재시도한다. prompt validation을 위한 기존 1회 재생성은 infrastructure 재시도와 별도로 집계한다.

운영 확인 후 item 동시성을 4로 올릴 수 있지만, provider 동시성은 실제 429 비율과 latency를 기준으로 별도 조절한다.

## 구현 순서

### Phase P0. 순차 기준선 고정

작업:

- fake embedding/LLM에 지연, 429, 5xx와 timeout을 주입하는 fixture를 추가한다.
- 댓글과 자막의 결과 payload, embedding/LLM 호출 수, client 생성 수와 jobs API 진행률을 snapshot으로 고정한다.
- 100개 fake item의 순차 처리 시간을 측정한다.

검증:

- `RAG_EXECUTION_MODE=sequential`에서 현재 결과와 호출 수가 변하지 않는다.
- RAG 이외 step의 실행 순서와 transaction 경계가 변하지 않는다.

### Phase P1. Retrieval 중복 제거와 client 재사용

작업:

- dual collection query 전에 query embedding을 한 번 생성한다.
- 동일 embedding vector로 definition과 example collection을 각각 조회한다.
- classifier가 Chroma client/collection handle과 외부 HTTP client를 생명주기 동안 재사용하게 한다.
- classifier factory와 명시적인 close 계약을 추가한다.

검증:

- 두 collection을 조회하는 item 하나당 embedding 호출은 retry 없이 정확히 한 번이다.
- item 950개 fixture에서 embedding 호출은 950번이며 기존 결과 순위와 prompt context가 같다.
- 여러 item을 분류해도 client 생성 수는 classifier 생명주기당 한 번이다.
- 한 collection 장애에서 다른 collection 결과를 사용하는 degraded mode가 유지된다.

### Phase P2. Item별 저장과 재시작 checkpoint

작업:

- classifier 결과를 ORM과 무관한 DTO로 반환하게 한다.
- item 하나의 결과를 `ON CONFLICT DO NOTHING`과 별도 짧은 transaction으로 저장한다.
- 기존 결과가 있는 source item을 건너뛰는 resume query를 구현한다.
- 실제 insert와 조건부 progress 증가를 같은 transaction에 두고 step 시작·종료 시 결과 row와 재조정한다.
- RAG coordinator heartbeat와 step attempt fencing을 추가한다.

검증:

- 같은 step을 두 번 실행해도 결과 row와 완료 수가 늘지 않는다.
- item 저장 전 crash는 해당 item만 재호출하고 저장 완료 item은 건너뛴다.
- unique 충돌과 늦은 응답에도 결과와 완료 수가 각각 하나다.
- item 수와 무관하게 item당 DB transaction은 결과/progress 한 번이고 전체 집계는 step당 두 번이다.
- 기존 DB schema와 jobs/report API contract가 유지된다.

### Phase P3. Job 내부 bounded parallelism

작업:

- analyzer loop를 coordinator와 item executor로 분리한다.
- executor thread별 classifier를 만드는 bounded `ThreadPoolExecutor`를 연결한다.
- comment/reply와 script segment에 같은 executor 계약을 적용한다.
- graceful shutdown 시 submit 중단, 제한된 drain과 outer stale recovery를 연결한다.

검증:

- 동시성 1은 순차 모드와 결과·provider 호출 수가 같다.
- 설정한 최대 in-flight item과 provider 호출 수를 넘지 않는다.
- 100개 fake I/O item, 동시성 4에서 순차 대비 wall time이 3배 이상 개선된다.
- 완료 순서가 섞여도 진행률이 단조 증가하고 최종 합계가 전체 수와 같다.
- RAG step의 모든 결과 저장 전에는 다음 pipeline step이 시작되지 않는다.
- worker 강제 종료 뒤 기존 결과를 보존하고 누락 item만 처리해 job이 완료된다.

### Phase P4. Provider 보호와 rollout

작업:

- embedding과 LLM에 별도 semaphore, retry와 backoff를 적용한다.
- operation log/metrics에 in-flight, retry, provider latency와 token usage를 기록한다.
- fake mode에서 동시성 1, 2, 4를 검증한 뒤 production 작은 job을 동시성 2로 실행한다.
- 429, 실패율, p95 latency, token 사용량을 확인한 뒤 동시성을 조정한다.

검증:

- 429 fixture에서 `Retry-After`와 최대 시도를 지킨다.
- validation 재생성과 network 재시도가 구분되어 기록된다.
- 재시도 외 provider 호출 수와 비용 추정치가 순차 모드보다 늘지 않는다.
- `RAG_EXECUTION_MODE=sequential` rollback이 기존 checkpoint를 보존한다.

실제 API smoke는 비용을 발생시키므로 fixture 검증 뒤 작은 job으로 수행한다. 새 API key가 필요한 경우에만 사용자에게 요청한다.

## 완료 기준

- job은 기존 worker 하나가 처음부터 끝까지 소유한다.
- dual retrieval은 item당 query embedding을 한 번만 수행하고 client 연결을 재사용한다.
- RAG 두 step의 item 호출만 설정된 제한 안에서 병렬 실행된다.
- 다른 pipeline step은 기존과 같은 순서로 실행된다.
- 중복 실행, out-of-order 완료와 worker crash 뒤에도 결과와 진행률이 정확하다.
- provider rate limit을 넘기는 무제한 fan-out이 없다.
- sequential rollback 경로가 검증된다.
- backend 전체 테스트, fake E2E와 dev/test/prod Compose config가 통과한 뒤 merge한다.
