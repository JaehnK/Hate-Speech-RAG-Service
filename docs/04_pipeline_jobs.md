# Job Pipeline

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.0 |
| 작성일시 | 2026-07-08 08:35:46 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 job pipeline을 정의한다.

이 문서는 FastAPI 요청 이후 background worker가 어떤 순서로 수집, 분석, 네트워크 생성, 보고서 snapshot 생성을 수행하는지 설명한다.

## 기본 가정

- MVP는 단일 영상만 처리한다.
- 동일 영상이 다시 요청되면 항상 새 job을 생성한다.
- 사용자의 분석 요청 HTTP 응답은 전체 분석 완료를 기다리지 않는다.
- background worker는 PostgreSQL의 `analysis_jobs`, `job_steps`를 polling하는 방식으로 시작한다.
- Redis, Celery, RQ 같은 별도 broker는 MVP 이후 처리량이 필요할 때 도입한다.
- 댓글은 항상 전체 수집과 전체 분석을 목표로 한다.
- 댓글 수집이 완료되지 않았으면 댓글 분석을 성공 처리하지 않는다.
- 공개 자막이 없더라도 댓글 분석과 보고서 생성은 계속할 수 있다.
- 보고서 snapshot은 성공한 artifact와 실패 정보를 함께 담는다.
- RAG 분석은 혐오표현 예시 검색과 혐오표현 정의 문서 검색을 함께 사용한다.

## Job 상태

### analysis_jobs.status

| 상태 | 의미 |
| --- | --- |
| `pending` | job이 생성되었고 worker 실행을 기다린다. |
| `running` | 하나 이상의 step이 실행 중이다. |
| `partial_success` | 필수 산출물 일부는 생성되었지만 독립 step 일부가 실패했다. |
| `succeeded` | MVP 기준 필수 step이 완료되었고 보고서 snapshot이 생성되었다. |
| `failed` | job을 계속할 수 없는 필수 step이 실패했다. |
| `canceled` | 운영자가 job을 중단했다. MVP API에는 포함하지 않는다. |

### job_steps.status

| 상태 | 의미 |
| --- | --- |
| `pending` | 아직 실행되지 않았다. |
| `running` | 현재 실행 중이다. |
| `succeeded` | step이 성공했다. |
| `failed` | step이 실패했다. |
| `skipped` | 선행 조건이 충족되지 않아 실행하지 않았다. |

## Step 목록

| 순서 | step_key | 필수 여부 | 주요 입력 | 주요 출력 |
| --- | --- | --- | --- | --- |
| 1 | `validate_input` | 필수 | 사용자 입력값 | 추출된 video ID |
| 2 | `collect_metadata` | 필수 | video ID | `video_metadata_snapshots` |
| 3 | `collect_comments` | 조건부 필수 | video ID | `comment_snapshots` |
| 4 | `collect_transcript` | 선택 | video ID | `transcript_snapshots`, `transcript_segments` |
| 5 | `create_analysis_run` | 필수 | job, 설정 | `analysis_runs` |
| 6 | `analyze_comments` | 댓글 수집 성공 시 필수 | `comment_snapshots` | `comment_analysis_results` |
| 7 | `analyze_script` | 자막 수집 성공 시 필수 | `transcript_segments` | `script_analysis_results` |
| 8 | `build_comment_network` | 선택 | 댓글 snapshot, 댓글 분석 결과 | `comment_networks`, nodes, edges |
| 9 | `build_report_snapshot` | 필수 | 성공 artifact, 실패 정보 | `report_snapshots` |
| 10 | `finalize_job` | 필수 | step 상태 | 최종 job 상태 |

해석:

- `collect_comments`는 댓글이 활성화된 영상에서는 필수로 본다.
- 댓글 비활성화는 terminal failure가 아니라 댓글 모듈의 부분 실패로 처리한다.
- `collect_transcript`는 공개 자막이 없을 수 있으므로 선택 step이다.
- `build_report_snapshot`은 메타데이터가 수집되었다면 가능한 범위에서 반드시 실행한다.

## 전체 흐름

```text
POST /api/analysis-jobs
  -> validate_input
  -> create analysis_jobs row
  -> initialize job_steps rows
  -> return job_id

worker loop
  -> claim pending job
  -> collect_metadata
  -> collect_comments
  -> collect_transcript
  -> create_analysis_run
  -> analyze_comments
  -> analyze_script
  -> build_comment_network
  -> build_report_snapshot
  -> finalize_job
```

## Worker 실행 모델

MVP 기본 worker는 DB polling 방식이다.

1. worker가 `pending` job을 조회한다.
2. `FOR UPDATE SKIP LOCKED` 방식으로 하나의 job을 점유한다.
3. job 상태를 `running`으로 바꾼다.
4. step을 순서대로 실행한다.
5. 각 step 시작과 종료를 `job_steps`와 `operation_logs`에 기록한다.
6. 최종적으로 `analysis_jobs.status`를 갱신한다.

동시성 정책:

- 같은 job은 한 worker만 실행한다.
- 같은 영상의 여러 job은 동시에 실행될 수 있다.
- MVP에서는 같은 video ID 동시 실행을 막지 않는다. 항상 새 분석 정책과 충돌하지 않기 때문이다.

## Step 상세

### validate_input

책임:

- YouTube URL 또는 video ID에서 video ID를 추출한다.
- video ID 형식을 검증한다.

성공 출력:

- `analysis_jobs.youtube_video_id`

실패 처리:

- 잘못된 입력이면 job을 만들지 않고 API에서 `400`을 반환한다.
- job 생성 이후 발견된 형식 오류는 `failed`로 기록한다.

### collect_metadata

책임:

- 공식 YouTube Data API로 영상 메타데이터를 조회한다.
- 채널 정보가 응답에 포함되거나 추가 조회 가능한 경우 `channels`를 갱신한다.
- 수집 시점의 `video_metadata_snapshots`를 저장한다.

성공 기준:

- video ID가 실제 영상으로 확인된다.
- 제목 또는 최소한의 식별 가능한 메타데이터가 저장된다.

실패 처리:

- 영상이 존재하지 않으면 job 전체를 `failed`로 종료한다.
- API quota 초과는 retryable failure로 기록한다.
- API 키 문제는 admin 확인이 필요한 failure로 기록한다.

### collect_comments

책임:

- 공식 YouTube Data API로 최상위 댓글을 페이지네이션 끝까지 수집한다.
- 각 최상위 댓글의 대댓글을 끝까지 수집한다.
- 수집된 댓글과 대댓글을 `comment_snapshots`에 저장한다.
- 수집 수량, API 호출 수, quota 이벤트를 기록한다.

성공 기준:

- 댓글이 활성화된 영상에서 모든 페이지를 끝까지 순회한다.
- 수집된 모든 댓글 snapshot이 저장된다.

실패 처리:

- 댓글 비활성화는 `COMMENTS_DISABLED`로 기록하고 step은 `failed`가 아니라 `skipped` 또는 부분 실패로 취급한다.
- quota 초과로 전체 수집을 완료하지 못하면 `failed`로 기록하고 댓글 분석을 실행하지 않는다.
- 중간까지 수집된 댓글은 보존하되, 보고서에는 댓글 수집 미완료로 표시한다.

정책:

- MVP에서 댓글 샘플링은 하지 않는다.
- 성공한 댓글 분석 섹션은 전체 수집 완료를 전제로 한다.

### collect_transcript

책임:

- 공개 자막을 조회하고 수집한다.
- 자막을 정규화해서 `transcript_snapshots`에 저장한다.
- 분석 단위로 `transcript_segments`를 생성한다.

성공 기준:

- 공개 자막 텍스트가 하나 이상 수집된다.
- 분석 가능한 segment가 하나 이상 생성된다.

실패 처리:

- 공개 자막 없음은 `CAPTION_NOT_AVAILABLE`로 기록하고 이후 스크립트 분석을 `skipped` 처리한다.
- 자막 수집 도구 오류는 retryable 여부를 기록한다.
- 외부 자막 업로드 fallback은 사용하지 않는다.

### create_analysis_run

책임:

- 현재 job의 분석 실행 단위를 생성한다.
- LLM provider, model, embedding provider, 예시 collection, 정의 collection, retriever 설정, definition corpus version, prompt version을 고정한다.

성공 기준:

- `analysis_runs` row가 생성된다.

실패 처리:

- 예시 또는 정의 vector store 설정이 없거나 모델 설정이 불완전하면 job을 `failed`로 종료한다.

### analyze_comments

책임:

- 수집 완료된 모든 댓글과 대댓글을 분석한다.
- 각 댓글에 대해 유사 혐오표현 예시와 관련 정의 문서를 검색한다.
- 각 댓글별 분석 결과를 `comment_analysis_results`에 저장한다.
- 실패한 댓글은 항목별 실패로 기록한다.

성공 기준:

- `comment_snapshots`의 모든 row에 대해 `succeeded`, `failed`, `skipped` 중 하나의 결과 row가 존재한다.
- 전체 실패 건수가 집계된다.

실패 처리:

- 일부 LLM 호출 실패는 항목별 `failed`로 저장하고 step은 `succeeded` 또는 `partial_success`로 볼 수 있다.
- 대부분 또는 전체 LLM 호출이 실패하면 step을 `failed`로 기록한다.
- 댓글 수집이 미완료이면 이 step은 `skipped` 처리한다.

정책:

- 댓글 수가 많아도 MVP에서는 전체 댓글 분석을 목표로 한다.
- batch size는 구현 설정값으로 둔다.

### analyze_script

책임:

- transcript segment를 순서대로 분석한다.
- 각 segment에 대해 유사 혐오표현 예시와 관련 정의 문서를 검색한다.
- 각 segment 결과를 `script_analysis_results`에 저장한다.

성공 기준:

- 모든 segment에 대해 결과 row가 존재한다.

실패 처리:

- 공개 자막이 없으면 `skipped` 처리한다.
- 일부 LLM 호출 실패는 항목별 `failed`로 저장한다.
- 전체 분석 불가 상태면 step을 `failed`로 기록하되 댓글 분석 결과는 유지한다.

### build_comment_network

책임:

- 댓글과 대댓글 관계를 작성자 기반 방향 그래프로 변환한다.
- 노드, 엣지, 그래프 요약을 저장한다.
- 보고서 렌더링용 payload를 생성한다.

성공 기준:

- `comment_networks`가 생성된다.
- 노드와 엣지가 저장된다.
- 댓글 또는 대댓글이 부족한 경우 빈 그래프 요약을 저장할 수 있다.

실패 처리:

- 댓글 수집 또는 댓글 분석이 없으면 `skipped` 처리한다.
- 그래프 생성 오류는 네트워크 step만 `failed` 처리한다.
- 보고서에는 소셜 네트워크 섹션 실패로 표시한다.

### build_report_snapshot

책임:

- 성공한 artifact와 실패 정보를 조합한다.
- 보고서 렌더링 payload를 생성한다.
- `report_snapshots`를 저장한다.

성공 기준:

- 영상 메타데이터가 포함된다.
- 댓글, 스크립트, 네트워크 섹션은 성공 또는 실패 상태가 명시된다.
- 생성 시점, 모델 설정, dual vector store 설정, definition corpus version이 포함된다.

실패 처리:

- 메타데이터가 없으면 보고서 snapshot을 만들지 않고 job을 `failed` 처리한다.
- 특정 분석 artifact가 없어도 실패 정보가 있으면 snapshot을 생성한다.

### finalize_job

책임:

- 모든 step 상태를 검토한다.
- job 최종 상태를 결정한다.

판정 규칙:

- `collect_metadata` 실패: `failed`
- `build_report_snapshot` 실패: `failed`
- 필수 artifact가 성공하고 선택 artifact만 실패: `partial_success`
- 모든 실행 대상 step 성공: `succeeded`
- 댓글 비활성화 또는 공개 자막 없음: MVP에서는 `partial_success`

MVP 기본값:

- 댓글 비활성화는 `partial_success`
- 공개 자막 없음은 댓글 분석이 성공했다면 `partial_success`
- 댓글과 자막이 모두 없으면 메타데이터 report만 생성하고 `partial_success`

## 오류 코드

| 코드 | 의미 | 재시도 |
| --- | --- | --- |
| `INVALID_INPUT` | 입력값 형식 오류 | 아니오 |
| `VIDEO_NOT_FOUND` | YouTube 영상 없음 | 아니오 |
| `YOUTUBE_QUOTA_EXCEEDED` | YouTube quota 초과 | 예 |
| `YOUTUBE_RATE_LIMITED` | YouTube rate limit | 예 |
| `YOUTUBE_API_ERROR` | 기타 YouTube API 오류 | 조건부 |
| `COMMENTS_DISABLED` | 댓글 비활성화 | 아니오 |
| `COMMENT_COLLECTION_INCOMPLETE` | 댓글 전체 수집 실패 | 예 |
| `CAPTION_NOT_AVAILABLE` | 공개 자막 없음 | 아니오 |
| `CAPTION_COLLECTION_ERROR` | 자막 수집 오류 | 조건부 |
| `EXAMPLE_VECTOR_STORE_UNAVAILABLE` | 혐오표현 예시 vector store 접근 실패 | 예 |
| `DEFINITION_VECTOR_STORE_UNAVAILABLE` | 혐오표현 정의 문서 vector store 접근 실패 | 예 |
| `RAG_CONTEXT_DEGRADED` | 예시 또는 정의 검색 한쪽만 성공 | 조건부 |
| `LLM_RATE_LIMITED` | LLM rate limit | 예 |
| `LLM_TIMEOUT` | LLM timeout | 예 |
| `LLM_ERROR` | 기타 LLM 오류 | 조건부 |
| `NETWORK_BUILD_ERROR` | 그래프 생성 오류 | 조건부 |
| `REPORT_BUILD_ERROR` | 보고서 snapshot 생성 오류 | 예 |
| `EXPORT_ERROR` | export 생성 오류 | 예 |

## 재시도 정책

### 자동 재시도

worker는 transient failure에 대해 같은 step 안에서 제한된 횟수만 자동 재시도한다.

기본값 후보:

- YouTube API rate limit: exponential backoff, 최대 3회
- YouTube quota exceeded: 자동 반복 재시도하지 않고 retryable failure로 종료
- LLM timeout: exponential backoff, 최대 3회
- LLM rate limit: provider 권장 대기 시간 우선, 최대 3회

### 관리자 재시도

관리자는 API로 실패 job을 재시도할 수 있다.

MVP 기본 정책:

- 같은 job의 실패 step부터 다시 실행한다.
- 이미 성공한 독립 step의 artifact는 삭제하지 않는다.
- 댓글 수집 미완료 상태에서 재시도하면 기존 partial comment snapshot을 폐기하지 않고 새 수집 시도 결과를 같은 job snapshot set에 합친다.
- 단, 사용자가 같은 video ID로 새 분석을 요청하는 경우에는 새 job을 만든다.

## 부분 실패 정책

| 상황 | 처리 |
| --- | --- |
| 댓글 비활성화 | 댓글 수집, 댓글 분석, 네트워크를 건너뛰고 보고서에 사유 표시 |
| 공개 자막 없음 | 스크립트 분석을 건너뛰고 보고서에 사유 표시 |
| 댓글 일부 LLM 실패 | 실패 댓글 수와 ID를 기록하고 보고서에 누락 범위 표시 |
| 스크립트 일부 LLM 실패 | 실패 segment 수와 ID를 기록하고 보고서에 누락 범위 표시 |
| 네트워크 생성 실패 | 네트워크 섹션만 실패 표시 |
| export 실패 | 보고서 snapshot은 유지하고 export만 실패 표시 |

## 진행률 계산

MVP 진행률은 정확한 시간 예측이 아니라 단계 기반으로 제공한다.

기본 가중치 후보:

| step | weight |
| --- | --- |
| `collect_metadata` | 5 |
| `collect_comments` | 25 |
| `collect_transcript` | 10 |
| `analyze_comments` | 35 |
| `analyze_script` | 10 |
| `build_comment_network` | 5 |
| `build_report_snapshot` | 10 |

진행률 표시 정책:

- step 시작 시 누적 weight를 반영한다.
- 댓글 수집과 댓글 분석은 처리 항목 수 기반으로 부분 진행률을 계산할 수 있다.
- 실패 또는 skipped step은 상태와 사유를 함께 표시한다.

## 로그와 이벤트

각 step은 최소 다음 이벤트를 기록한다.

- step started
- step succeeded
- step failed
- retry scheduled
- retry exhausted
- artifact created
- partial failure recorded

로그 정책:

- API 키, 인증정보, 쿠키, 로컬 경로 민감정보는 저장하지 않는다.
- 외부 API 오류 메시지는 저장 전에 마스킹한다.
- 대량 댓글 원문을 operation log에 저장하지 않는다.

## Export job

보고서 내보내기는 분석 job과 별도 export 작업으로 볼 수 있다.

MVP 기본:

- HTML export와 Excel export를 지원한다.
- PDF export는 MVP 이후로 미룬다.
- export는 `report_snapshots`를 입력으로 사용한다.
- export 실패는 원본 report snapshot을 무효화하지 않는다.

## 구현 세부 확인 사항

다음 항목은 구현 중 세부 수치를 정한다.

- YouTube API와 LLM 호출의 backoff 간격
- 댓글 분석 batch size
- worker polling interval
- 진행률 표시의 세부 갱신 주기

MVP 문서 기본값은 PostgreSQL polling, 같은 job 실패 step 재시도, 최종 상태 `partial_success`다.

## 검증 기준

이 pipeline은 다음 조건을 만족해야 한다.

- 사용자는 분석 요청 직후 job ID를 받는다.
- worker가 단계별 상태를 기록한다.
- 댓글 전체 수집이 완료되지 않으면 댓글 분석 성공으로 표시하지 않는다.
- 공개 자막 없음이 댓글 분석을 막지 않는다.
- 네트워크 생성 실패가 댓글 분석 결과를 무효화하지 않는다.
- 보고서 snapshot은 성공 artifact와 실패 정보를 함께 담는다.
