# 백엔드 설계

| 항목 | 값 |
| --- | --- |
| 버전 | v0.4.0 |
| 작성일시 | 2026-07-16 22:30:00 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 FastAPI 백엔드 모듈 구조와 주요 클래스 책임을 정의한다.

이 문서는 기존 `legacy/YouTubeHateSpeech/`, `legacy/hateSpeechRAG/` 연구 코드를 서비스 코드로 전환할 때의 경계와 adapter 설계를 설명한다.

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
- RAG mode: dual retriever, examples + definitions
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
      auth.py
      user_api_keys.py
    routes/
      health.py
      analysis_jobs.py
      reports.py
      exports.py
      admin.py
      auth.py
      me.py
  auth/
    google_oauth_client.py
    session_service.py
    session_cookie_codec.py
    user_account_service.py
    user_api_key_service.py
    key_encryption_service.py
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
      users.py
      sessions.py
      user_api_keys.py
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
    example_retriever.py
    definition_retriever.py
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
- 인증과 관리자 토큰 확인(세션 쿠키 기반 사용자 인증 포함)
- job/report 소유권 검사
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
- `auth.py`
- `me.py`(사용자 API 키, 내 job/report 목록)

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
- `UserAccountService`
- `SessionService`
- `UserApiKeyService`

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
- `example_vector_collection_name`
- `definition_vector_collection_name`
- `definition_corpus_version`
- `admin_token`
- `google_client_id`
- `google_client_secret`
- `google_oauth_redirect_uri`
- `session_cookie_name`
- `session_cookie_domain`
- `session_cookie_secure`
- `session_ttl_seconds`
- `api_key_encryption_key`

### GoogleOAuthClient

위치:

- `app/auth/google_oauth_client.py`

책임:

- Google authorization URL을 생성한다(state, PKCE code_challenge 포함).
- authorization code를 token으로 교환한다.
- ID token 서명과 claim(`aud`, `iss`, `exp`)을 검증한다.

주요 메서드:

```python
build_authorization_url(state: str, code_challenge: str) -> str
exchange_code(code: str, code_verifier: str) -> GoogleTokenResult
verify_id_token(id_token: str) -> GoogleIdentity
```

테스트에서는 fake 구현으로 대체해 실제 Google 호출 없이 로그인 흐름을 검증한다.

### UserAccountService

위치:

- `app/auth/user_account_service.py`

책임:

- `google_sub` 기준으로 사용자를 조회하거나 새로 생성한다.
- 로그인 시각과 프로필 정보를 갱신한다.
- 계정 상태(`active`/`suspended`)를 관리한다.

주요 메서드:

```python
get_or_create_user(identity: GoogleIdentity) -> User
suspend_user(user_id: UUID) -> None
```

### SessionService

위치:

- `app/auth/session_service.py`

책임:

- 로그인 성공 시 세션을 생성한다.
- 요청마다 세션 쿠키를 검증하고 sliding expiration을 적용한다.
- 로그아웃 시 세션을 무효화한다.

주요 메서드:

```python
create_session(user_id: UUID, user_agent: str | None, ip: str | None) -> IssuedSession
validate_session(raw_token: str) -> SessionContext | None
revoke_session(raw_token: str) -> None
```

정책:

- 세션 토큰은 SHA-256 해시로만 저장한다. 상세 사양은 `30_auth_oauth_byok.md`를 따른다.

### SessionCookieCodec

위치:

- `app/auth/session_cookie_codec.py`

책임:

- 세션 쿠키를 발급하고(`Set-Cookie` 헤더 생성), 요청에서 파싱한다.
- `HttpOnly`, `Secure`, `SameSite=Lax` 등 쿠키 속성을 일관되게 적용한다.

주요 메서드:

```python
encode(raw_token: str, expires_at: datetime) -> str
decode(cookie_header: str) -> str | None
expired_cookie() -> str
```

### UserApiKeyService

위치:

- `app/auth/user_api_key_service.py`

책임:

- 사용자가 등록한 Anthropic/Upstage API 키를 검증, 암호화, 저장, 삭제한다.
- 분석 job 실행 시점에 필요한 키를 복호화해 제공한다.

주요 메서드:

```python
register_key(user_id: UUID, provider: str, raw_api_key: str) -> UserApiKeySummary
list_keys(user_id: UUID) -> list[UserApiKeySummary]
delete_key(user_id: UUID, provider: str) -> None
resolve_decrypted_key(user_id: UUID, provider: str) -> str
```

정책:

- `resolve_decrypted_key`는 worker의 job 실행 스코프 안에서만 호출하고, 반환값을 로그나 예외 메시지에 포함하지 않는다.

### KeyEncryptionService

위치:

- `app/auth/key_encryption_service.py`

책임:

- API 키 원문을 애플리케이션 레벨 대칭키(Fernet)로 암호화/복호화한다.

주요 메서드:

```python
encrypt(plaintext: str) -> bytes
decrypt(ciphertext: bytes) -> str
```

정책:

- 마스터 키는 `settings.api_key_encryption_key`에서만 읽고, 암호화 결과 외의 중간값을 로그에 남기지 않는다.

### AnalysisJobService

위치:

- `app/jobs` 또는 `app/services`

책임:

- 분석 요청을 job으로 생성한다.
- video ID를 검증한다.
- 요청자가 필요한 API 키(Anthropic, Upstage)를 등록하고 유효한 상태인지 확인한다.
- 초기 `job_steps`를 생성한다.
- 같은 영상 요청도 새 job으로 만든다.
- job 조회 시 요청자의 소유권을 검사한다.

주요 메서드:

```python
create_job(user_id: UUID, input_value: str) -> AnalysisJobCreated
get_job_status(user_id: UUID, job_id: UUID) -> AnalysisJobStatus
list_jobs_for_user(user_id: UUID, filters: JobListFilters) -> Page[AnalysisJobSummary]
```

정책:

- API 키 미등록 또는 무효 상태면 `ApiKeyNotConfiguredError` 또는 `ApiKeyInvalidError`를 발생시키고 job을 만들지 않는다.
- `get_job_status`는 job의 `user_id`가 요청자와 다르면 `JobAccessDeniedError`를 발생시킨다.

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

- 혐오표현 예시 retriever, 혐오표현 정의 retriever, LLM 분류를 조합한다.
- comment와 script가 공통으로 사용하는 분류 결과 schema를 반환한다.
- 분류 결과에는 유사 예시, 정의 문서 근거, RAG context 상태를 포함한다.

주요 메서드:

```python
classify_text(text: str, context: ClassificationContext) -> ClassificationResult
```

정책:

- `LlmClient`와 embedding client는 전역 설정 키가 아니라, job의 `user_id`로 `UserApiKeyService.resolve_decrypted_key`를 통해 얻은 사용자 키를 사용한다.
- provider가 인증 오류를 반환하면 `ApiKeyInvalidError`로 변환하고, 해당 job step만 실패시킨다(다른 사용자의 job에는 영향 없음).

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
GET /api/auth/google/login
  -> GoogleOAuthClient.build_authorization_url

GET /api/auth/google/callback
  -> GoogleOAuthClient.exchange_code / verify_id_token
      -> UserAccountService.get_or_create_user
      -> SessionService.create_session
      -> SessionCookieCodec.encode

PUT /api/me/api-keys/{provider}
  -> UserApiKeyService.register_key
      -> KeyEncryptionService.encrypt

POST /api/analysis-jobs
  -> AnalysisJobService
      -> UserApiKeyService(키 등록/유효성 확인)
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
| `UserRepository` | 사용자 조회/생성, `google_sub` 기준 lookup |
| `UserSessionRepository` | 세션 생성, 해시 기준 조회, 만료/revoke 처리 |
| `UserApiKeyRepository` | 암호화된 API 키 저장, provider별 조회/삭제 |

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
- `GoogleIdentity`
- `IssuedSession`
- `SessionContext`
- `UserApiKeySummary`

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
- `OAuthStateMismatchError`
- `OAuthCallbackError`
- `SessionInvalidError`
- `SessionExpiredError`
- `AccountSuspendedError`
- `ApiKeyNotConfiguredError`
- `ApiKeyInvalidError`
- `JobAccessDeniedError`

정책:

- API layer는 domain error를 HTTP error response로 변환한다.
- worker는 domain error를 `job_steps.error_code`와 `operation_logs`에 기록한다.
- 민감정보는 error message 저장 전 마스킹한다.
- `ApiKeyInvalidError`, `ApiKeyNotConfiguredError`는 사용자 API 키 원문을 포함하지 않는다. provider와 오류 유형만 기록한다.
- `SessionInvalidError`, `SessionExpiredError`는 세션 토큰 원문을 포함하지 않는다.

## 트랜잭션 경계

권장 경계:

- job 생성과 step 초기화는 하나의 transaction이다.
- 각 pipeline step은 독립 transaction으로 완료 상태를 저장한다.
- 대량 댓글 저장은 batch transaction을 사용한다.
- LLM 호출 자체는 DB transaction 밖에서 수행한다.
- 분석 결과 저장은 batch transaction을 사용한다.
- report snapshot 생성은 payload 조립 후 단일 transaction으로 저장한다.
- 사용자 upsert와 세션 생성은 OAuth 콜백 처리 안에서 하나의 transaction으로 묶는다.
- API 키 등록은 검증 호출(외부 API, transaction 밖) 성공 후 암호화와 저장만 단일 transaction으로 수행한다.

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

### legacy/hateSpeechRAG

재사용 후보:

- Chroma vector store 접근
- RAG chain 구성
- 댓글 분류 schema
- 스크립트 분할과 분류 흐름
- 댓글-대댓글 네트워크 생성 아이디어

전환 방식:

- `RagClassifier`로 LLM, 예시 retriever, 정의 retriever 호출을 감싼다.
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
- 세션 생성/검증/만료/revoke 테스트
- `KeyEncryptionService` 암호화-복호화 round trip 테스트
- job/report 소유권 검사 테스트(다른 사용자의 리소스 접근 시 거부)
- API 키 미등록/무효 상태에서 job 생성이 거부되는지 테스트

외부 의존성 테스트:

- YouTube API client는 fixture payload로 단위 테스트한다.
- LLM 호출은 fake classifier로 대체한다.
- Chroma 접근은 integration test에서 별도로 확인한다.
- `GoogleOAuthClient`는 fake 구현으로 대체해 실제 Google 호출 없이 로그인 E2E를 테스트한다.
- Anthropic/Upstage 키 검증 호출은 fake provider response로 단위 테스트하고, 실제 키 검증은 integration test에서만 확인한다.

## 구현 전 확인 사항

다음 항목은 구현 시작 전 최종 확인한다.

- Python 3.11 기반 image tag
- 기존 raw 프로젝트를 git submodule로 둘지 vendor directory로 둘지
- `legacy_adapters/`를 MVP에 포함할지, 필요한 로직만 새 코드로 옮길지
- prod reverse proxy를 Compose에 포함할지 여부
- dev DB 관리 도구를 포함할지 여부
- Google Cloud Console에서 OAuth client(웹 애플리케이션 유형)를 발급하고 redirect URI를 등록하는 절차
- `API_KEY_ENCRYPTION_KEY` 생성과 배포 환경(Railway 등) 저장 방식

## 검증 기준

백엔드 설계는 다음 조건을 만족해야 한다.

- API 요청 경로에서 장시간 수집과 분석을 실행하지 않는다.
- 원천 수집 데이터와 분석 결과가 분리되어 저장된다.
- 같은 영상 재분석이 이전 snapshot을 덮어쓰지 않는다.
- 댓글 분석, 스크립트 분석, 네트워크 생성 실패가 독립적으로 표현된다.
- 보고서 snapshot이 특정 analysis run에 고정된다.
- raw 프로젝트의 기존 DAO에 서비스 런타임이 직접 의존하지 않는다.
- 로그인하지 않았거나 필요한 API 키가 없으면 분석 job을 생성할 수 없다.
- 소유자가 아닌 사용자의 job/report 조회는 거부된다(공개 샘플 report 제외).
- 사용자 API 키 원문과 세션 토큰 원문이 로그, 오류 메시지, DB 평문 컬럼 어디에도 남지 않는다.
