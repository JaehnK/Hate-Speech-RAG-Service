# 보고서 명세

| 항목 | 값 |
| --- | --- |
| 버전 | v0.4.0 |
| 작성일시 | 2026-07-16 22:45:00 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 웹 보고서, JSON report payload, HTML 및 Excel 내보내기 구성을 정의한다.

보고서는 수집, 댓글 분석, 스크립트 분석, 댓글 소셜 네트워크를 모듈별로 보여주고, 부분 실패와 분석 한계를 명확히 표시해야 한다.

## 보고서 원칙

- 보고서는 `report_snapshots` 기준으로 렌더링한다.
- report snapshot은 생성 후 수정하지 않는다.
- 같은 영상의 새 분석은 새 report snapshot을 만든다.
- 분석 모듈별 성공과 실패를 독립적으로 표시한다.
- 원천 데이터 전체를 한 화면에 모두 렌더링하지 않는다.
- 댓글과 스크립트 상세 목록은 API pagination으로 조회한다.
- RAG 근거는 유사 혐오표현 예시와 혐오표현 정의 문서 근거를 구분해 표시한다.
- PDF 내보내기는 MVP에서 제외한다.
- API 키, 쿠키, secret, 로컬 브라우저 캐시 정보는 보고서에 포함하지 않는다.
- 보고서 조회는 소유권 기준으로 접근을 제한한다. `is_public_sample = true`인 report만 로그인 없이 조회할 수 있고, 그 외 report는 소유자 본인만 조회할 수 있다. 접근 제어 자체의 상세 사양은 `03_data_model.md`, `05_api_spec.md`, `30_auth_oauth_byok.md`를 따른다.
- 보고서 화면과 payload에는 소유자의 Google 이메일, 표시 이름 등 신원 정보를 노출하지 않는다. 보고서 내용은 영상과 분석 결과에 대한 것이지 요청자 개인정보가 아니다.

## 보고서 대상

### 분석 이용자

분석 이용자는 본인이 소유한(또는 공개 샘플로 지정된) 영상별 혐오표현 분포, 대표 사례, 스크립트 분석, 댓글 네트워크를 확인한다.

### 관리자

관리자는 보고서의 실패 섹션과 분석 설정 정보를 통해 수집, quota, LLM, dual vector store 문제를 추적한다.

관리자 전용 운영 로그는 보고서가 아니라 관리자 API에서 조회한다.

## 보고서 생성 조건

보고서 snapshot은 다음 조건을 만족하면 생성한다.

- 영상 메타데이터 snapshot이 존재한다.
- 각 분석 모듈의 성공 artifact 또는 실패 정보가 존재한다.
- 보고서 생성 시점의 analysis run 설정이 존재한다.

보고서 snapshot을 생성하지 않는 경우:

- 영상 메타데이터 수집이 실패했다.
- report payload 조립 중 필수 데이터 무결성이 깨졌다.

## 웹 보고서 섹션

### 1. Header

목적:

- 어떤 영상에 대한 어떤 분석 snapshot인지 즉시 확인한다.

표시 항목:

- 영상 제목
- 채널명
- 게시일
- YouTube video ID
- 수집 시각
- 분석 완료 시각
- job 상태
- report snapshot ID

상태 badge:

- `succeeded`
- `partial_success`
- `failed`

### 2. 영상 및 수집 요약

표시 항목:

- 조회 수
- 좋아요 수
- YouTube API 기준 댓글 수
- 실제 수집 댓글 수
- 최상위 댓글 수
- 대댓글 수
- 공개 자막 수집 여부
- 스크립트 segment 수

주의:

- YouTube API의 댓글 수와 실제 수집 수는 다를 수 있다.
- 댓글 수집이 중간에 실패했으면 미완료 상태를 명확히 표시한다.

### 3. 댓글 혐오표현 분석 요약

표시 항목:

- 분석 대상 댓글 수
- 분석 성공 댓글 수
- 분석 실패 댓글 수
- 혐오표현 댓글 수
- 혐오표현 비율
- 카테고리 분포
- 대상 집단 분포
- 혐오 유형 분포

대표 사례:

- 혐오표현 가능성이 높은 댓글
- 카테고리별 대표 댓글
- 좋아요 수가 높은 혐오표현 댓글
- 대댓글 맥락이 있는 대표 사례

상세 조회:

- 웹 화면에서는 대표 사례와 요약을 우선 보여준다.
- 전체 댓글 분석 결과는 `/api/reports/{report_id}/comments`에서 pagination으로 조회한다.

### 4. 스크립트 혐오표현 분석 요약

표시 항목:

- segment 수
- 분석 성공 segment 수
- 분석 실패 segment 수
- 혐오표현 segment 수
- 카테고리 분포
- 타임라인 또는 segment 순서 기반 분포

대표 사례:

- 혐오표현으로 분류된 스크립트 문장
- 증거 강도가 높은 segment
- 카테고리별 대표 segment

상세 조회:

- 전체 segment 분석 결과는 `/api/reports/{report_id}/script-segments`에서 pagination으로 조회한다.
- 프론트엔드는 시간순으로 자막 구간, 정상·혐오표현·실패 상태, 카테고리, 한국어 분석 사유를 표시한다.
- 자막이 없는 경우와 API 조회 실패를 각각 다른 상태로 표시한다.

### 5. 댓글 소셜 네트워크

목적:

- 댓글과 대댓글 관계를 통해 상호작용 구조를 보여준다.
- 혐오표현 댓글이 특정 작성자 또는 상호작용 주변에 집중되는지 탐색할 수 있게 한다.

MVP 그래프 정의:

- 노드: 댓글 작성자
- 노드 key: `author_channel_id` 우선, 없으면 안정적인 내부 key
- 노드 label: 작성자 표시명
- 엣지: 대댓글 작성자가 부모 댓글 작성자에게 답글을 단 관계
- 방향: reply author -> parent comment author
- 저장 edge weight: 개별 대댓글 1건 기준 `1`
- 보고서 summary weight: 같은 작성자 쌍의 대댓글 수를 집계한 값

노드 표시 속성:

- 댓글 수
- 혐오표현 댓글 수
- 혐오표현 비율
- in-degree
- out-degree

엣지 표시 속성:

- 대댓글 수
- 혐오표현 대댓글 수
- 대표 comment ID

보고서 표시:

- 그래프 시각화
- 노드 수와 엣지 수
- 혐오표현 비율이 높은 작성자 목록
- 상호작용이 많은 작성자 쌍
- 네트워크 생성 실패 또는 데이터 부족 사유

주의:

- MVP의 네트워크는 댓글과 대댓글 관계만 사용한다.
- 구독, 조회, 좋아요 관계는 네트워크에 포함하지 않는다.
- 작성자 표시명은 중복될 수 있으므로 식별자는 `author_channel_id`를 우선한다.

### 6. 부분 실패 및 분석 한계

표시 항목:

- 댓글 비활성화
- 댓글 수집 미완료
- 공개 자막 없음
- 스크립트 수집 실패
- LLM 일부 실패
- 네트워크 생성 실패
- report export 실패

각 실패 항목은 다음 정보를 포함한다.

- 실패 모듈
- error code
- 사용자에게 보여줄 설명
- 재시도 가능 여부
- 영향을 받은 보고서 섹션

### 7. 분석 설정과 재현 정보

표시 항목:

- analysis run ID
- LLM provider
- LLM model
- embedding provider
- embedding model
- example Chroma collection
- definition Chroma collection
- definition corpus version
- example retriever 설정
- definition retriever 설정
- prompt version
- 생성 시각

표시하지 않는 항목:

- API key 원문
- secret manager key path
- 로컬 쿠키 또는 브라우저 캐시 경로
- raw prompt 전문이 민감정보를 포함할 경우의 원문

## Report Payload

`report_snapshots.payload`는 웹 보고서와 API 요약의 기준 payload다.

기본 구조:

```json
{
  "report_id": "uuid",
  "analysis_run_id": "uuid",
  "job_id": "uuid",
  "youtube_video_id": "VIDEO_ID",
  "created_at": "2026-07-08T07:07:13+09:00",
  "status": "partial_success",
  "video": {},
  "collection_summary": {},
  "comment_analysis_summary": {},
  "script_analysis_summary": {},
  "network_summary": {},
  "representative_cases": {
    "comments": [],
    "script_segments": []
  },
  "failure_summary": [],
  "methodology": {},
  "links": {}
}
```

### video

```json
{
  "title": "영상 제목",
  "channel_title": "채널명",
  "youtube_channel_id": "CHANNEL_ID",
  "published_at": "2026-07-01T10:00:00+09:00",
  "duration_seconds": 600,
  "view_count": 100000,
  "like_count": 5000,
  "comment_count": 1200,
  "thumbnail_url": "https://example.com/thumb.jpg"
}
```

### collection_summary

```json
{
  "metadata_collected_at": "2026-07-08T07:08:00+09:00",
  "comments": {
    "status": "succeeded",
    "total_collected": 1200,
    "top_level_count": 850,
    "reply_count": 350
  },
  "transcript": {
    "status": "succeeded",
    "language_code": "ko",
    "is_auto_generated": false,
    "segment_count": 90
  }
}
```

### comment_analysis_summary

```json
{
  "status": "succeeded",
  "total": 1200,
  "succeeded": 1195,
  "failed": 5,
  "hate_speech_count": 80,
  "hate_speech_ratio": 0.0667,
  "category_distribution": {
    "욕설": 40,
    "차별": 20
  },
  "target_group_distribution": {},
  "hate_type_distribution": {}
}
```

### script_analysis_summary

```json
{
  "status": "succeeded",
  "total": 90,
  "succeeded": 90,
  "failed": 0,
  "hate_speech_count": 3,
  "hate_speech_ratio": 0.0333,
  "category_distribution": {}
}
```

### network_summary

```json
{
  "status": "succeeded",
  "graph_type": "comment_reply_author_network",
  "directed": true,
  "node_count": 300,
  "edge_count": 350,
  "top_nodes": [],
  "top_edges": []
}
```

### failure_summary

```json
[
  {
    "module": "transcript",
    "error_code": "CAPTION_NOT_AVAILABLE",
    "message": "공개 자막을 찾을 수 없습니다.",
    "retryable": false,
    "affected_sections": ["script_analysis"]
  }
]
```

### methodology

```json
{
  "llm": {
    "provider": "configured-provider",
    "model": "configured-model"
  },
  "embedding": {
    "provider": "configured-embedding-provider",
    "model": "configured-embedding-model"
  },
  "vector_stores": {
    "examples": {
      "collection": "hate_speech_examples",
      "retriever": {}
    },
    "definitions": {
      "collection": "hate_speech_definitions",
      "retriever": {},
      "corpus_version": "definition-corpus-version"
    }
  },
  "prompt_versions": {}
}
```

## 대표 사례 선정 규칙

댓글 대표 사례:

- 혐오표현으로 분류된 댓글을 우선한다.
- `evidence_strength`가 높거나 reasoning이 명확한 항목을 우선한다.
- 유사 예시와 정의 문서 근거가 모두 있는 항목을 우선한다.
- 카테고리 다양성을 유지한다.
- 대댓글이면 부모 댓글 맥락을 함께 표시할 수 있다.
- 실패한 분석 항목은 대표 사례에 포함하지 않는다.

스크립트 대표 사례:

- 혐오표현으로 분류된 segment를 우선한다.
- 영상 내 순서를 유지한다.
- 가능하면 시작/종료 시간을 함께 표시한다.

MVP 기본 개수:

- 댓글 대표 사례 최대 10개
- 스크립트 대표 사례 최대 10개
- 카테고리별 대표 사례 최대 3개

## HTML 보고서

MVP HTML 보고서는 FastAPI server-side template로 렌더링한다.

구성:

- Header
- 수집 요약
- 댓글 분석 요약
- 스크립트 분석 요약
- 댓글 소셜 네트워크
- 대표 사례
- 부분 실패 및 분석 한계
- 분석 설정
- 내보내기 버튼

정책:

- HTML은 report snapshot payload를 기준으로 렌더링한다.
- 상세 댓글 목록은 필요할 때 API로 조회한다.
- 네트워크 시각화는 report payload 또는 `/api/reports/{report_id}/network`를 사용한다.
- React 기반 frontend 분리는 MVP 이후로 미룬다.

## Excel 내보내기

Excel 파일은 분석 결과를 이동 가능한 형태로 제공한다.

MVP sheet 구성:

| Sheet | 내용 |
| --- | --- |
| `summary` | 영상 정보, 수집 요약, 분석 요약 |
| `failures` | 부분 실패와 오류 코드 |
| `comment_analysis` | 댓글 및 대댓글 분석 결과 |
| `script_analysis` | 스크립트 segment 분석 결과 |
| `network_nodes` | 댓글 네트워크 노드 |
| `network_edges` | 댓글 네트워크 엣지 |
| `methodology` | 모델, dual vector store, prompt version |

`comment_analysis` 주요 컬럼:

- youtube_comment_id
- parent_youtube_comment_id
- is_reply
- author_display_name
- author_channel_id
- text_original
- like_count
- published_at
- analysis_status
- is_hate_speech
- categories
- target_group
- hate_type
- reasoning
- similar_cases_used
- definition_docs_used
- rag_context_status

`script_analysis` 주요 컬럼:

- segment_index
- start_seconds
- end_seconds
- text
- analysis_status
- is_hate_speech
- categories
- target_group
- hate_type
- reasoning
- similar_cases_used
- definition_docs_used
- rag_context_status

정책:

- Excel에는 secret 정보를 포함하지 않는다.
- 실패한 분석 항목은 status와 error code를 포함한다.
- PDF 내보내기는 생성하지 않는다.

## HTML 내보내기

HTML export는 웹 보고서와 같은 내용을 이동 가능한 단일 HTML 파일로 저장한다.

정책:

- 외부 secret이나 서버 내부 경로를 포함하지 않는다.
- 가능하면 CSS와 필요한 최소 JS를 포함한다.
- 대량 댓글 전체 목록은 HTML에 모두 포함하지 않고 요약과 대표 사례를 우선한다.

## 부분 실패 표시 규칙

| 실패 | 보고서 표시 |
| --- | --- |
| 댓글 비활성화 | 댓글 분석과 네트워크 섹션에 댓글 비활성화 표시 |
| 댓글 수집 미완료 | 댓글 분석 미실행 또는 미완료 표시 |
| 공개 자막 없음 | 스크립트 분석 섹션에 자막 없음 표시 |
| LLM 일부 실패 | 실패 건수와 누락 범위 표시 |
| 네트워크 생성 실패 | 네트워크 섹션에 실패 사유 표시 |
| export 실패 | report snapshot은 유지하고 export 상태 API에서 실패 표시 |

## 수치 정의

| 지표 | 정의 |
| --- | --- |
| 댓글 혐오표현 비율 | 혐오표현 댓글 수 / 분석 성공 댓글 수 |
| 스크립트 혐오표현 비율 | 혐오표현 segment 수 / 분석 성공 segment 수 |
| 댓글 분석 실패율 | 분석 실패 댓글 수 / 수집 댓글 수 |
| 네트워크 혐오표현 비율 | 노드별 혐오표현 댓글 수 / 노드별 전체 댓글 수 |
| edge weight | 작성자 쌍의 대댓글 수 또는 개별 대댓글 1건 |

주의:

- 분모가 0이면 비율은 `null`로 표시한다.
- 분석 실패 항목은 혐오표현 비율 분모에 넣지 않는다.

## 보류 사항

다음 항목은 구현 또는 디자인 단계에서 확정한다.

- 네트워크 시각화 라이브러리
- HTML export에 전체 댓글을 포함할지 요약만 포함할지
- 대표 사례 선정에서 `evidence_strength`를 신뢰할 수 없는 경우의 fallback 정렬
- 댓글 작성자 노드 key를 `author_channel_id`로 완전히 고정할지, 없는 경우 표시명 hash를 사용할지
- `partial_success`를 사용자 화면에서 어떤 문구로 보여줄지

## 검증 기준

보고서는 다음 조건을 만족해야 한다.

- 영상 기본 정보와 수집 시각을 표시한다.
- 댓글 수, 대댓글 수, 분석 성공/실패 수를 표시한다.
- 댓글 혐오표현 카테고리 분포와 대표 사례를 표시한다.
- 스크립트 분석 요약과 대표 segment를 표시한다.
- 댓글과 대댓글 기반 소셜 네트워크를 표시한다.
- 부분 실패를 숨기지 않는다.
- 분석 모델과 dual vector store 설정을 표시한다.
- HTML과 Excel 내보내기를 지원한다.
- PDF 내보내기를 제공하지 않는다.
