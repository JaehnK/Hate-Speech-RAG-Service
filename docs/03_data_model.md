# 데이터 모델

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.2 |
| 작성일시 | 2026-07-09 03:04:53 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 PostgreSQL 데이터 모델을 정의한다.

이 문서는 HLD의 저장 경계를 테이블 수준으로 풀어내며, 이후 job pipeline, API 명세, 백엔드 설계의 기준으로 사용한다.

## 설계 원칙

- PostgreSQL을 기준 저장소로 사용한다.
- 동일 영상이 다시 분석되면 새 job과 새 snapshot을 만든다.
- 원천 수집 데이터와 분석 결과를 같은 테이블에 섞지 않는다.
- 보고서는 특정 analysis run의 snapshot으로 고정한다.
- 댓글과 대댓글은 수집 시점의 상태를 보존한다.
- 댓글 분석, 스크립트 분석, 네트워크 생성은 독립 artifact로 저장한다.
- RAG 근거는 혐오표현 예시와 혐오표현 정의 문서 출처를 분리해 저장한다.
- 민감정보 원문은 저장하지 않는다.
- 기존 `legacy/YouTubeHateSpeech/`, `legacy/hateSpeechRAG/`의 테이블은 참조 대상으로만 보고, MVP 서비스 스키마는 새로 정규화한다.

## 공통 규칙

- 기본 PK는 `uuid`를 사용한다.
- YouTube 원천 ID는 `youtube_*_id` 형태의 `text` 컬럼으로 보존한다.
- 시각 컬럼은 `timestamptz`를 사용한다.
- 외부 API 원문 응답은 필요한 경우 `raw_payload jsonb`에 저장한다.
- 배열형 분류값은 `text[]` 또는 `jsonb`로 저장한다.
- 상태값은 애플리케이션 enum으로 먼저 관리하고, DB enum 도입은 구현 단계에서 결정한다.
- 대량 조회가 필요한 테이블은 `job_id`, `analysis_run_id`, `youtube_video_id` 중심으로 인덱싱한다.

## ERD 개요

```text
analysis_jobs
  -> job_steps
  -> video_metadata_snapshots
  -> comment_snapshots
  -> transcript_snapshots
      -> transcript_segments
  -> analysis_runs
      -> comment_analysis_results
      -> script_analysis_results
      -> comment_networks
          -> comment_network_nodes
          -> comment_network_edges
      -> report_snapshots
          -> report_exports
  -> operation_logs

channels
  <- video_metadata_snapshots

secret_references
api_quota_events
```

## 핵심 테이블

### analysis_jobs

분석 요청 단위를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | job ID |
| input_value | text | 사용자가 입력한 URL 또는 video ID |
| youtube_video_id | text | 추출된 YouTube video ID |
| status | text | `pending`, `running`, `partial_success`, `succeeded`, `failed`, `canceled` |
| requested_by | text nullable | MVP에서는 익명 또는 내부 식별자 |
| request_options | jsonb | 요청 옵션. MVP에서는 대부분 기본값 |
| error_summary | jsonb nullable | 전체 실패 또는 부분 실패 요약 |
| created_at | timestamptz | 생성 시각 |
| started_at | timestamptz nullable | 시작 시각 |
| finished_at | timestamptz nullable | 종료 시각 |

인덱스:

- `(status, created_at)`
- `(youtube_video_id, created_at)`

정책:

- 같은 `youtube_video_id`의 기존 job이 있어도 새 row를 만든다.
- MVP에서는 deduplication을 하지 않는다.

### job_steps

job의 단계별 상태를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | step ID |
| job_id | uuid FK | `analysis_jobs.id` |
| step_key | text | 단계 이름 |
| status | text | `pending`, `running`, `succeeded`, `failed`, `skipped` |
| attempt_count | int | 실행 시도 횟수 |
| is_required | boolean | 전체 성공 판단에 필수인지 여부 |
| error_code | text nullable | 실패 코드 |
| error_message | text nullable | 마스킹된 실패 메시지 |
| metrics | jsonb | 단계별 수량, 소요 시간, 외부 호출 수 |
| items_total | int nullable | item 단위 분석의 전체 수 |
| items_completed | int | 완료 item 수 |
| items_succeeded | int | 성공 item 수 |
| items_failed | int | 실패 item 수 |
| heartbeat_at | timestamptz nullable | worker 생존 및 진행 확인 시각 |
| started_at | timestamptz nullable | 시작 시각 |
| finished_at | timestamptz nullable | 종료 시각 |

인덱스:

- `(job_id, step_key)`
- `(status, started_at)`

### channels

YouTube 채널의 최신 확인 정보를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| youtube_channel_id | text PK | YouTube channel ID |
| title | text nullable | 채널명 |
| custom_url | text nullable | custom URL |
| country | text nullable | 국가 |
| description | text nullable | 설명 |
| subscriber_count | bigint nullable | 구독자 수 |
| video_count | bigint nullable | 영상 수 |
| view_count | bigint nullable | 조회 수 |
| thumbnail_url | text nullable | 대표 썸네일 |
| raw_payload | jsonb nullable | API 원문 응답 |
| last_collected_at | timestamptz | 마지막 수집 시각 |

정책:

- 채널은 분석 snapshot이 아니라 최신 참조 정보로 관리한다.
- 보고서 재현에는 `video_metadata_snapshots`의 채널 필드를 우선 사용한다.

### video_metadata_snapshots

영상 메타데이터의 수집 시점 snapshot을 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | snapshot ID |
| job_id | uuid FK | `analysis_jobs.id` |
| youtube_video_id | text | YouTube video ID |
| youtube_channel_id | text nullable | YouTube channel ID |
| title | text nullable | 영상 제목 |
| channel_title | text nullable | 채널명 |
| published_at | timestamptz nullable | YouTube 게시 시각 |
| category_id | text nullable | YouTube category ID |
| duration_seconds | int nullable | 영상 길이 |
| view_count | bigint nullable | 조회 수 |
| like_count | bigint nullable | 좋아요 수 |
| comment_count | bigint nullable | API 기준 댓글 수 |
| made_for_kids | boolean nullable | 아동용 여부 |
| tags | text[] nullable | 태그 |
| description | text nullable | 영상 설명 |
| thumbnail_url | text nullable | 썸네일 |
| raw_payload | jsonb nullable | API 원문 응답 |
| collected_at | timestamptz | 수집 시각 |

인덱스:

- `(job_id)`
- `(youtube_video_id, collected_at)`
- `(youtube_channel_id)`

정책:

- `youtube_video_id`를 PK로 쓰지 않는다. 같은 영상의 반복 분석 snapshot을 보존해야 하기 때문이다.

### comment_snapshots

댓글과 대댓글의 수집 시점 snapshot을 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | 내부 댓글 snapshot ID |
| job_id | uuid FK | `analysis_jobs.id` |
| youtube_video_id | text | YouTube video ID |
| youtube_comment_id | text | YouTube comment ID |
| parent_youtube_comment_id | text nullable | 대댓글의 부모 댓글 ID |
| parent_comment_snapshot_id | uuid nullable | 같은 job 안의 부모 댓글 snapshot |
| is_reply | boolean | 대댓글 여부 |
| reply_depth | int | MVP에서는 0 또는 1 |
| author_display_name | text nullable | 작성자 표시명 |
| author_channel_id | text nullable | 작성자 채널 ID |
| text_display | text nullable | YouTube display text |
| text_original | text nullable | 원문 텍스트 |
| like_count | bigint nullable | 좋아요 수 |
| reply_count | bigint nullable | 최상위 댓글의 답글 수 |
| published_at | timestamptz nullable | 작성 시각 |
| updated_at | timestamptz nullable | 수정 시각 |
| raw_payload | jsonb nullable | API 원문 응답 |
| collected_at | timestamptz | 수집 시각 |

제약:

- `UNIQUE (job_id, youtube_comment_id)`

인덱스:

- `(job_id, is_reply)`
- `(job_id, parent_youtube_comment_id)`
- `(youtube_video_id, collected_at)`
- `(author_channel_id)`

정책:

- 댓글 분석 결과는 이 테이블에 직접 쓰지 않는다.
- 같은 YouTube 댓글이라도 다른 job에서 다시 수집되면 별도 snapshot row를 만든다.

### transcript_snapshots

공개 자막 수집 결과의 상위 정보를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | transcript snapshot ID |
| job_id | uuid FK | `analysis_jobs.id` |
| youtube_video_id | text | YouTube video ID |
| language_code | text nullable | 자막 언어 |
| is_auto_generated | boolean nullable | 자동 생성 자막 여부 |
| source_type | text | `public_caption` |
| source_uri | text nullable | 저장된 자막 파일 경로 |
| raw_text | text nullable | 정규화된 전체 자막 텍스트 |
| raw_payload | jsonb nullable | 수집 도구의 결과 정보 |
| status | text | `succeeded`, `failed`, `not_available` |
| error_code | text nullable | 실패 코드 |
| collected_at | timestamptz | 수집 시각 |

인덱스:

- `(job_id)`
- `(youtube_video_id, collected_at)`

정책:

- 외부 자막 업로드는 MVP에서 저장하지 않는다.

### transcript_segments

스크립트 분석 단위로 사용할 자막 세그먼트를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | segment ID |
| transcript_snapshot_id | uuid FK | `transcript_snapshots.id` |
| segment_index | int | 세그먼트 순서 |
| start_seconds | numeric nullable | 시작 시각 |
| end_seconds | numeric nullable | 종료 시각 |
| text | text | 세그먼트 텍스트 |
| token_count | int nullable | 토큰 수 |
| created_at | timestamptz | 생성 시각 |

제약:

- `UNIQUE (transcript_snapshot_id, segment_index)`

인덱스:

- `(transcript_snapshot_id, segment_index)`

## 분석 테이블

### analysis_runs

분석 실행 단위를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | analysis run ID |
| job_id | uuid FK | `analysis_jobs.id` |
| youtube_video_id | text | YouTube video ID |
| status | text | `running`, `partial_success`, `succeeded`, `failed` |
| llm_provider | text | LLM provider |
| llm_model | text | LLM model |
| embedding_provider | text | embedding provider |
| embedding_model | text | embedding model |
| example_vector_collection | text | 혐오표현 예시 Chroma collection |
| definition_vector_collection | text | 혐오표현 정의 문서 Chroma collection |
| definition_corpus_version | text nullable | 정의 문서 corpus version |
| retriever_config | jsonb | 예시/정의 retriever type, k 등 |
| prompt_versions | jsonb | 댓글/스크립트 prompt version |
| started_at | timestamptz | 시작 시각 |
| finished_at | timestamptz nullable | 종료 시각 |

인덱스:

- `(job_id)`
- `(youtube_video_id, started_at)`

정책:

- 동일 job 안에서는 MVP 기준 하나의 analysis run을 둔다.
- 이후 사람이 검수한 재분석이 들어오면 같은 job 안에 여러 analysis run을 둘 수 있다.

### comment_analysis_results

댓글과 대댓글의 혐오표현 분석 결과를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | result ID |
| analysis_run_id | uuid FK | `analysis_runs.id` |
| comment_snapshot_id | uuid FK | `comment_snapshots.id` |
| status | text | `succeeded`, `failed`, `skipped` |
| is_hate_speech | boolean nullable | 혐오표현 여부 |
| categories | text[] nullable | 혐오표현 카테고리 |
| target_group | text nullable | 대상 집단 |
| hate_type | text nullable | 혐오 유형 |
| evidence_strength | numeric nullable | 증거 강도 |
| reasoning | text nullable | 분류 근거 |
| similar_cases_used | jsonb nullable | RAG 유사 예시 |
| definition_docs_used | jsonb nullable | RAG 정의 문서 근거 |
| rag_context_status | text nullable | `complete`, `example_only`, `definition_only`, `unavailable` |
| prompt_version | text nullable | prompt version |
| model_name | text nullable | 모델명 |
| raw_response | jsonb nullable | LLM 응답 원문 |
| error_code | text nullable | 실패 코드 |
| error_message | text nullable | 마스킹된 실패 메시지 |
| created_at | timestamptz | 생성 시각 |

제약:

- `UNIQUE (analysis_run_id, comment_snapshot_id)`

인덱스:

- `(analysis_run_id, status)`
- `(analysis_run_id, is_hate_speech)`
- `(comment_snapshot_id)`

### script_analysis_results

스크립트 세그먼트의 혐오표현 분석 결과를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | result ID |
| analysis_run_id | uuid FK | `analysis_runs.id` |
| transcript_segment_id | uuid FK | `transcript_segments.id` |
| status | text | `succeeded`, `failed`, `skipped` |
| is_hate_speech | boolean nullable | 혐오표현 여부 |
| categories | text[] nullable | 혐오표현 카테고리 |
| target_group | text nullable | 대상 집단 |
| hate_type | text nullable | 혐오 유형 |
| evidence_strength | numeric nullable | 증거 강도 |
| reasoning | text nullable | 분류 근거 |
| similar_cases_used | jsonb nullable | RAG 유사 예시 |
| definition_docs_used | jsonb nullable | RAG 정의 문서 근거 |
| rag_context_status | text nullable | `complete`, `example_only`, `definition_only`, `unavailable` |
| prompt_version | text nullable | prompt version |
| model_name | text nullable | 모델명 |
| raw_response | jsonb nullable | LLM 응답 원문 |
| error_code | text nullable | 실패 코드 |
| error_message | text nullable | 마스킹된 실패 메시지 |
| created_at | timestamptz | 생성 시각 |

제약:

- `UNIQUE (analysis_run_id, transcript_segment_id)`

인덱스:

- `(analysis_run_id, status)`
- `(analysis_run_id, is_hate_speech)`
- `(transcript_segment_id)`

## 네트워크 테이블

### comment_networks

댓글과 대댓글 기반 소셜 네트워크 artifact의 상위 정보를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | network ID |
| analysis_run_id | uuid FK | `analysis_runs.id` |
| graph_type | text | `comment_reply_author_network` |
| directed | boolean | 방향 그래프 여부 |
| status | text | `succeeded`, `failed`, `skipped` |
| summary | jsonb | 노드 수, 엣지 수, 주요 지표 |
| layout_payload | jsonb nullable | 보고서 렌더링용 좌표 또는 옵션 |
| error_code | text nullable | 실패 코드 |
| error_message | text nullable | 마스킹된 실패 메시지 |
| created_at | timestamptz | 생성 시각 |

인덱스:

- `(analysis_run_id)`
- `(status, created_at)`

### comment_network_nodes

소셜 네트워크의 노드를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | node row ID |
| network_id | uuid FK | `comment_networks.id` |
| node_key | text | 그래프 내부 노드 ID |
| node_type | text | MVP에서는 `author` |
| label | text nullable | 표시명 |
| author_channel_id | text nullable | 작성자 채널 ID |
| comment_count | int | 작성 댓글 수 |
| hate_speech_count | int | 혐오표현 댓글 수 |
| hate_speech_ratio | numeric | 혐오표현 비율 |
| metrics | jsonb | degree, in_degree, out_degree 등 |
| attributes | jsonb | 기타 렌더링 속성 |

제약:

- `UNIQUE (network_id, node_key)`

인덱스:

- `(network_id)`
- `(author_channel_id)`

정책:

- MVP에서는 `author_channel_id`를 `node_key`의 우선값으로 사용한다.
- `author_channel_id`가 없으면 같은 job 안에서 재현 가능한 내부 key를 사용한다.

### comment_network_edges

소셜 네트워크의 엣지를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | edge row ID |
| network_id | uuid FK | `comment_networks.id` |
| source_node_key | text | 대댓글 작성자 노드 |
| target_node_key | text | 부모 댓글 작성자 노드 |
| edge_type | text | `reply_to` |
| weight | numeric | 관계 가중치 |
| comment_snapshot_id | uuid nullable | 대댓글 snapshot |
| parent_comment_snapshot_id | uuid nullable | 부모 댓글 snapshot |
| is_hate_speech | boolean nullable | 대댓글 혐오표현 여부 |
| attributes | jsonb | 기타 속성 |

인덱스:

- `(network_id)`
- `(network_id, source_node_key)`
- `(network_id, target_node_key)`

정책:

- MVP 기본값은 개별 대댓글 단위 edge 저장이다.
- 저장된 개별 edge의 기본 `weight`는 1이다.
- 작성자 쌍 집계 weight는 보고서 조회 또는 network summary 생성 시 계산한다.

## 보고서 테이블

### report_snapshots

보고서 생성 시점의 고정 snapshot을 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | report snapshot ID |
| analysis_run_id | uuid FK | `analysis_runs.id` |
| status | text | `succeeded`, `partial_success`, `failed` |
| title | text | 보고서 제목 |
| payload | jsonb | 보고서 렌더링용 정규화 payload |
| payload_uri | text nullable | payload를 파일로 저장할 경우 경로 |
| html_uri | text nullable | 렌더링된 HTML 저장 경로 |
| source_counts | jsonb | 댓글 수, 세그먼트 수, 실패 수 |
| failure_summary | jsonb nullable | 부분 실패 요약 |
| created_at | timestamptz | 생성 시각 |

인덱스:

- `(analysis_run_id)`
- `(status, created_at)`

정책:

- report snapshot은 생성 이후 수정하지 않는다.
- 수정이 필요하면 새 snapshot을 생성한다.

### report_exports

보고서 내보내기 파일을 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | export ID |
| report_snapshot_id | uuid FK | `report_snapshots.id` |
| format | text | `html`, `xlsx` |
| status | text | `pending`, `running`, `succeeded`, `failed` |
| file_uri | text nullable | 저장 경로 |
| file_size_bytes | bigint nullable | 파일 크기 |
| checksum | text nullable | 파일 checksum |
| error_code | text nullable | 실패 코드 |
| error_message | text nullable | 마스킹된 실패 메시지 |
| created_at | timestamptz | 생성 시각 |
| finished_at | timestamptz nullable | 종료 시각 |

인덱스:

- `(report_snapshot_id)`
- `(status, created_at)`

## 운영 테이블

### operation_logs

서비스 운영 로그를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | log ID |
| job_id | uuid nullable | 관련 job |
| job_step_id | uuid nullable | 관련 step |
| analysis_run_id | uuid nullable | 관련 analysis run |
| level | text | `debug`, `info`, `warning`, `error` |
| event_type | text | 이벤트 유형 |
| message | text | 마스킹된 메시지 |
| metadata | jsonb | 추가 정보 |
| created_at | timestamptz | 생성 시각 |

인덱스:

- `(job_id, created_at)`
- `(level, created_at)`
- `(event_type, created_at)`

### secret_references

API 키와 같은 민감정보의 등록 상태만 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | secret reference ID |
| secret_key | text | `youtube_api_key`, `llm_api_key` 등 |
| provider | text | 환경변수, secret manager 등 |
| is_configured | boolean | 등록 여부 |
| last_used_at | timestamptz nullable | 마지막 사용 시각 |
| last_error_code | text nullable | 최근 오류 코드 |
| updated_at | timestamptz | 갱신 시각 |

제약:

- `UNIQUE (secret_key, provider)`

정책:

- secret 원문 값은 저장하지 않는다.

### api_quota_events

YouTube API quota 관련 이벤트를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | quota event ID |
| job_id | uuid nullable | 관련 job |
| provider | text | `youtube` |
| operation | text | `videos.list`, `commentThreads.list`, `comments.list` 등 |
| quota_cost | int nullable | 추정 quota cost |
| status | text | `used`, `quota_exceeded`, `rate_limited`, `failed` |
| error_code | text nullable | 오류 코드 |
| metadata | jsonb | 추가 정보 |
| created_at | timestamptz | 생성 시각 |

인덱스:

- `(provider, created_at)`
- `(job_id, created_at)`
- `(status, created_at)`

## 삭제와 보존 정책

MVP 기본 보존 정책:

- job, 수집 snapshot, 분석 결과, 보고서 snapshot은 삭제하지 않는다.
- export 파일은 재생성 가능하므로 보존 기간을 둘 수 있다.
- 운영 로그는 기간 기반 보존 정책을 둘 수 있다.
- 민감정보 원문은 저장하지 않으므로 삭제 대상이 아니다.

삭제 API는 MVP 범위에 포함하지 않는다. 운영 중 수동 정리가 필요하면 별도 관리 명령으로 처리한다.

## 기존 원천 스키마와의 차이

기존 원천 코드의 특징:

- `videos.video_id`와 `comments.comment_id`를 전역 PK로 사용한다.
- `comments` 테이블에 혐오표현 분석 컬럼이 직접 추가되어 있다.
- `scriptresult`는 스크립트 분석 결과만 별도 저장한다.
- 일부 컬럼 타입과 실제 저장값이 맞지 않을 수 있다.

MVP 서비스 스키마의 변경 방향:

- 같은 영상과 댓글의 반복 분석을 보존하기 위해 snapshot 테이블을 사용한다.
- 댓글 원천 데이터와 댓글 분석 결과를 분리한다.
- 스크립트 원천 세그먼트와 스크립트 분석 결과를 분리한다.
- 네트워크 artifact와 보고서 snapshot을 명시적인 1급 데이터로 둔다.

## 보류 사항

다음 항목은 구현 직전 또는 배포 문서에서 확정한다.

- PostgreSQL enum을 사용할지, text + 애플리케이션 enum으로 유지할지
- report `payload`를 DB에 저장할지 파일 저장소에 저장할지
- export 파일의 기본 보존 기간

## 검증 기준

이 데이터 모델은 다음 조건을 만족해야 한다.

- 동일 영상 재분석 시 이전 결과가 덮어써지지 않는다.
- 댓글 전체 분석 결과를 항목별로 추적할 수 있다.
- 스크립트 없음, 댓글 비활성화, 네트워크 생성 실패를 독립적으로 표현할 수 있다.
- 보고서 snapshot이 특정 analysis run에 고정된다.
- 민감정보 원문이 저장되지 않는다.
