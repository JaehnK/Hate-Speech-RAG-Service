# MVP 구현 계획

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.0 |
| 작성일시 | 2026-07-08 08:35:46 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 보고서 서비스의 MVP 구현 순서와 검증 기준을 정의한다.

목표는 FastAPI 기반 modular monolith를 빠르게 세우되, 수집, 분석, 보고서 생성이 서로 뒤섞이지 않게 단계별로 검증하는 것이다.

## MVP 완료 정의

MVP는 다음 조건을 만족하면 완료로 본다.

- 사용자가 YouTube URL 또는 video ID 하나를 제출하고 job ID를 받는다.
- worker가 job을 처리하고 단계별 상태를 기록한다.
- 영상 메타데이터, 댓글, 대댓글, 공개 자막 snapshot을 저장한다.
- 댓글과 스크립트 segment에 예시 검색과 정의 문서 검색을 함께 사용하는 RAG 기반 혐오표현 분석을 수행한다.
- 댓글과 대댓글 기반 소셜 네트워크를 생성한다.
- 보고서 snapshot을 저장한다.
- 웹 보고서와 JSON report API로 결과를 확인한다.
- HTML과 Excel export를 생성한다.
- 부분 실패가 보고서와 job 상태에 표시된다.

## MVP 제외 항목

- 다중 영상 업로드
- 사용자 계정과 멀티 테넌트
- 과금과 quota 공유
- PDF export
- 외부 자막 업로드
- 관리자 웹 화면
- 브라우저 캐시 또는 로컬 Chrome 세션 기반 수집
- 기존 결과 재사용 기반 재분석 판단
- 자동 음성 전사

## 구현 전략

가장 먼저 얇은 end-to-end 경로를 만든다.

초기 end-to-end 경로:

```text
POST /api/analysis-jobs
  -> job 생성
  -> fake worker step 실행
  -> fake report snapshot 생성
  -> GET /api/reports/{report_id}
```

그 다음 실제 YouTube 수집, RAG 분석, 네트워크, export를 단계적으로 붙인다.

이 전략의 이유:

- API, DB, worker, report 경계가 먼저 검증된다.
- 외부 API나 LLM 문제가 전체 구조 검증을 막지 않는다.
- raw 프로젝트 전환 범위를 작게 유지할 수 있다.

## Phase 0. 구현 전 확정

목표:

- 구현 착수 전에 바뀌면 비용이 큰 결정을 정리한다.

작업:

- Python 버전 확정
- `uv` 기반 dependency와 lock file 정책 반영
- Docker Compose 환경 분리 문서 반영
- SQLAlchemy sync/async 권장안 최종 확인
- PostgreSQL polling worker 권장안 최종 확인
- Chroma persistent directory 권장안 최종 확인
- raw 프로젝트를 git submodule로 둘지 vendor로 둘지 확정
- 관리자 인증의 MVP 방식 확정

검증:

- 결정 사항이 `09_implementation_decisions.md`와 관련 설계 문서에 반영되어 있다.
- Docker 환경 분리 기준이 `10_docker_environment.md`에 정리되어 있다.
- `.env*.example`에 필요한 환경변수 목록이 정리되어 있다.

MVP 기본값:

- `uv`
- sync SQLAlchemy
- Alembic
- PostgreSQL polling worker
- Chroma persistent directory
- 관리자 API는 `X-Admin-Token`
- Docker Compose dev, test, prod override 분리

## Phase 1. 프로젝트 스캐폴딩

목표:

- FastAPI 앱과 worker가 실행 가능한 기본 구조를 만든다.

작업:

- `app/` 패키지 생성
- FastAPI `main.py` 생성
- settings, logging, error handler 구성
- health API 추가
- pytest 기본 구조 추가
- `pyproject.toml`과 `uv.lock` 구성
- Dockerfile과 compose 파일 초안 구성

검증:

- `GET /health`가 `200`을 반환한다.
- settings가 `.env`를 읽는다.
- `uv run pytest`가 빈 테스트라도 실행된다.
- web 프로세스와 worker entrypoint가 분리되어 있다.
- dev compose 조합으로 web과 worker가 실행된다.

## Phase 2. DB 모델과 마이그레이션

목표:

- 핵심 테이블을 Alembic migration으로 생성한다.

작업:

- SQLAlchemy model 작성
- Alembic 초기화
- `analysis_jobs`, `job_steps` 생성
- snapshot, analysis, network, report, operation 테이블 생성
- repository 기본 class 작성

검증:

- migration up/down이 동작한다.
- 빈 DB에서 전체 테이블이 생성된다.
- `analysis_jobs`와 `job_steps` repository 단위 테스트가 통과한다.
- 동일 video ID로 여러 job row를 만들 수 있다.

## Phase 3. Job API와 Worker Skeleton

목표:

- 분석 요청부터 fake report snapshot 생성까지 end-to-end를 검증한다.

작업:

- `POST /api/analysis-jobs` 구현
- `GET /api/analysis-jobs/{job_id}` 구현
- job step 초기화 구현
- PostgreSQL polling worker 구현
- fake step runner 구현
- fake report snapshot 생성

검증:

- 유효한 video ID 입력 시 job ID가 반환된다.
- 같은 video ID를 두 번 요청하면 job이 두 개 생성된다.
- worker가 pending job을 running, succeeded로 전이한다.
- job 상태 API가 step 목록을 반환한다.
- fake report API가 snapshot을 반환한다.

## Phase 4. YouTube 메타데이터 수집

목표:

- 공식 YouTube Data API로 영상 메타데이터를 수집하고 snapshot으로 저장한다.

작업:

- video ID 추출 utility 구현
- `YouTubeApiClient.get_video` 구현
- `VideoMetadataCollector` 구현
- `video_metadata_snapshots` 저장
- 영상 없음, quota 초과 오류 처리

검증:

- 실제 video ID 하나로 metadata snapshot이 저장된다.
- 존재하지 않는 video ID는 `VIDEO_NOT_FOUND`로 실패한다.
- API key 원문이 로그에 남지 않는다.
- metadata 수집 실패 시 job이 `failed`로 종료된다.

## Phase 5. 댓글과 대댓글 수집

목표:

- 댓글과 대댓글을 전체 수집하고 snapshot으로 저장한다.

작업:

- `commentThreads.list` pagination 구현
- `comments.list` reply pagination 구현
- `CommentCollector.collect_all` 구현
- `comment_snapshots` batch insert 구현
- 댓글 비활성화 처리
- quota event 기록

검증:

- 댓글이 있는 영상에서 최상위 댓글과 대댓글이 저장된다.
- `UNIQUE (job_id, youtube_comment_id)`가 동작한다.
- 댓글 비활성화 영상은 댓글 모듈 실패로 기록되고 job은 계속 진행 가능하다.
- quota 초과는 retryable failure로 기록된다.
- 댓글 수집 미완료 상태에서는 댓글 분석을 성공 처리하지 않는다.

## Phase 6. 공개 자막 수집과 segment 생성

목표:

- 공개 자막을 수집하고 분석 가능한 segment로 저장한다.

작업:

- `TranscriptCollector` 구현
- 공개 자막 조회와 수집 구현
- 자막 정규화 구현
- segment 분할 구현
- `transcript_snapshots`, `transcript_segments` 저장

검증:

- 공개 자막이 있는 영상에서 segment가 생성된다.
- 공개 자막이 없는 영상은 `CAPTION_NOT_AVAILABLE`로 기록된다.
- 외부 자막 업로드 경로가 없다.
- 자막 실패가 댓글 분석을 막지 않는다.

## Phase 7. RAG 분류 Adapter

목표:

- Chroma dual retriever와 LLM 호출을 서비스용 `RagClassifier`로 감싼다.

작업:

- `VectorStoreClient` 구현
- `ExampleRetriever` 구현
- `DefinitionRetriever` 구현
- 혐오표현 정의 문서 corpus seed와 version 기록 방식 추가
- `LlmClient` 구현
- `RagClassifier.classify_text` 구현
- prompt version 관리 추가
- fake classifier 테스트 추가

검증:

- fake classifier로 댓글과 스크립트 분석 테스트가 통과한다.
- 실제 Chroma example collection과 definition collection 접근이 integration test에서 확인된다.
- 분석 결과에 model, prompt version, example collection, definition collection, definition corpus version이 기록된다.
- 분석 결과에 유사 예시와 정의 문서 근거가 분리되어 저장된다.
- LLM 오류가 domain error로 변환된다.

## Phase 8. 댓글 분석

목표:

- 수집된 모든 댓글과 대댓글을 분석하고 결과를 저장한다.

작업:

- `CommentAnalyzer` 구현
- batch 처리 구현
- `comment_analysis_results` 저장
- 항목별 실패 기록
- 분석 요약 계산

검증:

- 수집된 모든 comment snapshot에 결과 row가 생긴다.
- 일부 실패 항목은 `failed`로 저장된다.
- 댓글 혐오표현 수와 카테고리 분포가 계산된다.
- 댓글 분석이 원천 댓글 snapshot을 수정하지 않는다.

## Phase 9. 스크립트 분석

목표:

- transcript segment를 분석하고 결과를 저장한다.

작업:

- `ScriptAnalyzer` 구현
- segment 순서 기반 분석 실행
- `script_analysis_results` 저장
- 분석 요약 계산

검증:

- 모든 segment에 결과 row가 생긴다.
- 공개 자막 없음이면 step이 skipped 처리된다.
- 일부 LLM 실패는 항목별 실패로 기록된다.
- 스크립트 분석이 댓글 분석 결과를 무효화하지 않는다.

## Phase 10. 댓글 소셜 네트워크

목표:

- 댓글과 대댓글 관계를 작성자 기반 네트워크로 저장한다.

작업:

- `CommentNetworkBuilder` 구현
- `author_channel_id` 기반 node key 생성
- node metrics 계산
- edge 생성
- `comment_networks`, nodes, edges 저장
- 네트워크 summary 생성

검증:

- 대댓글이 있는 영상에서 노드와 엣지가 생성된다.
- 자기 자신에게 답글을 단 관계 처리 정책이 적용된다.
- 혐오표현 댓글 수와 비율이 node에 반영된다.
- 네트워크 생성 실패가 댓글 분석 결과를 무효화하지 않는다.

## Phase 11. 보고서 Snapshot과 조회 API

목표:

- 분석 artifact를 조합해 report snapshot을 만들고 API로 조회한다.

작업:

- `ReportBuilder` 구현
- 대표 사례 선정 구현
- failure summary 생성
- `report_snapshots.payload` 저장
- `GET /api/reports/{report_id}` 구현
- comments, script, network 상세 API 구현

검증:

- 성공 artifact와 실패 정보가 report payload에 포함된다.
- 댓글 상세 API가 pagination으로 동작한다.
- 네트워크 API가 nodes와 edges를 반환한다.
- 같은 영상 새 분석이 기존 report snapshot을 바꾸지 않는다.

## Phase 12. 웹 보고서와 Export

목표:

- 웹 보고서와 HTML, Excel export를 제공한다.

작업:

- `/reports/{report_id}` server-side template 구현
- HTML export 구현
- Excel export 구현
- export 상태 API 구현
- 파일 저장소 adapter 구현

검증:

- 웹 보고서에서 영상 요약, 댓글 분석, 스크립트 분석, 네트워크가 보인다.
- 부분 실패가 보고서에 표시된다.
- Excel에 `summary`, `comment_analysis`, `script_analysis`, `network_nodes`, `network_edges` sheet가 있다.
- PDF 요청은 거부된다.

## Phase 13. 관리자 API와 운영 로그

목표:

- API 기반 운영 확인과 실패 job 재시도를 제공한다.

작업:

- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
- `POST /api/admin/jobs/{job_id}/retry`
- `GET /api/admin/settings`
- `GET /api/admin/logs`
- `GET /api/admin/quota-events`
- `X-Admin-Token` 검증

검증:

- 관리자 토큰 없이 관리자 API가 거부된다.
- API 키 원문이 응답에 없다.
- 실패 job의 retryable 여부가 표시된다.
- quota event가 조회된다.

## Phase 14. End-to-End 검증

목표:

- 실제 영상 하나로 전체 흐름을 검증한다.

작업:

- 댓글과 공개 자막이 있는 영상으로 E2E 실행
- 댓글 비활성화 영상으로 부분 실패 실행
- 공개 자막 없는 영상으로 부분 실패 실행
- LLM fake mode와 real mode 검증
- 로그와 민감정보 노출 점검

검증:

- 정상 영상은 report snapshot과 export를 생성한다.
- 댓글 비활성화 영상은 댓글 섹션 실패를 표시한다.
- 공개 자막 없는 영상은 스크립트 섹션 실패를 표시한다.
- API key와 secret이 로그와 보고서에 없다.
- 문서의 MVP 완료 정의를 모두 만족한다.

## 구현 우선순위

1. 프로젝트 스캐폴딩
2. DB migration
3. job API와 worker skeleton
4. metadata 수집
5. 댓글 수집
6. 자막 수집
7. fake RAG 기반 분석 저장
8. 실제 dual vector RAG adapter 연결
9. 네트워크 생성
10. report snapshot
11. 웹 보고서
12. Excel export
13. 관리자 API
14. E2E hardening

## 주요 리스크

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| YouTube quota 초과 | 댓글 전체 수집 실패 | quota event 기록, retryable failure |
| 댓글 수가 매우 많음 | 분석 시간과 LLM 비용 증가 | batch 처리, progress 기록 |
| 공개 자막 없음 | 스크립트 분석 불가 | 부분 실패로 표시 |
| LLM rate limit | 분석 지연 | backoff, 항목별 실패 기록 |
| 기존 DAO와 신규 스키마 충돌 | 데이터 무결성 저하 | raw DAO 직접 사용 금지 |
| 네트워크 그래프 과대 | 보고서 렌더링 지연 | summary 우선, 상세 API 분리 |
| secret 로그 노출 | 보안 사고 | masking, settings repr 제한 |

## 구현 전 질문 후보

다음 항목은 개발 착수 전 확인하면 좋다.

- Python 3.11을 사용할 것인가?
- 관리자 API 인증을 `X-Admin-Token`으로 시작해도 되는가?
- raw 프로젝트는 git submodule로 둘 것인가, 필요한 코드만 새 `app/`으로 옮길 것인가?
- Chroma는 persistent directory로 시작할 것인가, 별도 서버로 띄울 것인가?
- 혐오표현 정의 문서 corpus의 출처와 versioning을 어떻게 둘 것인가?
- 웹 보고서는 server-side template로 먼저 만들고 React 분리는 MVP 이후로 미뤄도 되는가?
- prod profile에 reverse proxy를 포함할 것인가?

이 질문들은 현재 문서 작성을 막지는 않는다. 구현을 시작하기 전에는 결정이 필요하다.

## 산출물 체크리스트

- FastAPI app
- Background worker
- Alembic migrations
- PostgreSQL repositories
- YouTube collection adapters
- RAG classifier adapter
- Definition corpus seed
- Comment analyzer
- Script analyzer
- Comment network builder
- Report builder
- HTML report template
- Excel exporter
- Admin APIs
- E2E test 또는 실행 절차 문서

## 검증 기준

구현 계획은 다음 조건을 만족해야 한다.

- 작은 단위로 구현하고 검증할 수 있다.
- 외부 API나 LLM 없이도 skeleton을 먼저 검증할 수 있다.
- MVP 제외 범위를 끌어오지 않는다.
- 댓글 전체 분석 정책을 유지한다.
- 보고서 snapshot과 항상 새 분석 정책을 유지한다.
- raw 프로젝트의 기존 코드를 안전하게 전환할 수 있다.
