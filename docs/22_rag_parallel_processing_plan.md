# RAG 병렬 처리 계획

## 목표와 현재 기준선

댓글과 자막 segment의 RAG 분류를 제한된 동시성으로 실행해 처리 시간을 줄이되, worker 중단과 중복 실행 뒤에도 결과와 진행률이 정확해야 한다. 이 문서는 로컬 병렬 실행부터 여러 worker의 분산 실행까지 같은 item 계약을 유지하는 구현 순서를 정의한다.

현재 `CommentAnalyzer`와 `ScriptAnalyzer`는 다음 방식으로 동작한다.

- 한 worker가 job 하나를 점유하고 step을 순서대로 실행한다.
- 한 step 안에서는 source item을 순차 분류한다.
- SQLAlchemy `Session` 하나에 결과를 모아 step 마지막에 flush·commit한다.
- 진행률은 별도 transaction에서 item 완료마다 counter를 `+ 1` 한다.
- 댓글·자막 결과 테이블은 각각 `(analysis_run_id, source_id)` unique constraint를 가진다.

이 loop만 thread로 감싸면 thread 사이의 `Session` 공유, 중복 완료에 따른 counter 과대 집계, worker 종료 시 전체 step 재실행, 외부 provider의 429 증가 문제가 생긴다. 따라서 item 상태와 소유권을 먼저 영속화한다.

## 확정 설계

### 1. Item 실행 단위

새 `rag_analysis_items` 테이블에 분석 대상 하나당 row 하나를 만든다.

| 필드 | 용도 |
| --- | --- |
| `analysis_run_id`, `step_key` | 실행과 댓글·자막 step 식별 |
| `source_type`, `source_id` | comment, reply, script segment 원본 식별 |
| `status` | `pending`, `running`, `succeeded`, `failed` |
| `attempt_count` | item claim 횟수 |
| `lease_owner`, `lease_token` | 현재 실행자와 claim 세대 식별 |
| `lease_expires_at`, `heartbeat_at` | 중단된 item의 자동 회수 기준 |
| `error_code`, `error_message` | 최종 item 실패 원인 |
| `created_at`, `started_at`, `finished_at` | 실행 추적 |

`(analysis_run_id, step_key, source_type, source_id)`를 unique key로 둔다. step 시작 시 source snapshot에서 `INSERT ... ON CONFLICT DO NOTHING`으로 item을 materialize하므로 같은 step을 재실행해도 작업 수가 늘지 않는다.

### 2. Claim과 lease

1. coordinator가 `pending` 또는 lease가 만료된 `running` item을 `FOR UPDATE SKIP LOCKED`로 최대 동시성만큼 claim한다.
2. claim할 때 새 `lease_token`, 만료 시각, heartbeat와 `attempt_count`를 기록한다.
3. 외부 호출은 DB transaction 밖에서 수행한다.
4. 긴 호출 중에는 active item lease와 `job_steps.heartbeat_at`을 주기적으로 갱신한다.
5. 결과 저장 시 `lease_token`이 여전히 일치하는 item만 terminal 상태로 전환한다.
6. worker가 죽으면 lease가 만료된 item만 다시 claim하고 완료 item은 건너뛴다.

실행 보장은 exactly-once 호출이 아니라 **at-least-once 실행 + exactly-once 결과 반영**이다. 외부 호출 직후 worker가 죽으면 같은 요청이 한 번 더 발생할 수 있으므로 provider 비용도 중복될 수 있다는 한계는 operation log에 남긴다.

### 3. Transaction과 thread 경계

- SQLAlchemy `Session`과 ORM instance를 thread 사이에 전달하지 않는다.
- coordinator는 source ID, 원문, source type만 immutable DTO로 만든다.
- 각 item 완료는 새 session의 짧은 transaction에서 결과 upsert와 item terminal 전이를 함께 수행한다.
- 기존 결과 unique constraint를 최종 방어선으로 유지한다.
- lease를 잃은 실행자의 늦은 응답은 저장하지 않는다.
- 보고서의 자막 순서는 실행 완료 순서가 아니라 기존 `segment_index`로 정렬한다.

### 4. 제한된 동시성과 backpressure

현재 Anthropic, Chroma, Upstage 호출 경로가 동기식이므로 첫 구현은 `ThreadPoolExecutor` 기반의 제한된 병렬 처리로 한다. `asyncio` 전환은 provider adapter가 비동기 client를 제공할 때 별도 단계로 평가하며, item 저장 계약은 바꾸지 않는다.

초기 설정은 다음과 같이 둔다.

| 설정 | 초기값 | 의미 |
| --- | ---: | --- |
| `RAG_EXECUTION_MODE` | `sequential` | rollout 중 `sequential` 또는 `parallel` 선택 |
| `RAG_ITEM_CONCURRENCY` | `2` | job 하나의 최대 동시 item 수 |
| `RAG_ITEM_LEASE_SECONDS` | `180` | heartbeat가 없을 때 item을 회수하는 시간 |
| `RAG_ITEM_MAX_ATTEMPTS` | `3` | infrastructure 오류의 item 재시도 상한 |

운영 확인 뒤 기본 동시성을 4로 올린다. executor queue에는 전체 item을 한꺼번에 넣지 않고 최대 동시 실행 수만큼만 제출한다. Upstage retrieval과 Anthropic generation에는 provider별 semaphore를 두고 429의 `Retry-After`와 일시적 5xx만 지수 backoff와 jitter로 재시도한다. prompt validation을 위한 기존 1회 재생성은 infrastructure 재시도와 별도로 집계한다.

DB connection pool은 `worker 수 × RAG_ITEM_CONCURRENCY`에 API와 progress/lease 갱신 여유분을 더해 산정한다. pool이 이보다 작으면 동시성을 낮추며, connection을 확보한 채 외부 API 응답을 기다리지 않는다.

### 5. 진행률 계약

기존 jobs API의 `items_total`, `items_completed`, `items_succeeded`, `items_failed` 필드는 유지한다. 다만 병렬 모드에서는 완료 이벤트를 무조건 더하지 않고 `rag_analysis_items`의 terminal 상태를 집계해 `job_steps` projection을 갱신한다.

- `items_total`: materialize된 item 수
- `items_completed`: `succeeded + failed`
- `items_succeeded`: `status = succeeded`
- `items_failed`: `status = failed`

동일 item의 재시도와 중복 delivery는 한 번만 집계된다. 집계 projection이 어긋나면 item table에서 재생성할 수 있다. 기존 job은 item row가 없으므로 현재 legacy 진행률 표시를 유지한다.

## 구현 순서

### Phase P0. 기준선과 부하 fixture

작업:

- fake embedding/LLM에 지연, 429, 5xx, timeout을 주입할 수 있는 fixture를 추가한다.
- 순차 모드의 처리량, provider 호출 수, DB connection 사용량을 측정한다.
- 댓글과 자막의 현재 결과 payload 및 jobs API contract를 snapshot으로 고정한다.

검증:

- `RAG_EXECUTION_MODE=sequential`에서 현재 결과와 호출 수가 변하지 않는다.
- 100개 fake item의 기준 시간이 반복 측정에서 기록된다.

### Phase P1. Item ledger와 멱등 저장

작업:

- `rag_analysis_items` model, migration, repository를 추가한다.
- step 시작 시 item materialize, claim, lease 갱신, terminal 전이를 구현한다.
- item 결과와 terminal 상태를 item별 짧은 transaction으로 저장한다.
- item 집계에서 기존 progress projection을 갱신한다.
- 기존 step stale recovery가 완료 item을 재실행하지 않도록 연결한다.

검증:

- 같은 step을 두 번 시작해도 item row와 결과 row가 늘지 않는다.
- 결과 저장 전 crash는 lease 만료 뒤 재처리되고, 저장 후 crash는 완료 item을 건너뛴다.
- 중복 claim과 늦은 응답에도 결과와 완료 수가 각각 하나다.
- SQLite와 PostgreSQL migration upgrade/downgrade가 통과한다.

### Phase P2. 단일 worker의 bounded parallelism

작업:

- analyzer loop를 coordinator와 item executor로 분리한다.
- executor thread마다 별도 classifier를 생성하는 bounded `ThreadPoolExecutor`를 연결한다.
- comment/reply와 script segment에 같은 실행기를 사용한다.
- 종료 신호 시 신규 claim을 중단하고 grace period 동안 실행 중 item만 drain한다.

검증:

- 동시성 1은 순차 모드와 결과·호출 수가 같다.
- 설정한 최대 in-flight item 수를 넘지 않는다.
- 100개 fake I/O item, 동시성 4에서 순차 대비 wall time이 3배 이상 개선된다.
- 완료 순서가 뒤섞여도 진행률이 단조 증가하고 최종 합계가 전체 수와 같다.
- worker 강제 종료 뒤 lease 시간 내에 미완료 item만 회수된다.

### Phase P3. Provider rate limit과 관측성

작업:

- embedding과 LLM에 별도 concurrency gate를 둔다.
- retry 대상과 비대상을 분리하고 `Retry-After`, backoff, jitter, 최대 시도를 적용한다.
- operation log/metrics에 queued, running, retry, provider latency, token usage를 기록한다.
- 최근 429 비율이 임계치를 넘으면 신규 claim 속도를 낮추는 backpressure를 적용한다.

검증:

- 429 fixture에서 provider가 지시한 대기 시간을 지키고 최대 시도 뒤 item이 종료된다.
- validation 오류와 network 재시도가 서로 다른 counter로 관측된다.
- 재시도 외 provider 호출 수와 비용 추정치가 순차 모드보다 늘지 않는다.

### Phase P4. 여러 worker의 item 분산 처리

작업:

- job coordinator와 item executor의 생명주기를 분리한다.
- 여러 worker가 같은 step의 item을 `SKIP LOCKED`로 나눠 claim하게 한다.
- coordinator가 terminal item 집계를 확인한 뒤에만 다음 pipeline step으로 이동한다.
- 로컬 persistent Chroma의 multi-process 읽기 안전성을 검증하고, 충족하지 못하면 Chroma server 또는 host별 read-only replica로 전환한다.

검증:

- worker 2개가 source item을 중복 반영하지 않고 나눠 처리한다.
- worker 한 개를 종료해도 다른 worker가 만료 item을 회수해 job을 완료한다.
- coordinator 재시작 뒤에도 다음 step을 중복 실행하지 않는다.

## Rollout과 rollback

1. schema와 sequential-compatible item ledger를 먼저 배포한다.
2. fake mode에서 동시성 1, 2, 4를 순서대로 검증한다.
3. production은 작은 job에서 `parallel`, 동시성 2로 시작한다.
4. 429, 실패율, p95 latency, token 사용량, DB pool 대기를 확인한 뒤 4로 올린다.
5. 문제가 생기면 `RAG_EXECUTION_MODE=sequential`로 되돌린다. item ledger와 완료 결과는 그대로 재사용하므로 완료 item을 다시 호출하지 않는다.

실제 API를 사용하는 검증은 비용을 발생시키므로 코드·fixture 검증 후 별도 smoke job으로 실행한다. 새 API key가 필요한 경우에만 사용자에게 요청한다.

## 완료 기준

- 댓글과 자막 모두 설정된 제한 안에서 병렬 처리된다.
- 중복 실행, out-of-order 완료, worker crash 뒤에도 item 결과와 진행률이 정확하다.
- 기존 jobs API와 report 결과 계약이 유지된다.
- provider rate limit을 넘기는 무제한 fan-out이 없다.
- sequential rollback 경로가 실제로 검증된다.
- migration 왕복, backend 전체 테스트, dev/test/prod Compose config, fake E2E가 통과한 뒤 merge한다.
