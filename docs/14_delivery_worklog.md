# 배포 전 완성 작업 기록

| 항목 | 값 |
| --- | --- |
| 시작일 | 2026-07-11 |
| 기준 브랜치 | `main` |
| 완료 기준 | 외부 API 키만 주입하면 실제 E2E를 실행할 수 있는 배포 직전 상태 |

## 작업 원칙

- 기능 묶음마다 별도 브랜치를 사용하고 검증 후 `main`에 병합한다.
- 병합한 브랜치는 삭제하지 않는다.
- 사용자 로컬 `.env`는 읽거나 커밋하지 않는다.
- 외부 API가 필요한 검증은 fake adapter로 자동화하고, 실제 API 검증 절차를 별도로 남긴다.
- 각 병합 전에 테스트, 정적 정합성, migration, 문서와 구현의 일치 여부를 확인한다.

## 예정 시퀀스

1. `feat/rag-poc` — RAG 계약, corpus ingest, 분류 adapter, 비교 실험 기반
2. `feat/service-foundation` — FastAPI, 설정, DB 모델, Alembic, repository
3. `feat/job-pipeline` — job API, polling worker, 단계 실행과 상태 전이
4. `feat/collectors-analysis` — YouTube metadata/comment/transcript 수집과 분석 저장
5. `feat/reporting-operations` — 네트워크, report snapshot, HTML/Excel export, 관리자 API
6. `feat/predeploy-hardening` — Docker 환경, 보안, 관측성, 전체 E2E와 운영 문서

## 병합 기록

### `feat/rag-poc`

- 범위: RAG prompt/output 계약, 내부 taxonomy와 예시 corpus ingest, Chroma dual retrieval, LLM/embedding adapter, 비교 실험 runner
- 사전 상태: `main` 대비 6개 구현 커밋, 로컬 `.env`는 추적하지 않음
- 검증:
  - `git diff main...feat/rag-poc --check`
  - `uv run pytest -q`
- 결과: diff whitespace 오류 없음, 테스트 33개 통과

### `feat/service-foundation`

- 범위: FastAPI app factory, health/readiness, 환경 설정, SQLAlchemy 전체 모델, Alembic 초기 migration, job repository
- 주요 결정:
  - PostgreSQL을 운영 DB로 사용하고 SQLite를 repository/migration 테스트에 사용한다.
  - PostgreSQL에서는 JSONB와 text array를 사용하고 SQLite에서는 호환 JSON 타입을 사용한다.
  - 같은 video ID의 job 중복 생성을 허용하고 댓글 ID는 job 내부에서만 유일하게 유지한다.
- 검증:
  - migration `upgrade head`와 `downgrade base`
  - health/readiness ASGI 호출
  - 전체 table metadata 생성과 repository 제약 테스트
  - `uv run pytest -q`
- 결과: diff 검사와 compileall 통과, migration up/down 포함 테스트 38개 통과

### `feat/job-pipeline`

- 범위: YouTube video ID 검증, Job 생성/상태 API, DB polling worker, step orchestrator, fake report E2E
- 주요 결정:
  - 문서의 10개 step 순서를 repository가 명시적으로 보장한다.
  - 필수 step 실패 시 이후 step을 skipped 처리하고, 선택 step 실패는 report 생성을 계속한다.
  - handler 실패 트랜잭션을 rollback하여 부분 artifact가 다음 단계에 섞이지 않게 한다.
- 검증:
  - URL 형식별 video ID 추출과 잘못된 입력 거부
  - 같은 영상의 독립 job 생성
  - pending → running → succeeded 상태 전이와 report link 생성
  - 필수 metadata 실패 시 job failed 및 downstream skipped
  - 전체 회귀 `uv run pytest -q`
- 결과: diff 검사와 compileall 통과, 정상/실패 E2E 포함 테스트 47개 통과

### `feat/collectors-analysis`

- 범위: YouTube metadata/comment adapter, 공개 자막 수집·segment, 댓글/스크립트 분석 저장, production worker 조립, 외부 정의 corpus와 평가 도구
- 주요 결정:
  - YouTube metadata/comment는 공식 Data API v3만 사용한다.
  - 공개 자막은 API key가 필요 없는 `youtube-transcript-api` adapter로 조회하며 외부 파일 업로드는 추가하지 않는다.
  - 댓글 수집이 중단되면 수집 완료분은 보존하지만 해당 job의 댓글 분석은 실행하지 않는다.
  - 외부 definition corpus는 기본적으로 `commercial_ok`만 ingest하고 ShareAlike, permission, review tier는 제외한다.
  - 합성 gold set은 평가 코드 smoke test에만 사용하고 실제 품질 지표로 표현하지 않는다.
- 검증:
  - YouTube pagination, 추가 reply 조회, quota/comments-disabled 오류 변환
  - 자막 정규화와 시간/길이 기반 segment 생성
  - comment/script 모든 항목에 성공 또는 실패 결과 생성
  - 실제 adapter 조립 pipeline과 부분 댓글 수집 경로
  - RAG collection/corpus metadata 기록 및 license gate
  - 전체 회귀 `uv run pytest -q`
- 결과: diff, Ruff, compileall 통과, 수집·분석·부분 실패 포함 테스트 57개 통과

## 외부 검증 대기 항목

- YouTube Data API 실제 metadata/comment 수집: `YOUTUBE_API_KEY` 필요
- 실제 LLM RAG 품질 실험: `ANTHROPIC_API_KEY` 필요
- Upstage embedding 실제 corpus ingest: `UPSTAGE_API_KEY` 필요
- API 키 없이 fake client와 deterministic embedding으로 전체 경로를 먼저 검증한다.
