# HLD

| 항목 | 값 |
| --- | --- |
| 버전 | v0.1.0 |
| 작성일시 | 2026-07-08 06:48:52 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP의 상위 설계를 정의한다.

이 문서는 구현자가 FastAPI 애플리케이션, background worker, 수집 모듈, 분석 모듈, 보고서 모듈의 책임을 혼동하지 않도록 하는 기준 문서다.

## 설계 범위

MVP는 단일 YouTube 영상 URL 또는 영상 ID 하나를 입력받아 다음 산출물을 만든다.

- 영상 메타데이터
- 댓글과 대댓글 원천 데이터
- 공개 자막 기반 스크립트 데이터
- 댓글 혐오표현 분석 결과
- 스크립트 혐오표현 분석 결과
- 댓글과 대댓글 기반 소셜 네트워크
- 웹 보고서와 HTML, Excel 내보내기
- 보고서 생성 시점의 snapshot

MVP는 다음 항목을 포함하지 않는다.

- 다중 영상 업로드
- 멀티 테넌트 사용자 관리
- PDF 내보내기
- 외부 자막 업로드
- 관리자 웹 화면
- 브라우저 캐시 또는 로컬 Chrome 세션 의존 수집
- 기존 분석 결과 재사용 기반 재분석 판단

## 핵심 결정

- 초기 구조는 modular monolith로 시작한다.
- 하나의 FastAPI 애플리케이션과 하나의 background worker 프로세스를 둔다.
- 수집, 분석, 보고서 생성은 내부 모듈로 분리한다.
- 오래 걸리는 작업은 HTTP 요청 경로 안에서 직접 실행하지 않는다.
- 동일 영상이 다시 요청되어도 MVP에서는 항상 새 job을 생성하고 새 분석을 수행한다.
- 댓글은 항상 전체 수집과 전체 분석을 목표로 한다.
- 관리자 기능은 MVP에서 API로만 제공한다.
- 보고서는 생성 시점의 snapshot을 저장한다.
- 댓글 소셜 네트워크는 독립 artifact로 생성한다.
- 원천 프로젝트 디렉토리인 `YouTubeHateSpeech/`, `hateSpeechRAG/`는 MVP 구현 전환의 참조 코드로 사용하고, 추후 별도 서브모듈 또는 vendor 구조로 포함하는 것을 검토한다.

## 시스템 컨텍스트

```text
분석 이용자
  -> FastAPI Web/API
      -> PostgreSQL
      -> Object/File Storage
      -> Chroma Vector Store
      -> Background Worker
          -> YouTube Data API
          -> Public Caption Collector
          -> LLM Provider
관리자
  -> FastAPI Admin API
```

## 런타임 구성

### FastAPI 애플리케이션

FastAPI 애플리케이션은 동기적인 요청 처리와 조회 화면 렌더링을 담당한다.

주요 책임:

- 영상 분석 요청 접수
- video ID 추출과 입력 검증
- job 생성
- job 상태 조회 API 제공
- 보고서 조회 페이지 렌더링
- HTML, Excel 내보내기 제공
- 관리자 API 제공

FastAPI 애플리케이션은 댓글 수집, RAG 분석, 보고서 생성 같은 장시간 작업을 직접 수행하지 않는다.

### Background Worker

Background worker는 job queue에서 작업을 가져와 수집, 분석, 보고서 생성을 순차 또는 단계별로 실행한다.

주요 책임:

- job 상태 전이
- 단계별 task 실행
- 외부 API 호출 재시도
- 부분 실패 기록
- 분석 artifact 저장
- 보고서 snapshot 생성 요청

MVP에서는 worker를 별도 프로세스로 실행하되, 코드베이스는 FastAPI 앱과 공유한다.

### PostgreSQL

PostgreSQL은 서비스의 기준 저장소다.

저장 대상:

- jobs
- videos
- comments
- transcripts
- analysis runs
- comment analysis results
- script analysis results
- network nodes and edges
- report snapshots
- exports
- operation logs

### Chroma Vector Store

Chroma는 RAG 분류에 필요한 혐오표현 유사 사례 검색 저장소로 사용한다.

MVP에서는 기존 `hate_speech_collection`에 해당하는 컬렉션을 서비스 설정으로 관리한다. 분석 결과에는 사용한 embedding provider, collection name, retriever 설정을 남긴다.

### Object/File Storage

원천 자막 파일, 내보내기 파일, 보고서 snapshot payload처럼 관계형 테이블에 직접 넣기 부담스러운 산출물을 저장한다.

MVP에서는 로컬 파일 시스템 또는 단일 object storage adapter 중 하나로 시작할 수 있다. 저장소 선택은 배포 환경 문서에서 확정한다.

## 내부 모듈

### API Module

HTTP endpoint와 request/response schema를 담당한다.

주요 하위 영역:

- `analysis_api`: 분석 요청과 상태 조회
- `report_api`: 보고서 조회와 내보내기
- `admin_api`: 운영 설정과 실패 job 조회
- `health_api`: health check

### Job Orchestrator

job 생성, 단계 전이, 재시도 가능 여부 판단을 담당한다.

주요 상태:

- `pending`
- `running`
- `partial_success`
- `succeeded`
- `failed`
- `canceled`

주요 단계:

- `collect_metadata`
- `collect_comments`
- `collect_transcript`
- `analyze_comments`
- `analyze_script`
- `build_comment_network`
- `build_report_snapshot`
- `export_report`

### Collection Module

YouTube 원천 데이터를 수집한다.

주요 컴포넌트:

- `VideoMetadataCollector`
- `CommentCollector`
- `TranscriptCollector`

수집 정책:

- 영상 메타데이터와 댓글, 대댓글은 공식 YouTube Data API를 기본 경로로 수집한다.
- 댓글은 페이지네이션을 끝까지 따라가며 전체 수집을 목표로 한다.
- 대댓글은 최상위 댓글 응답에 포함된 일부 답글만 믿지 않고, 필요한 경우 parent comment ID 기준으로 추가 조회한다.
- 공개 자막은 외부 파일 업로드 없이 수집 가능한 공개 자막만 사용한다.
- 브라우저 캐시, 로컬 Chrome 세션, 쿠키 의존 수집은 MVP 기본 경로로 사용하지 않는다.

### Analysis Module

댓글과 스크립트 텍스트를 RAG 기반으로 분류한다.

주요 컴포넌트:

- `CommentAnalyzer`
- `ScriptAnalyzer`
- `RagClassifier`
- `VectorStoreClient`
- `LlmClient`

분석 정책:

- 댓글 분석은 수집된 전체 댓글과 대댓글을 대상으로 한다.
- 스크립트 분석은 수집된 자막을 세그먼트로 나누어 수행한다.
- 각 분석 결과에는 모델명, prompt version, vector store collection, retriever 설정, 실행 시각을 저장한다.
- 개별 댓글 또는 세그먼트 분석 실패는 전체 job 실패가 아니라 항목별 실패로 기록할 수 있다.

### Network Module

댓글과 대댓글 관계를 소셜 네트워크 artifact로 변환한다.

MVP 기본 그래프:

- 노드: 댓글 작성자
- 엣지: 작성자 A가 작성자 B의 댓글에 대댓글을 단 관계
- 방향: reply author -> parent comment author
- 노드 속성: 댓글 수, 혐오표현 댓글 수, 혐오표현 비율
- 엣지 속성: comment ID, parent ID, 혐오표현 여부, weight

저장 대상:

- network nodes
- network edges
- network summary
- report rendering payload

그래프 생성 실패는 보고서의 소셜 네트워크 섹션만 실패 처리한다.

### Report Module

보고서 화면과 내보내기 산출물을 만든다.

주요 컴포넌트:

- `ReportBuilder`
- `ReportSnapshotStore`
- `HtmlReportRenderer`
- `ExcelExportBuilder`

보고서 구성:

- 영상 기본 정보
- 수집 요약
- 댓글 분석 요약
- 스크립트 분석 요약
- 대표 혐오표현 사례
- 댓글과 대댓글 기반 소셜 네트워크
- 부분 실패와 분석 한계
- 사용 모델과 분석 기준

보고서는 생성 시점의 snapshot을 저장한다. 이후 같은 영상에 새 분석이 생성되어도 기존 보고서 snapshot은 바뀌지 않는다.

### Admin Module

관리자 API를 제공한다.

MVP 기능:

- API 키 등록 여부 확인
- 최근 quota 오류 조회
- 실패 job 조회
- 재시도 가능한 job 확인
- 모델과 RAG 설정 조회
- 운영 로그 조회

MVP에서는 관리자 웹 UI를 만들지 않는다.

## Job 흐름

```text
1. submit_analysis
2. create_job
3. collect_metadata
4. collect_comments
5. collect_transcript
6. analyze_comments
7. analyze_script
8. build_comment_network
9. build_report_snapshot
10. mark_job_done
```

단계 간 기본 의존성:

- `collect_metadata`는 모든 후속 단계의 기준이 된다.
- `analyze_comments`는 `collect_comments` 성공 또는 부분 성공 이후 실행된다.
- `analyze_script`는 `collect_transcript` 성공 이후 실행된다.
- `build_comment_network`는 댓글 수집 데이터와 댓글 분석 결과를 사용한다.
- `build_report_snapshot`은 성공한 artifact와 실패 기록을 모두 조합한다.

부분 실패 정책:

- 댓글이 비활성화되면 댓글 분석과 네트워크 생성만 실패 처리한다.
- 공개 자막이 없으면 스크립트 분석만 실패 처리한다.
- 일부 LLM 호출이 실패하면 실패 항목 수와 실패 ID를 기록한다.
- 네트워크 생성이 실패해도 댓글 분석 결과는 유지한다.
- 보고서 snapshot은 성공한 artifact와 실패 정보를 함께 담는다.

## 주요 API 표면

상세 endpoint는 `05_api_spec.md`에서 확정한다.

MVP에서 필요한 API 표면은 다음과 같다.

- `POST /api/analysis-jobs`
- `GET /api/analysis-jobs/{job_id}`
- `GET /api/reports/{report_id}`
- `GET /reports/{report_id}`
- `POST /api/reports/{report_id}/exports`
- `GET /api/exports/{export_id}`
- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
- `POST /api/admin/jobs/{job_id}/retry`
- `GET /api/admin/settings`
- `GET /api/admin/logs`

## 데이터 저장 경계

상세 테이블은 `03_data_model.md`에서 확정한다.

HLD 기준의 저장 경계는 다음과 같다.

- 원천 수집 데이터와 분석 결과를 같은 테이블에 섞지 않는다.
- 분석 실행 단위는 `analysis_run`으로 분리한다.
- 동일 영상의 반복 분석은 서로 다른 job과 analysis run으로 저장한다.
- 보고서 snapshot은 특정 analysis run을 기준으로 고정한다.
- network nodes와 edges는 특정 analysis run에 종속된다.
- exports는 특정 report snapshot에 종속된다.

## 보안과 민감정보

- YouTube API 키, LLM API 키, embedding API 키는 로그와 보고서에 출력하지 않는다.
- 관리자 API 응답은 키 원문 대신 등록 여부와 최근 오류만 제공한다.
- 쿠키 파일 경로, 브라우저 세션 정보, 로컬 캐시 경로는 MVP 보고서에 포함하지 않는다.
- 외부 API 오류 메시지는 저장 전 민감정보를 마스킹한다.
- 보고서에는 YouTube 공개 데이터와 분석 결과만 포함한다.

## 관측성과 운영

MVP에서 기록해야 할 최소 운영 정보:

- job 생성 시각, 시작 시각, 종료 시각
- 단계별 상태와 소요 시간
- YouTube API quota 관련 오류
- LLM 호출 실패 수
- 댓글 수집 수량
- 분석 성공/실패 항목 수
- 보고서 snapshot 생성 여부
- export 생성 여부

운영 로그는 관리자 API로 조회한다. 민감정보는 저장 전 마스킹한다.

## 배포 형태

MVP 기준 프로세스:

- `web`: FastAPI 애플리케이션
- `worker`: background worker
- `postgres`: PostgreSQL
- `chroma`: Chroma vector store 또는 persistent directory

초기 개발 환경은 Docker Compose로 묶는 것을 기본 후보로 둔다. 실제 배포 방식은 `08_mvp_plan.md`에서 구현 순서와 함께 확정한다.

## 원천 프로젝트 전환 기준

`YouTubeHateSpeech/`의 수집 코드는 다음 책임으로 재구성한다.

- video ID 추출
- 영상 메타데이터 수집
- 댓글과 대댓글 전체 수집
- 자막 수집 adapter
- 수집 결과 정규화

`hateSpeechRAG/`의 분석 코드는 다음 책임으로 재구성한다.

- Chroma vector store 접근
- RAG classifier
- 댓글 분석
- 스크립트 세그먼트 분석
- 댓글-대댓글 네트워크 생성

전환 시 주의할 점:

- 기존 DAO와 신규 서비스 DAO를 직접 섞지 않는다.
- 기존 스크립트의 print 기반 진행 상황은 job event와 operation log로 전환한다.
- 기존 raw 파일과 노트북 산출물은 서비스 런타임 의존성으로 두지 않는다.
- 원천 프로젝트는 추후 서브모듈 또는 vendor 형태로 포함할 수 있으나, MVP 서비스의 실행 경계는 새 FastAPI 코드베이스가 가진다.

## HLD 검증 기준

이 HLD는 다음 조건을 만족하면 다음 문서 작업의 기준으로 사용할 수 있다.

- `00_project_brief.md`의 MVP 범위를 넓히지 않는다.
- `01_user_scenarios.md`의 이용자 및 관리자 시나리오를 모두 수용한다.
- 수집, 분석, 네트워크, 보고서 모듈의 책임이 분리되어 있다.
- 부분 실패가 독립 artifact 단위로 표현된다.
- 보고서 snapshot과 항상 재분석 정책이 설계에 반영되어 있다.

## 다음 문서

HLD 이후에는 다음 순서로 문서를 작성한다.

1. `03_data_model.md`: 테이블, 관계, 인덱스, 저장 정책
2. `04_pipeline_jobs.md`: job 상태, 단계, 재시도, 부분 실패
3. `05_api_spec.md`: FastAPI endpoint와 schema
4. `06_report_spec.md`: 웹 보고서와 내보내기 구성
5. `07_backend_design.md`: 주요 클래스와 모듈 책임
6. `08_mvp_plan.md`: 구현 순서와 검증 기준
