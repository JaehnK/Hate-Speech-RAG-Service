# 백엔드 설계

| 항목 | 값 |
| --- | --- |
| 버전 | v0.2.0 |
| 작성일시 | 2026-07-08 08:17:03 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 FastAPI 백엔드 모듈 구조와 주요 클래스 책임을 정의한다.

이 문서는 기존 `YouTubeHateSpeech/`, `hateSpeechRAG/` 연구 코드를 서비스 코드로 전환할 때의 경계와 adapter 설계를 설명한다.

## 설계 원칙

- 초기 구조는 modular monolith다.
- FastAPI web 프로세스와 worker 프로세스는 같은 코드베이스를 공유한다.
- HTTP layer, service layer, repository layer, external adapter를 분리한다.
- 기존 raw 프로젝트의 DAO를 서비스 런타임에서 직접 사용하지 않는다.
- 원천 데이터와 분석 결과의 저장 책임은 repository가 가진다.
- 장시간 작업은 worker와 job orchestrator가 실행한다.
- 각 분석 모듈은 독립 실패가 가능해야 한다.
- 구현은 단순하게 시작하고, 실제 확장 필요가 생기기 전에는 서비스 분리를 하지 않는다.

## 기술 기본값

MVP 구현 기본값:

- Web framework: FastAPI
- Template: Jinja2 또는 FastAPI compatible template
- Dependency management: `uv`
- DB: PostgreSQL
- DB access: SQLAlchemy 2.x
- Migration: Alembic
- Worker: PostgreSQL polling worker
- Vector store: Chroma
- Vector store mode: persistent directory
- Runtime: Docker Compose with dev, test, prod overrides
- Report export: openpyxl 또는 pandas 기반 Excel writer
- HTTP client: 외부 API adapter 내부에서 관리

구현 세부 확인 사항:

- Python 3.11 기반 image tag
- raw 프로젝트 submodule 또는 vendor 경로
- prod reverse proxy를 Compose에 포함할지 여부

MVP 기본값은 `uv`, sync SQLAlchemy, PostgreSQL polling worker, Chroma persistent directory, server-side template다.

## 패키지 구조

제안 구조:

```text
app/
  main.py
  core/
    config.py
    errors.py
    logging.py
    security.py
    time.py
  api/
    deps.py
    schemas/
      common.py
      jobs.py
      reports.py
      admin.py
      exports.py
    routes/
      health.py
      analysis_jobs.py
      reports.py
      exports.py
      admin.py
  db/
    base.py
    session.py
    models.py
    repositories/
      jobs.py
      videos.py
      comments.py
      transcripts.py
      analysis.py
      networks.py
      reports.py
      operations.py
  jobs/
    worker.py
    orchestrator.py
    steps.py
    progress.py
    retry.py
  collection/
    youtube_client.py
    video_metadata_collector.py
    comment_collector.py
    transcript_collector.py
    normalizers.py
  analysis/
    rag_classifier.py
    comment_analyzer.py
    script_analyzer.py
    prompt_registry.py
    vector_store_client.py
    llm_client.py
  network/
    comment_network_builder.py
    metrics.py
  reports/
    report_builder.py
    representative_cases.py
    html_renderer.py
    excel_exporter.py
  storage/
    file_storage.py
  legacy_adapters/
    youtube_raw_adapter.py
    rag_raw_adapter.py
```

원칙:

- `legacy_adapters/`는 전환기 bridge다.
- 새 서비스 코드가 raw 프로젝트의 전역 설정, 기존 DAO, notebook 산출물에 직접 의존하지 않게 한다.

## Layer 책임

### API Layer

책임:

- request validation
- response schema 변환
- 인증과 관리자 토큰 확인
- service 호출
- HTTP status 결정

API layer가 하지 않는 일:

- YouTube API 직접 호출
- LLM 직접 호출
- DB transaction 세부 처리
- 장시간 분석 실행

주요 router:

- `analysis_jobs.py`
- `reports.py`
- `exports.py`
- `admin.py`
- `health.py`

### Service Layer

책임:

- use case 실행
- transaction 경계 결정
- repository 조합
- external adapter 호출
- domain error 변환

주요 service:

- `AnalysisJobService`
- `ReportQueryService`
- `ExportService`
- `AdminService`

### Repository Layer

책임:

- SQLAlchemy model query
- 저장과 조회
- pagination
- row locking
- transaction 내 데이터 무결성 유지

repository는 외부 API를 호출하지 않는다.

### External Adapter Layer

책임:

- YouTube Data API 호출
- 공개 자막 수집
- Chroma 접근
- LLM 호출
- 파일 저장소 접근

adapter는 service schema에 맞는 DTO를 반환한다.

## 주요 클래스

### Settings

위치:

- `app/core/config.py`

책임:

- 환경변수 로드
- DB URL, Chroma 경로, model 설정, YouTube API 설정 제공
- secret 원문이 로그에 출력되지 않도록 repr 제어

주요 필드:

- `database_url`
- `youtube_api_key`
- `llm_provider`
- `llm_model`
- `embedding_provider`
- `embedding_model`
- `chroma_persist_directory`
- `chroma_collection_name`
- `admin_token`

### AnalysisJobService

위치:

- `app/jobs` 또는 `app/services`

책임:

- 분석 요청을 job으로 생성한다.
- video ID를 검증한다.
- 초기 `job_steps`를 생성한다.
- 같은 영상 요청도 새 job으로 만든다.

주요 메서드:

```python
create_job(input_value: str) -> AnalysisJobCreated
get_job_status(job_id: UUID) -> AnalysisJobStatus
```

### JobWorker

위치:

- `app/jobs/worker.py`

책임:

- pending job을 점유한다.
- orchestrator를 호출한다.
- worker lifecycle을 관리한다.

주요 메서드:

```python
run_forever() -> None
run_once() -> bool
```

### JobOrchestrator

위치:

- `app/jobs/orchestrator.py`

책임:

- pipeline step 순서를 제어한다.
- step 성공, 실패, skipped 상태를 기록한다.
- 최종 job 상태를 결정한다.

주요 메서드:

```python
run_job(job_id: UUID) -> None
run_step(job_id: UUID, step_key: str) -> StepResult
finalize(job_id: UUID) -> JobStatus
```

### StepRunner

위치:

- `app/jobs/steps.py`

책임:

- 개별 step의 공통 실행 로직을 제공한다.
- 시작/종료 로그를 기록한다.
- retryable error를 처리한다.

주요 메서드:

```python
execute(step_context: StepContext) -> StepResult
```

### YouTubeApiClient

위치:

- `app/collection/youtube_client.py`

책임:

- YouTube Data API 호출을 캡슐화한다.
- quota event를 기록할 수 있는 결과를 반환한다.
- raw API 응답을 normalizer에 전달한다.

주요 메서드:

```python
get_video(video_id: str) -> YouTubeVideoPayload
list_comment_threads(video_id: str, page_token: str | None) -> Page
list_replies(parent_comment_id: str, page_token: str | None) -> Page
```

### VideoMetadataCollector

책임:

- video metadata를 수집한다.
- `VideoMetadataSnapshot` DTO로 정규화한다.

주요 메서드:

```python
collect(video_id: str) -> VideoMetadataSnapshot
```

### CommentCollector

책임:

- 최상위 댓글과 대댓글을 전체 수집한다.
- 댓글 수집 미완료와 댓글 비활성화를 구분한다.
- `CommentSnapshot` DTO list를 반환한다.

주요 메서드:

```python
collect_all(video_id: str) -> CommentCollectionResult
```

정책:

- MVP에서는 comment limit을 받지 않는다.
- partial collection은 실패 정보와 함께 반환한다.

### TranscriptCollector

책임:

- 공개 자막을 수집한다.
- 자막 없음과 수집 오류를 구분한다.
- segment를 생성한다.

주요 메서드:

```python
collect(video_id: str) -> TranscriptCollectionResult
```

정책:

- 외부 자막 업로드는 처리하지 않는다.

### RagClassifier

위치:

- `app/analysis/rag_classifier.py`

책임:

- vector store 검색과 LLM 분류를 조합한다.
- comment와 script가 공통으로 사용하는 분류 결과 schema를 반환한다.

주요 메서드:

```python
classify_text(text: str, context: ClassificationContext) -> ClassificationResult
```

### CommentAnalyzer

책임:

- 수집된 모든 댓글 snapshot을 분석한다.
- batch 단위로 RAG classifier를 호출한다.
- 항목별 성공/실패를 저장한다.

주요 메서드:

```python
analyze_all(analysis_run_id: UUID, job_id: UUID) -> CommentAnalysisSummary
```

### ScriptAnalyzer

책임:

- transcript segment를 분석한다.
- segment 순서를 보존한다.
- 항목별 성공/실패를 저장한다.

주요 메서드:

```python
analyze_all(analysis_run_id: UUID, transcript_snapshot_id: UUID) -> ScriptAnalysisSummary
```

### CommentNetworkBuilder

위치:

- `app/network/comment_network_builder.py`

책임:

- 댓글과 대댓글 관계를 작성자 기반 그래프로 만든다.
- 노드와 엣지, summary를 저장한다.

주요 메서드:

```python
build(analysis_run_id: UUID) -> CommentNetworkResult
```

정책:

- 노드 key는 `author_channel_id`를 우선한다.
- `author_channel_id`가 없으면 내부 stable key를 생성한다.
- 그래프 실패는 네트워크 artifact 실패로만 기록한다.

### ReportBuilder

위치:

- `app/reports/report_builder.py`

책임:

- 성공 artifact와 실패 정보를 조합한다.
- report payload를 생성한다.
- `report_snapshots`를 저장한다.

주요 메서드:

```python
build_snapshot(analysis_run_id: UUID) -> ReportSnapshot
```

### HtmlReportRenderer

책임:

- report snapshot payload를 HTML로 렌더링한다.

주요 메서드:

```python
render(report_snapshot_id: UUID) -> str
```

### ExcelExporter

책임:

- report snapshot과 상세 분석 결과를 Excel 파일로 생성한다.

주요 메서드:

```python
export(report_snapshot_id: UUID) -> ExportResult
```

### AdminService

책임:

- 관리자 API에 필요한 job, 설정, 로그, quota event 조회를 제공한다.
- secret 원문을 반환하지 않는다.

주요 메서드:

```python
list_jobs(filters: AdminJobFilters) -> Page[AdminJobItem]
get_settings_summary() -> AdminSettings
retry_job(job_id: UUID) -> RetryResult
```

## 흐름 다이어그램

```text
POST /api/analysis-jobs
  -> AnalysisJobService
      -> JobRepository
      -> JobStepRepository

JobWorker
  -> JobOrchestrator
      -> VideoMetadataCollector
      -> CommentCollector
      -> TranscriptCollector
      -> CommentAnalyzer
      -> ScriptAnalyzer
      -> CommentNetworkBuilder
      -> ReportBuilder

GET /api/reports/{report_id}
  -> ReportQueryService
      -> ReportRepository
      -> AnalysisRepository
      -> NetworkRepository
```

## Repository 목록

| Repository | 책임 |
| --- | --- |
| `JobRepository` | job 생성, 조회, 상태 전이, row locking |
| `JobStepRepository` | step 초기화, 상태 갱신, metrics 저장 |
| `VideoRepository` | video metadata snapshot 저장 |
| `CommentRepository` | comment snapshot 저장과 pagination 조회 |
| `TranscriptRepository` | transcript snapshot과 segment 저장 |
| `AnalysisRepository` | analysis run과 분석 결과 저장 |
| `NetworkRepository` | network, nodes, edges 저장 |
| `ReportRepository` | report snapshot과 export 저장 |
| `OperationLogRepository` | operation log와 quota event 저장 |
| `SecretReferenceRepository` | secret 등록 상태 조회 |

## DTO 경계

외부 adapter는 DB model을 직접 반환하지 않는다.

예시 DTO:

- `VideoMetadataSnapshot`
- `CommentSnapshot`
- `TranscriptSnapshot`
- `TranscriptSegment`
- `ClassificationResult`
- `CommentNetworkNode`
- `CommentNetworkEdge`
- `ReportPayload`

DTO를 두는 이유:

- raw API payload와 DB schema를 분리한다.
- 테스트에서 외부 API 없이 service를 검증할 수 있다.
- 기존 raw 프로젝트 adapter를 안전하게 교체할 수 있다.

## 오류 처리

오류는 domain error로 변환한다.

기본 error class:

- `InvalidInputError`
- `VideoNotFoundError`
- `YoutubeQuotaExceededError`
- `YoutubeRateLimitedError`
- `CommentsDisabledError`
- `CaptionNotAvailableError`
- `CaptionCollectionError`
- `VectorStoreUnavailableError`
- `LlmRateLimitedError`
- `LlmTimeoutError`
- `NetworkBuildError`
- `ReportBuildError`

정책:

- API layer는 domain error를 HTTP error response로 변환한다.
- worker는 domain error를 `job_steps.error_code`와 `operation_logs`에 기록한다.
- 민감정보는 error message 저장 전 마스킹한다.

## 트랜잭션 경계

권장 경계:

- job 생성과 step 초기화는 하나의 transaction이다.
- 각 pipeline step은 독립 transaction으로 완료 상태를 저장한다.
- 대량 댓글 저장은 batch transaction을 사용한다.
- LLM 호출 자체는 DB transaction 밖에서 수행한다.
- 분석 결과 저장은 batch transaction을 사용한다.
- report snapshot 생성은 payload 조립 후 단일 transaction으로 저장한다.

이유:

- 긴 외부 API 호출 중 DB transaction을 오래 잡지 않는다.
- 부분 실패 artifact를 안전하게 보존한다.
- 재시도 시 완료된 step을 식별할 수 있다.

## 기존 raw 코드 전환

### YouTubeHateSpeech

재사용 후보:

- video ID 추출 로직
- YouTube Data API metadata 수집 로직
- 댓글과 대댓글 전체 수집 로직
- 댓글 구조 분석 로직

전환 방식:

- 기존 class를 직접 import하기 전에 service DTO와 repository 경계를 먼저 만든다.
- 필요한 로직만 `collection/` adapter로 옮기거나 감싼다.
- 기존 DB 저장 코드는 사용하지 않는다.

주의:

- 기존 `duration_formatted` 타입과 실제 값이 맞지 않을 수 있다.
- 기존 자막 downloader는 실제 다운로드와 목록 조회 동작을 재확인해야 한다.

### hateSpeechRAG

재사용 후보:

- Chroma vector store 접근
- RAG chain 구성
- 댓글 분류 schema
- 스크립트 분할과 분류 흐름
- 댓글-대댓글 네트워크 생성 아이디어

전환 방식:

- `RagClassifier`로 LLM과 retriever 호출을 감싼다.
- 기존 DAO update 방식은 사용하지 않는다.
- `CommentAnalyzer`, `ScriptAnalyzer`가 새 분석 결과 테이블에 저장한다.
- 네트워크 builder는 `author_channel_id` 기반 node key를 우선하도록 조정한다.

주의:

- 기존 `comments` 테이블에 분석 컬럼을 직접 쓰는 방식은 사용하지 않는다.
- 기존 `scriptresult` 테이블은 새 `script_analysis_results`로 대체한다.

## 테스트 전략

MVP 최소 테스트:

- video ID 추출 테스트
- job 생성 테스트
- step 상태 전이 테스트
- comment snapshot 저장 테스트
- comment analysis result 저장 테스트
- report payload 생성 테스트
- API schema validation 테스트

외부 의존성 테스트:

- YouTube API client는 fixture payload로 단위 테스트한다.
- LLM 호출은 fake classifier로 대체한다.
- Chroma 접근은 integration test에서 별도로 확인한다.

## 구현 전 확인 사항

다음 항목은 구현 시작 전 최종 확인한다.

- Python 3.11 기반 image tag
- 기존 raw 프로젝트를 git submodule로 둘지 vendor directory로 둘지
- `legacy_adapters/`를 MVP에 포함할지, 필요한 로직만 새 코드로 옮길지
- prod reverse proxy를 Compose에 포함할지 여부
- dev DB 관리 도구를 포함할지 여부

## 검증 기준

백엔드 설계는 다음 조건을 만족해야 한다.

- API 요청 경로에서 장시간 수집과 분석을 실행하지 않는다.
- 원천 수집 데이터와 분석 결과가 분리되어 저장된다.
- 같은 영상 재분석이 이전 snapshot을 덮어쓰지 않는다.
- 댓글 분석, 스크립트 분석, 네트워크 생성 실패가 독립적으로 표현된다.
- 보고서 snapshot이 특정 analysis run에 고정된다.
- raw 프로젝트의 기존 DAO에 서비스 런타임이 직접 의존하지 않는다.
