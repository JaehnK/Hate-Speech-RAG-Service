# API 명세

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.0 |
| 작성일시 | 2026-07-16 22:00:00 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 FastAPI endpoint와 request/response schema를 정의한다.

이 문서는 구현자가 API 표면을 과하게 넓히지 않고, job 기반 처리와 보고서 snapshot 조회를 일관되게 제공하도록 하는 기준이다.

## API 설계 원칙

- 모든 장시간 작업은 job 또는 export 작업으로 생성한다.
- 분석 요청 API는 즉시 `202 Accepted`와 job ID를 반환한다.
- 동일 영상 요청도 항상 새 job을 생성한다.
- 보고서 JSON은 snapshot 기준으로 반환한다.
- 댓글, 스크립트, 네트워크 상세 목록은 pagination을 사용한다.
- 분석 상세 응답은 유사 예시 근거와 정의 문서 근거를 구분해 제공한다.
- 관리자 기능은 MVP에서 웹 화면 없이 API로만 제공한다.
- API 키, 쿠키, secret 원문은 응답에 포함하지 않는다.
- 오류 응답은 공통 형식을 사용한다.
- 분석 job 생성, 본인 job/report 조회, API 키 관리는 로그인 세션 쿠키 인증을 요구한다.
- 공개 샘플 report 조회는 인증 없이 허용한다.
- 사용자가 소유하지 않은 job/report에 대한 요청은 `403` 또는 `404`로 거부한다.

## 공통 규칙

### Base URL

개발 기본값:

```text
http://localhost:8000
```

### Content Type

요청과 응답의 기본 형식:

```text
Content-Type: application/json
```

파일 다운로드 응답은 파일 형식에 맞는 content type을 사용한다.

### 인증

MVP 기본값:

- 분석 이용자 API는 Google OAuth 로그인 이후 발급되는 세션 쿠키로 인증한다.
- 세션 쿠키는 `HttpOnly`, 운영 환경에서 `Secure`, `SameSite=Lax` 속성을 사용한다. 상세 사양은 `30_auth_oauth_byok.md`를 따른다.
- 공개 샘플 report 조회 API(`is_public_sample = true`)는 인증 없이 허용한다.
- 인증이 필요한 API에 세션 쿠키 없이 요청하면 `401`을 반환한다.
- 관리자 API는 계속 `X-Admin-Token` 헤더를 사용하며, 사용자 세션 인증과는 별개 체계로 유지한다.

세션 쿠키 요청 예시(브라우저가 자동으로 첨부):

```http
Cookie: hsr_session=********
```

관리자 요청 예시:

```http
X-Admin-Token: ********
```

### 공통 오류 응답

```json
{
  "error": {
    "code": "VIDEO_NOT_FOUND",
    "message": "YouTube video was not found.",
    "details": {
      "youtube_video_id": "abc123"
    }
  },
  "request_id": "req_01H00000000000000000000000"
}
```

공통 HTTP status:

| Status | 의미 |
| --- | --- |
| `400` | 입력값 오류 |
| `401` | 인증 필요 |
| `403` | 권한 없음 |
| `404` | 리소스 없음 |
| `409` | 현재 상태에서 수행 불가 |
| `422` | schema 검증 실패 |
| `500` | 서버 오류 |
| `503` | 외부 의존성 또는 설정 오류 |

### Pagination

목록 API는 기본적으로 cursor pagination을 사용한다.

요청 query:

| 이름 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| limit | int | 50 | 최대 200 |
| cursor | string nullable | null | 다음 페이지 cursor |

응답 형식:

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false
}
```

## 인증 API

### GET /api/auth/google/login

Google OAuth 동의 화면으로 리디렉션한다.

응답:

```http
302 Found
Location: https://accounts.google.com/o/oauth2/v2/auth?...
```

정책:

- 이미 로그인된 세션이 있으면 다시 로그인하지 않고 원래 이동하려던 경로로 리디렉션한다.

### GET /api/auth/google/callback

Google이 authorization code와 함께 리디렉션하는 콜백 경로다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| code | string | Google이 발급한 authorization code |
| state | string | CSRF 방지용 state 값 |

성공 응답:

```http
302 Found
Set-Cookie: hsr_session=********; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1209600
Location: /
```

정책:

- `state` 값이 로그인 시작 시 발급한 값과 다르면 로그인을 완료하지 않고 오류로 처리한다.
- 최초 로그인이면 `users` row를 생성하고, 기존 사용자면 `last_login_at`을 갱신한다.
- 세션 발급, code-token 교환, ID token 검증의 상세 흐름은 `30_auth_oauth_byok.md`를 따른다.

### GET /api/auth/session

현재 로그인 상태와 사용자 정보를 조회한다.

성공 응답:

```json
{
  "user_id": "8f14e45f-ceea-467e-9a95-4c5ea2b1a123",
  "email": "user@example.com",
  "display_name": "홍길동",
  "avatar_url": "https://...",
  "api_keys_registered": {
    "anthropic": true,
    "upstage": false
  }
}
```

미인증 응답:

```http
401 Unauthorized
```

### POST /api/auth/logout

현재 세션을 무효화하고 쿠키를 만료시킨다.

성공 응답:

```http
204 No Content
Set-Cookie: hsr_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0
```

## 사용자 API 키 API

이 절의 모든 endpoint는 로그인 세션 쿠키 인증을 요구한다.

### GET /api/me/api-keys

로그인한 사용자가 등록한 API 키 목록을 마스킹된 형태로 조회한다.

성공 응답:

```json
{
  "items": [
    {
      "provider": "anthropic",
      "key_fingerprint": "sk-ant-...a1b2",
      "is_valid": true,
      "last_validated_at": "2026-07-16T10:00:00+09:00"
    }
  ]
}
```

정책:

- API 키 원문은 어떤 상황에서도 응답에 포함하지 않는다.

### PUT /api/me/api-keys/{provider}

지정한 provider(`anthropic` 또는 `upstage`)의 API 키를 등록하거나 교체한다.

요청:

```json
{
  "api_key": "sk-ant-xxxxxxxxxxxxxxxx"
}
```

성공 응답:

```json
{
  "provider": "anthropic",
  "key_fingerprint": "sk-ant-...a1b2",
  "is_valid": true,
  "last_validated_at": "2026-07-16T10:00:00+09:00"
}
```

정책:

- 저장 전에 provider에 가벼운 검증 호출을 수행한다. 검증에 실패하면 키를 저장하지 않고 `422`를 반환한다.
- 기존에 등록된 같은 provider의 키가 있으면 대체한다.

### DELETE /api/me/api-keys/{provider}

지정한 provider의 등록된 키를 삭제한다.

성공 응답:

```http
204 No Content
```

정책:

- 삭제 이후 해당 provider 키가 필요한 새 분석 job 생성은 `422`로 거부한다.
- 이미 실행 중이거나 완료된 job에는 영향을 주지 않는다.

## 분석 Job API

### POST /api/analysis-jobs

단일 YouTube 영상 분석 job을 생성한다.

요청:

```json
{
  "input_value": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| input_value | string | 예 | YouTube URL 또는 video ID |

MVP에서 허용하지 않는 필드:

- `external_caption_file`
- `comment_limit`
- `reuse_previous_result`
- `multi_video_file`

성공 응답:

```http
202 Accepted
```

```json
{
  "job_id": "0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
  "user_id": "8f14e45f-ceea-467e-9a95-4c5ea2b1a123",
  "youtube_video_id": "VIDEO_ID",
  "status": "pending",
  "status_url": "/api/analysis-jobs/0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
  "created_at": "2026-07-08T07:05:36+09:00"
}
```

정책:

- 같은 `youtube_video_id`의 기존 job이 있어도 새 job을 생성한다.
- 입력값에서 video ID를 추출할 수 없으면 `400`을 반환한다.
- 로그인 세션이 없으면 job을 생성하지 않고 `401`을 반환한다.
- 요청자가 Anthropic 또는 Upstage API 키를 등록하지 않았거나, 등록된 키의 마지막 검증이 `is_valid = false`이면 job을 생성하지 않고 `422`를 반환한다. 오류 `code`는 `API_KEY_NOT_CONFIGURED` 또는 `API_KEY_INVALID`를 사용한다.
- 생성된 job의 `user_id`는 요청자의 세션 `user_id`로 채운다.

### GET /api/analysis-jobs/{job_id}

job 상태와 단계별 진행 상황을 조회한다.

성공 응답:

```json
{
  "job_id": "0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
  "youtube_video_id": "VIDEO_ID",
  "status": "running",
  "progress": {
    "percent": 45,
    "current_step": "analyze_comments"
  },
  "steps": [
    {
      "step_key": "collect_metadata",
      "status": "succeeded",
      "attempt_count": 1,
      "started_at": "2026-07-08T07:06:00+09:00",
      "finished_at": "2026-07-08T07:06:03+09:00",
      "metrics": {
        "video_count": 1
      },
      "item_progress": null,
      "error": null
    },
    {
      "step_key": "analyze_comments",
      "status": "running",
      "attempt_count": 1,
      "started_at": "2026-07-08T07:06:10+09:00",
      "finished_at": null,
      "metrics": {},
      "item_progress": {
        "total": 1200,
        "completed": 430,
        "succeeded": 426,
        "failed": 4,
        "percent": 36
      },
      "error": null
    }
  ],
  "summary": {
    "comments_collected": 1200,
    "comments_analyzed": 430,
    "script_segments_analyzed": 0,
    "failed_items": 0
  },
  "links": {
    "report_api": null,
    "report_page": null
  },
  "created_at": "2026-07-08T07:05:36+09:00",
  "started_at": "2026-07-08T07:06:00+09:00",
  "finished_at": null
}
```

`item_progress`는 item 단위 분석 단계에서만 제공한다. counter는 별도 transaction의 원자적 증가로 저장하므로 장시간 RAG transaction이 완료되기 전에도 조회할 수 있고, 향후 같은 step 내부의 병렬 item 처리에서도 값이 역행하지 않는다.

인증과 소유권:

- 로그인 세션이 없으면 `401`을 반환한다.
- 요청자의 `user_id`가 job의 `user_id`와 다르면 `403`을 반환한다.

상태별 링크:

- 보고서 snapshot이 생성되기 전에는 `report_api`, `report_page`가 `null`이다.
- 보고서 snapshot 생성 이후에는 각각 `/api/reports/{report_id}`, `/reports/{report_id}`를 반환한다.

### GET /api/analysis-jobs/{job_id}/steps

job step 목록만 조회한다.

성공 응답:

```json
{
  "items": [
    {
      "step_key": "collect_comments",
      "status": "running",
      "attempt_count": 1,
      "metrics": {
        "pages_collected": 12,
        "comments_collected": 1180
      },
      "error": null
    }
  ]
}
```

이 endpoint는 상태 화면에서 polling할 때 사용한다.

## 내 리소스 API

이 절의 모든 endpoint는 로그인 세션 쿠키 인증을 요구하며, 요청자 본인 소유의 항목만 반환한다.

### GET /api/me/jobs

로그인한 사용자가 생성한 job 목록을 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| status | string nullable | job 상태 필터 |
| limit | int | 페이지 크기 |
| cursor | string nullable | 다음 페이지 cursor |

성공 응답 형식은 `GET /api/admin/jobs`의 `items`와 동일한 job 요약 구조를 사용하되, 요청자 본인 소유 job만 포함한다.

### GET /api/me/reports

로그인한 사용자가 소유한 report 목록을 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| limit | int | 페이지 크기 |
| cursor | string nullable | 다음 페이지 cursor |

성공 응답:

```json
{
  "items": [
    {
      "report_id": "176ff06e-e91c-402b-ae5a-bd3a8dc977c6",
      "youtube_video_id": "VIDEO_ID",
      "status": "succeeded",
      "created_at": "2026-07-08T07:20:00+09:00"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

## 보고서 API

이 절의 `report_id` 기반 endpoint(`comments`, `script-segments`, `network`, `exports` 포함)는 모두 `GET /api/reports/{report_id}`와 같은 인증/소유권 규칙을 따른다: `is_public_sample = true`이면 인증 없이 허용하고, 그 외에는 소유자 본인만 접근할 수 있다.

### GET /api/reports/public

로그인 없이 열람 가능한 공개 샘플 report 목록을 조회한다.

성공 응답 형식은 `GET /api/me/reports`와 동일하다. `is_public_sample = true`인 report만 포함한다.

정책:

- 인증 없이 호출할 수 있다.
- 이 endpoint는 새 분석 job을 생성하지 않는다.

### GET /api/reports/{report_id}

보고서 snapshot의 요약 JSON을 조회한다.

성공 응답:

```json
{
  "report_id": "176ff06e-e91c-402b-ae5a-bd3a8dc977c6",
  "analysis_run_id": "e3ac77cf-08e1-4d1a-87af-57be69c28712",
  "youtube_video_id": "VIDEO_ID",
  "status": "succeeded",
  "created_at": "2026-07-08T07:20:00+09:00",
  "video": {
    "title": "영상 제목",
    "channel_title": "채널명",
    "published_at": "2026-07-01T10:00:00+09:00",
    "view_count": 100000,
    "comment_count": 1200
  },
  "collection_summary": {
    "comments_collected": 1200,
    "replies_collected": 350,
    "transcript_available": true
  },
  "comment_analysis_summary": {
    "total": 1200,
    "succeeded": 1195,
    "failed": 5,
    "hate_speech_count": 80,
    "category_distribution": {
      "욕설": 40,
      "차별": 20
    }
  },
  "script_analysis_summary": {
    "total": 90,
    "succeeded": 90,
    "failed": 0,
    "hate_speech_count": 3
  },
  "network_summary": {
    "status": "succeeded",
    "node_count": 300,
    "edge_count": 350
  },
  "failure_summary": [],
  "links": {
    "comments": "/api/reports/176ff06e-e91c-402b-ae5a-bd3a8dc977c6/comments",
    "script_segments": "/api/reports/176ff06e-e91c-402b-ae5a-bd3a8dc977c6/script-segments",
    "network": "/api/reports/176ff06e-e91c-402b-ae5a-bd3a8dc977c6/network",
    "page": "/reports/176ff06e-e91c-402b-ae5a-bd3a8dc977c6"
  }
}
```

정책:

- 이 응답은 보고서 전체 요약과 대표 link를 반환한다.
- 댓글 전체 목록은 포함하지 않는다.
- `is_public_sample = true`인 report는 인증 없이 조회할 수 있다.
- 그 외 report는 로그인 세션이 필요하며, 요청자의 `user_id`가 report의 `owner_user_id`와 다르면 `403`(비인증 상태면 `401`)을 반환한다.

### GET /reports/{report_id}

웹 보고서 페이지를 렌더링한다.

응답:

```http
200 OK
Content-Type: text/html
```

정책:

- MVP에서는 FastAPI template 렌더링으로 시작한다.
- React 등 별도 frontend 분리는 MVP 이후로 미룬다.
- 페이지는 `report_snapshots.payload`를 기준으로 렌더링한다.

### GET /api/reports/{report_id}/comments

보고서에 포함된 댓글 분석 결과 목록을 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| limit | int | 페이지 크기 |
| cursor | int | 다음 페이지 offset cursor |
| is_hate_speech | boolean nullable | 혐오표현 여부 필터 |
| status | string nullable | `succeeded`, `failed`, `skipped` |
| category | string nullable | 카테고리 필터 |
| author_channel_id | string nullable | 작성자 채널 필터 |
| sort | string | `collected_at`(기본) 또는 `like_count`(좋아요 내림차순) |

성공 응답:

```json
{
  "items": [
    {
      "comment_snapshot_id": "a72e2f83-4f4d-4d7f-a237-85bb3cc9fe77",
      "youtube_comment_id": "COMMENT_ID",
      "is_reply": false,
      "parent_youtube_comment_id": null,
      "author_display_name": "작성자",
      "author_channel_id": "CHANNEL_ID",
      "text_original": "댓글 원문",
      "like_count": 10,
      "published_at": "2026-07-01T11:00:00+09:00",
      "analysis": {
        "status": "succeeded",
        "is_hate_speech": true,
        "categories": ["욕설"],
        "target_group": null,
        "hate_type": "insult",
        "reasoning": "분류 근거 요약",
        "rag_context_status": "complete",
        "similar_cases_used": [],
        "definition_docs_used": []
      }
    }
  ],
  "total": 1,
  "next_cursor": null,
  "has_more": false
}
```

### GET /api/reports/{report_id}/script-segments

스크립트 세그먼트 분석 결과 목록을 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| limit | int | 페이지 크기 |
| cursor | string | 다음 페이지 cursor |
| is_hate_speech | boolean nullable | 혐오표현 여부 필터 |
| status | string nullable | `succeeded`, `failed`, `skipped` |

성공 응답:

```json
{
  "items": [
    {
      "segment_id": "d1432d33-c277-4584-9cc9-8334819a8f61",
      "segment_index": 0,
      "start_seconds": 0.0,
      "end_seconds": 5.2,
      "text": "스크립트 문장",
      "analysis": {
        "status": "succeeded",
        "is_hate_speech": false,
        "categories": [],
        "target_group": null,
        "hate_type": null,
        "reasoning": "분류 근거 요약",
        "rag_context_status": "complete",
        "similar_cases_used": [],
        "definition_docs_used": []
      }
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### GET /api/reports/{report_id}/network

댓글과 대댓글 기반 소셜 네트워크를 조회한다.

성공 응답:

```json
{
  "network_id": "44c2fc79-8070-480a-92c7-62d64775ca16",
  "status": "succeeded",
  "graph_type": "comment_reply_author_network",
  "directed": true,
  "summary": {
    "node_count": 300,
    "edge_count": 350,
    "top_nodes": []
  },
  "nodes": [
    {
      "node_key": "CHANNEL_ID",
      "node_type": "author",
      "label": "작성자",
      "comment_count": 12,
      "hate_speech_count": 2,
      "hate_speech_ratio": 0.1667,
      "metrics": {
        "in_degree": 3,
        "out_degree": 4
      }
    }
  ],
  "edges": [
    {
      "source_node_key": "REPLY_AUTHOR_CHANNEL_ID",
      "target_node_key": "PARENT_AUTHOR_CHANNEL_ID",
      "edge_type": "reply_to",
      "weight": 1,
      "is_hate_speech": false
    }
  ]
}
```

정책:

- 네트워크가 큰 경우 MVP 이후 nodes와 edges에도 pagination을 도입할 수 있다.
- MVP에서는 보고서 렌더링 가능한 크기의 JSON을 우선 제공한다.

## Export API

### POST /api/reports/{report_id}/exports

보고서 내보내기 작업을 생성한다.

요청:

```json
{
  "format": "xlsx"
}
```

허용 format:

- `html`
- `xlsx`

MVP 제외 format:

- `pdf`

성공 응답:

```http
202 Accepted
```

```json
{
  "export_id": "4040f67c-3c63-4ac2-bd45-86889491d342",
  "report_id": "176ff06e-e91c-402b-ae5a-bd3a8dc977c6",
  "format": "xlsx",
  "status": "pending",
  "status_url": "/api/exports/4040f67c-3c63-4ac2-bd45-86889491d342"
}
```

### GET /api/exports/{export_id}

export 상태를 조회한다.

성공 응답:

```json
{
  "export_id": "4040f67c-3c63-4ac2-bd45-86889491d342",
  "report_id": "176ff06e-e91c-402b-ae5a-bd3a8dc977c6",
  "format": "xlsx",
  "status": "succeeded",
  "file_size_bytes": 123456,
  "download_url": "/api/exports/4040f67c-3c63-4ac2-bd45-86889491d342/download",
  "created_at": "2026-07-08T07:21:00+09:00",
  "finished_at": "2026-07-08T07:21:03+09:00"
}
```

### GET /api/exports/{export_id}/download

export 파일을 다운로드한다.

응답:

- HTML: `text/html`
- Excel: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

## 관리자 API

관리자 API는 `X-Admin-Token` 헤더를 요구한다.

### GET /api/admin/jobs

job 목록을 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| status | string nullable | job 상태 필터 |
| youtube_video_id | string nullable | video ID 필터 |
| limit | int | 페이지 크기 |
| cursor | string nullable | 다음 페이지 cursor |

성공 응답:

```json
{
  "items": [
    {
      "job_id": "0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
      "youtube_video_id": "VIDEO_ID",
      "status": "partial_success",
      "created_at": "2026-07-08T07:05:36+09:00",
      "finished_at": "2026-07-08T07:20:00+09:00",
      "error_summary": []
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### GET /api/admin/jobs/{job_id}

관리자용 job 상세를 조회한다.

성공 응답은 일반 job 조회보다 step metrics, error summary, retry 가능 여부를 더 자세히 포함한다.

```json
{
  "job_id": "0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
  "status": "failed",
  "retryable": true,
  "failed_steps": [
    {
      "step_key": "collect_comments",
      "error_code": "YOUTUBE_QUOTA_EXCEEDED",
      "retryable": true
    }
  ]
}
```

### POST /api/admin/jobs/{job_id}/retry

실패한 job의 재시도를 요청한다.

요청:

```json
{
  "from_failed_step": true
}
```

성공 응답:

```http
202 Accepted
```

```json
{
  "job_id": "0cfcf4ce-8b1f-46b0-9cb2-962dbad45f47",
  "status": "pending",
  "retry_mode": "same_job_failed_step"
}
```

정책:

- MVP 기본값은 같은 job의 실패 step부터 재실행이다.
- 사용자가 새 분석을 요청하는 API와 다르다.

### GET /api/admin/settings

운영 설정의 노출 가능한 값만 조회한다.

성공 응답:

```json
{
  "youtube_api_key": {
    "is_configured": true,
    "last_used_at": "2026-07-08T07:10:00+09:00",
    "last_error_code": null
  },
  "llm": {
    "provider": "anthropic",
    "model": "configured-model-name",
    "api_key_configured": true
  },
  "embedding": {
    "provider": "upstage",
    "model": "configured-embedding-model",
    "api_key_configured": true
  },
  "vector_stores": {
    "provider": "chroma",
    "examples": {
      "collection": "hate_speech_examples",
      "is_configured": true
    },
    "definitions": {
      "collection": "hate_speech_definitions",
      "corpus_version": "definition-corpus-version",
      "is_configured": true
    }
  }
}
```

정책:

- API 키 원문은 반환하지 않는다.
- 설정 변경 API는 MVP 범위에서 제외한다.

### GET /api/admin/logs

운영 로그를 조회한다.

Query:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| job_id | uuid nullable | job 필터 |
| level | string nullable | 로그 레벨 |
| event_type | string nullable | 이벤트 유형 |
| limit | int | 페이지 크기 |
| cursor | string nullable | 다음 페이지 cursor |

성공 응답:

```json
{
  "items": [
    {
      "created_at": "2026-07-08T07:10:00+09:00",
      "level": "warning",
      "event_type": "quota_event",
      "message": "YouTube quota exceeded.",
      "metadata": {
        "provider": "youtube"
      }
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### GET /api/admin/quota-events

YouTube API quota 이벤트를 조회한다.

성공 응답:

```json
{
  "items": [
    {
      "provider": "youtube",
      "operation": "commentThreads.list",
      "status": "used",
      "quota_cost": 1,
      "created_at": "2026-07-08T07:10:00+09:00"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

## Health API

### GET /health

프로세스 생존 여부를 확인한다.

응답:

```json
{
  "status": "ok"
}
```

### GET /api/health/readiness

주요 의존성 준비 상태를 확인한다.

응답:

```json
{
  "status": "ok",
  "checks": {
    "postgres": "ok",
    "chroma": "ok",
    "youtube_api_key": "configured",
    "llm_api_key": "configured"
  }
}
```

## Schema 이름 제안

FastAPI Pydantic schema는 다음 이름을 사용한다.

- `CreateAnalysisJobRequest`
- `CreateAnalysisJobResponse`
- `AnalysisJobStatusResponse`
- `JobStepResponse`
- `ReportSummaryResponse`
- `ReportCommentItem`
- `ReportScriptSegmentItem`
- `ReportNetworkResponse`
- `CreateExportRequest`
- `ExportStatusResponse`
- `AdminJobListResponse`
- `AdminSettingsResponse`
- `ErrorResponse`
- `SessionResponse`
- `RegisterApiKeyRequest`
- `UserApiKeyItem`
- `MeJobListResponse`
- `MeReportListResponse`
- `PublicReportListResponse`

## API 검증 기준

API는 다음 조건을 만족해야 한다.

- 유효한 영상 입력은 항상 새 job을 만든다.
- 분석 요청은 장시간 작업을 기다리지 않고 `202`를 반환한다.
- job 상태 API는 단계별 상태와 실패 사유를 반환한다.
- 보고서 API는 snapshot 기준으로 결과를 반환한다.
- 댓글 전체 목록은 pagination으로 조회한다.
- PDF export 요청은 MVP에서 거부한다.
- 관리자 API는 secret 원문을 반환하지 않는다.
- 분석 job 생성은 로그인 세션과 유효한 Anthropic/Upstage API 키 등록을 모두 요구한다.
- 소유자가 아닌 사용자의 job/report 접근은 차단된다.
- 사용자 API 키 원문은 어떤 응답에도 포함되지 않는다.

## 보류 사항

다음 항목은 구현 전 확정한다.

- 관리자 인증을 `X-Admin-Token`으로 계속 유지할지, 이후 관리자도 OAuth 기반으로 통합할지
- 네트워크 API가 큰 그래프에 대해 pagination을 도입할 시점
- HTML 보고서 route를 `/reports/{report_id}`로 유지할지 `/api/reports/{report_id}/html`로 통합할지
- 세션 쿠키의 정확한 만료 기간과 sliding expiration 갱신 주기(초안은 `30_auth_oauth_byok.md` 참조)
- 프론트엔드가 백엔드와 다른 origin/서브도메인에 배포될 경우의 CORS 및 `SameSite` 정책 조정
