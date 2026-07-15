# RAG job 사용량 및 진행률 진단

## 대상

- 확인 일시: 2026-07-15
- job: `35181ecb-c628-4a63-b41c-9b2f7ef5322b`
- video: `ZShDaSoNjs4`
- 브랜치: `feat/rag-job-progress`

## 진단 순서와 결과

1. job API 확인
   - 댓글·답글 404건, 자막 세그먼트 33건을 수집했다.
   - `analyze_comments`가 약 22분 후 `UNEXPECTED_ERROR`로 실패했다.
   - 기존 구현은 step 마지막에 한 번 flush하므로 댓글 결과는 0건으로 rollback됐다.
2. worker 설정 확인
   - `PIPELINE_MODE=production`
   - LLM provider/model은 `anthropic` / `claude-haiku-4-5-20251001`
   - Anthropic과 Upstage key가 모두 주입된 상태였다.
3. Anthropic 최소 호출 확인
   - key 원문을 출력하지 않고 같은 worker/config로 직접 호출했다.
   - 응답 usage는 input 36 tokens, output 13 tokens였다.
   - API 호출 경로와 key는 정상이다. Dashboard가 0이면 key가 속한 workspace, API key filter, 시간 범위를 확인해야 한다.
4. PostgreSQL 오류 확인
   - `2026-07-15 04:09:16 UTC`에 `value too long for type character varying(64)`가 기록됐다.
   - 모델이 반환한 `hate_type` 중 하나가 DB의 64자 제한을 초과했고, 404건 bulk INSERT 전체가 rollback됐다.
5. 자막 분석 확인
   - 33건은 성공했고 job은 최종 `partial_success`가 됐다.

## 수정 사항

- 댓글·자막 RAG step에 `items_total`, `items_completed`, `items_succeeded`, `items_failed`를 추가했다.
- item 완료 event마다 별도 DB transaction에서 counter를 원자적으로 증가시킨다.
- job API에 `item_progress`를 추가하고 jobs 화면과 live process log에 `완료 / 전체 · 성공 · 실패`를 표시한다.
- 예전 job에는 저장된 counter가 없으므로 수집 총량과 “상세 완료 수 미기록”을 명확히 표시한다.
- `hate_type`을 `VARCHAR(64)`에서 `TEXT`로 변경했다.
- 예상하지 못한 step 예외는 worker log에 traceback과 job/step context를 남긴다.

## 동시 처리 고려

진행률은 analyzer가 계산한 절대값을 덮어쓰지 않고 DB에서 `+ 1`로 갱신하므로 현재 순차 실행에서 counter가 역행하지 않는다. 다만 job 내부 병렬 실행의 중복 완료에서는 과대 집계될 수 있다. 병렬화 전 기존 결과 unique constraint를 checkpoint로 사용하고 저장 결과 집계 방식으로 전환하는 계획은 `docs/22_rag_parallel_processing_plan.md`에 정의했다.

## 현재 job에 대한 해석

기존 job은 새 counter 도입 전에 실행됐기 때문에 댓글 404건 중 정확한 중간 완료 숫자를 사후 복원할 수 없다. PostgreSQL의 404건 bulk INSERT와 실행 시간을 보면 분류 호출 후 저장 단계에서 실패한 것은 확인되지만, 성공/실패 수를 추측해 DB에 기록하지 않는다. 자막 33건은 저장 결과와 step 상태로 완료를 확인할 수 있다.

## 개발 환경 적용 결과

- PostgreSQL을 migration `b6dd8f31c7e2` head까지 적용했다.
- 새 `DatabaseJobProgressReporter`가 포함된 worker image를 다시 빌드하고 worker를 재기동했다.
- 기존 job API와 jobs 화면은 `partial_success` 및 legacy counter 안내를 정상 표시한다.
- 새 분석은 별도 요청하지 않았다. 같은 영상 재분석은 Anthropic/Upstage 비용을 다시 발생시키므로 사용자가 새 job을 생성할 때 교정된 저장 경로와 진행 counter가 적용된다.

## 2026-07-15 후속 checkpoint 구현

초기 진단 당시의 counter-only reporter는 `feat/rag-item-checkpoints`에서 결과 저장 경로에 통합됐다. 현재 구현은 item 결과와 조건부 progress 증가를 같은 transaction으로 commit하고, unique conflict에서는 counter를 증가시키지 않는다. step 재시작 시 기존 결과를 건너뛰며 시작·종료 reconcile이 실제 결과 row에서 progress를 교정한다. 구현 기록은 `docs/24_rag_parallel_delivery.md`를 따른다.
