# Worker stale job 자동 회수

## 배경

2026-07-15 job `ca375d25-3fd7-470f-a6de-eb4f6671a2d6`이 댓글·답글 942건과 자막 8개를 수집한 뒤 `analyze_comments` 실행 중 worker 재배포로 중단됐다. 기존 worker는 `pending` job만 claim했고 `WORKER_STALE_AFTER_SECONDS` 설정을 사용하지 않아 job이 `running`에 고정됐다.

사용자 요청에 따라 이 job은 삭제했다. `operation_logs`와 `api_quota_events`의 job 외래키는 cascade가 아니므로 두 테이블의 종속 row를 먼저 삭제한 뒤 `analysis_jobs`를 삭제했고, API의 `JOB_NOT_FOUND` 404를 확인했다.

## 회수 방식

1. step 시작 시 `job_steps.heartbeat_at`을 기록한다.
2. 댓글·자막 RAG는 item 하나가 완료될 때마다 진행 counter와 heartbeat를 같은 별도 transaction에서 갱신한다.
3. worker poll 시작 시 `running` step 중 heartbeat가 stale 기준보다 오래된 job 한 건을 row lock으로 선택한다.
4. 해당 step만 `pending`으로 되돌리고 job도 `pending`으로 전환한다.
5. `attempt_count`는 유지하므로 재실행 시 증가한다.
6. `stale_job_recovered` operation log에 step과 이전 attempt 수를 기록한다.
7. 같은 poll에서 다시 claim해 중단된 step부터 pipeline을 계속한다.

기본 stale 기준은 `WORKER_STALE_AFTER_SECONDS=900`이다. 단순히 step 시작 시각만 사용하지 않으므로 15분 이상 걸리는 정상적인 대용량 RAG를 고아 job으로 오인하지 않는다.

## 동시성과 한계

- stale 후보는 `FOR UPDATE SKIP LOCKED`로 선택해 여러 worker가 같은 job을 동시에 회수하지 않게 한다.
- 현재 분석 결과는 step transaction 마지막에 저장되므로 worker crash 시 미완료 transaction이 rollback되고 같은 step을 안전하게 다시 실행할 수 있다.
- 향후 item 결과를 개별 commit하거나 분산 queue로 전환하면 item idempotency key를 먼저 도입해야 한다.
- RAG가 아닌 장시간 step은 시작 heartbeat만 가진다. 해당 step이 stale 기준보다 오래 걸릴 가능성이 생기면 주기 heartbeat를 추가해야 한다.

## 성공 기준

- 오래된 heartbeat의 `running` job은 다음 worker poll에서 자동 완료된다.
- 최근 heartbeat의 active job은 회수되지 않는다.
- recovery 후 step `attempt_count`가 증가한다.
- recovery operation log가 남는다.
- SQLite와 PostgreSQL에서 heartbeat migration이 왕복 가능하다.

## 개발 환경 적용 결과

- PostgreSQL migration `c42f3a91e8b0` head 적용 완료
- `WORKER_STALE_AFTER_SECONDS=900` 주입 확인
- stale recovery method가 포함된 worker image 재빌드 및 재기동 완료
- 삭제 대상 job의 API 404 확인
- backend 76개 테스트와 dev/test/prod Compose config 통과
