# 배포 전 완성 작업 기록

| 항목 | 값 |
| --- | --- |
| 시작일 | 2026-07-11 |
| 최종 live 검증 | 2026-07-14 |
| 기준 브랜치 | `main` |
| 완료 기준 | 외부 API 키만 주입하면 실제 E2E를 실행할 수 있는 배포 직전 상태 |

## 2026-07-17 — Google OAuth/BYOK 및 로그인 전 공개 샘플

- 설계: `design/prelogin-public-samples`에서 Stitch desktop/mobile 화면과 공개 표면 계약을 작성하고 `main`에 병합했다.
- 구현: `feat/google-oauth-public-samples`에서 OAuth, server session, Fernet BYOK, 소유권, 공개 sample API, job별 RAG key 주입과 frontend를 구현했다.
- 검증·배포 전 결과는 `34_google_oauth_public_samples_delivery.md`에 기록한다.

## 2026-07-18 — 배포 산출물·샘플 데이터셋 인벤토리

- 브랜치: `docs/public-artifact-inventory`
- 공개 화면, 내부 배포 문서, production RAG 적재 자료, 보류 데이터셋을 `docs/40_public_artifact_inventory.md`에 한 번에 추적하도록 정리했다.
- raw dataset과 vector store volume은 Git에 올리지 않고, 공개 화면에는 운영 secret·prompt 원문·내부 collection 세부를 노출하지 않는 경계를 함께 기록했다.

## 2026-07-18 — 벡터스토어 적재 문서 인벤토리 정정

- 브랜치: `docs/vectorstore-document-inventory`
- `docs/40_public_artifact_inventory.md`의 범위를 공개 산출물 목록에서 Chroma collection에 실제 적재되는 문서·row 목록으로 정정했다.
- `hate_speech_definitions`의 내부 taxonomy 23건, K-HATERS README chunk 8건과 `hate_speech_examples`의 K-HATERS train row 172,157건을 doc id 패턴, source file, loader 코드와 함께 기록했다.

## 2026-07-18 — 공식·권위 RAG 문서 후보 기록

- 브랜치: `docs/authoritative-rag-sources`
- 내부 taxonomy가 definition collection을 과도하게 지배할 때 생길 수 있는 기준 순환, 권위 근거 부족, recall 편향, 감사 어려움을 기록했다.
- 국가인권위원회, YouTube 정책, OHCHR Rabat Plan of Action을 공식·권위 definition source 후보로 추가하고, source type별 균형 retrieval 보강 방향을 문서화했다.

## 2026-07-18 — 3분리 RAG vector store 구현

- 브랜치: `feat/three-vector-rag`
- Chroma collection을 `hate_speech_taxonomy`, `hate_speech_authoritative`, `hate_speech_examples`로 분리하고 retriever가 query embedding 1회로 세 collection을 독립 조회하도록 변경했다.
- prompt version을 `category-rag-v0.3.1`로 올리고 `taxonomy_context`, `authoritative_context`, `example_context`를 명시적으로 분리했다.
- bootstrap summary, worker analysis config, admin settings, vector store inventory와 재현성 문서를 새 구조 기준으로 갱신했다.

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

### `feat/reporting-operations`

- 범위: 댓글 작성자 네트워크, report snapshot, 상세 API, HTML 화면, HTML/Excel export, 관리자 API
- 주요 결정:
  - 작성자 채널 ID가 없으면 comment snapshot UUID 기반 익명 node key를 사용한다.
  - 자기 답글 edge를 제거하지 않고 summary에 별도 집계한다.
  - report snapshot은 생성 후 수정하지 않으며 재분석 시 새 snapshot을 만든다.
  - export 파일 경로는 설정된 storage root 내부로 제한한다.
  - 관리자 token은 constant-time 비교하고 설정 API에는 secret 존재 여부만 노출한다.
- 검증:
  - node/edge/degree와 혐오 비율 계산
  - report summary, 대표 사례, 부분 실패 표시
  - 댓글/스크립트 pagination·filter와 network API
  - HTML escaping 및 Excel 5개 sheet 생성
  - export 생성·상태·다운로드와 PDF 거부
  - 관리자 인증, 설정 masking, retry 상태 전이, log/quota 조회
  - 전체 회귀 `uv run pytest -q`
- 결과: diff, Ruff, compileall 통과, reporting/export/admin 포함 테스트 59개 통과

## 외부 검증 결과

2026-07-14에 YouTube, Anthropic, Upstage 실제 키를 사용한 production Compose 검증을 완료했다. 제한 corpus 적재, dual retrieval, 정상/댓글 비활성/자막 없음 job, HTML/XLSX, 관리자 API, secret scan의 상세 증적은 `docs/17_live_validation_evidence.md`에 기록한다.

### `feat/predeploy-hardening`

- 범위: 불변 migration, Docker image, dev/test/prod Compose, CI, production 설정 검증, 보안 헤더, dependency audit, 운영 runbook
- 주요 결정:
  - production은 PostgreSQL, production pipeline, 변경된 관리자 token을 강제한다.
  - web/worker는 non-root로 실행하고 named volume ownership은 일회성 `init-volumes`가 설정한다.
  - migration 컨테이너에는 DB URL만 전달하고 YouTube/LLM/embedding secret은 전달하지 않는다.
  - Chroma HTTP server는 실행하지 않으며 `PYSEC-2026-311`의 도달 불가능 조건과 제거 기준을 `SECURITY.md`에 기록한다.
- 검증:
  - SQLite와 PostgreSQL 16 migration upgrade/downgrade/upgrade
  - runtime image build와 container health smoke test
  - dev/test/prod Compose config
  - PostgreSQL + web + worker fake pipeline job/report E2E
  - container XLSX export와 관리자 secret masking
  - Ruff, compileall, pytest, pip-audit gate
- 결과: diff, Ruff, compileall 통과, 테스트 61개 통과; dependency audit는 문서화된 Chroma server 비도달 예외 1건 외 통과; PostgreSQL migration 왕복, runtime image, Compose fake E2E, XLSX export 검증 통과

### `chore/live-e2e-validation`

- 범위: 실제 정상/댓글 비활성/자막 없음 E2E runner, HTML/XLSX 검증, admin/secret scan, RAG 3회 안정성 지표
- 자동 검증: mock HTTP contract, batch ingest, prompt v0.2, similarity gate, repeat evaluator 테스트 통과
- 외부 검증: 제한 K-HATERS corpus와 실제 YouTube/Anthropic/Upstage production E2E 통과
- RAG 교정: example 본문/라벨 전달 누락 수정, `example_min_similarity=0.40` 적용 후 합성 smoke 15/15 성공·정확도/F1/안정성 1.000
- 최종 게이트: Ruff, compileall, pytest 69개, dependency audit, dev/test/prod Compose config 통과
- 증적: `docs/17_live_validation_evidence.md`

### `fix/swagger-docs-csp`

- 범위: `/docs`, `/redoc`, OAuth redirect에만 Swagger CDN script/style CSP 허용
- 원인: 전역 CSP가 FastAPI Swagger UI의 `cdn.jsdelivr.net` script를 차단해 빈 화면 발생
- 보안 경계: 일반 API와 보고서 응답의 기존 strict CSP는 유지
- 검증: docs HTML asset URL과 route별 CSP 회귀 테스트, 실제 컨테이너 `/docs` 확인
# 2026-07-15 Stitch 프론트엔드 구현

- 브랜치: `feat/stitch-frontend`
- Stitch MCP에서 `YouTube Hate Speech Analyzer`의 분석 요청, 상태, 이력, 보고서 화면과 VoxGuard 디자인 시스템을 읽었다.
- 별도 React/Vite 프론트와 개발/배포 Docker target을 추가했다.
- 프론트의 분석 요청, job polling, 브라우저 이력, report, HTML/XLSX export를 FastAPI에 연결했다.
- 개발 Vite proxy와 배포 Nginx reverse proxy를 구성해 별도 CORS 허용 없이 동일 출처로 통신한다.
- 상세 작업 시퀀스와 검증 증적은 `docs/18_stitch_frontend_delivery.md`에 기록했다.

# 2026-07-15 production 댓글 수집 모드 및 secret 로그 점검

- 브랜치: `fix/http-client-secret-logging`
- 댓글 0건의 원인이 API 키 누락이 아니라 로컬 `.env`의 `PIPELINE_MODE` 미설정에 따른 `fake` 기본값임을 확인했다.
- 로컬 실행 설정을 `PIPELINE_MODE=production`으로 전환하고 web/worker 모두 production handler를 사용하도록 재기동했다.
- YouTube commentThreads API가 대상 영상에서 댓글을 반환함을 확인했다.
- HTTP client INFO 로그가 query string의 API 키를 출력할 수 있어 `httpx`와 `httpcore` 로그 레벨을 WARNING으로 제한했다.
- 실제 값이 로그에 한 번 노출된 YouTube API 키는 교체 후 새 분석을 실행해야 한다.

# 2026-07-15 프론트 hero 줄바꿈 교정

- 브랜치: `fix/hero-line-breaks`
- 분석 요청 화면 제목을 `YouTube 영상`과 `혐오표현 분석` 두 줄로 고정했다.
- 설명 문구도 쉼표 뒤에서 두 줄로 고정해 화면 폭에 따른 어색한 단어 단위 줄바꿈을 제거했다.

# 2026-07-15 RAG 방법론 페이지

- 브랜치: `feat/rag-methodology-page`
- Stitch MCP의 기존 `YouTube Hate Speech Analyzer` 프로젝트와 VoxGuard 디자인 시스템을 기준으로 `RAG 방법론 & 재현성` 화면을 먼저 설계했다.
- Stitch 화면 ID: `b8156a72574e4f94890af9a0e8ec63bf`
- `/rag-methodology`에 호출 파이프라인, dual-vector 검색, 프롬프트 구조, 실행 설정, 검증 규칙, 재현 체크리스트를 구현했다.
- 데스크톱 사이드바와 상단 메뉴에 진입점을 추가하고, 모바일 전용 메뉴 및 단일 열 레이아웃을 추가했다.
- 정적 렌더링 회귀 테스트, Vitest 전체 테스트, TypeScript/Vite production build, 1440px/500px 브라우저 렌더링을 검증했다.

# 2026-07-15 RAG 재현성 문서

- 브랜치: `docs/rag-reproducibility`
- 현재 구현을 기준으로 API/worker 실행 경계, item별 동기 호출, dual-vector 검색과 degraded mode를 문서화했다.
- system/user prompt, output contract, validation과 단일 retry를 재현 가능한 형태로 기록했다.
- corpus/license/embedding 구성, run/item provenance, 실험 명령, 결정성 한계와 점검표를 추가했다.
- runtime 상수와 문서의 핵심 식별자가 함께 변경되는지 확인하는 회귀 테스트를 추가했다.
- 검증: diff check, Ruff, compileall, backend 72개 테스트, frontend 3개 테스트와 production build, dev/test/prod Compose config 통과.

# 2026-07-15 RAG job 진행률 및 저장 실패 교정

- 브랜치: `feat/rag-job-progress`
- production worker와 같은 설정의 Anthropic 최소 호출에서 input 36/output 13 token 사용을 확인했다.
- 대상 job의 댓글 404건 rollback 원인이 64자를 넘은 `hate_type`의 PostgreSQL 저장 실패임을 확인하고 컬럼을 `TEXT`로 변경했다.
- 댓글·자막 item 진행률을 별도 atomic transaction으로 저장하고 job API, 단계 목록, live process log에 노출했다.
- 기존 job은 확인 가능한 수집 총량과 legacy counter 안내를 표시하도록 했다.
- 예상하지 못한 worker step 예외에 traceback 로깅을 추가했다.
- 상세 진단과 동시 처리 확장 경계는 `docs/20_rag_job_progress_diagnosis.md`에 기록했다.
- 검증: diff check, Ruff, compileall, backend 74개 테스트, frontend 4개 테스트와 production build, SQLite/PostgreSQL migration 왕복, dev/test/prod Compose config, 대상 jobs 화면 브라우저 렌더링 통과.
- 개발 PostgreSQL을 migration head로 올리고 새 progress reporter가 포함된 worker를 재빌드·재기동했다. 비용이 발생하는 대상 영상 재분석은 자동 실행하지 않았다.

# 2026-07-15 RAG 방법론 가독성 개선

- 브랜치: `style/rag-methodology-readability`
- 방법론 화면의 제목, 본문, code, 설정표, validation, 체크리스트 글자 크기와 행간을 확대했다.
- 데스크톱 파이프라인과 재현 체크리스트를 4/3열에서 2열로 완화해 확대된 텍스트가 겹치지 않도록 했다.
- 모바일은 단일 열 구조를 유지하고 제목 크기를 확대했다.
- 검증: frontend 4개 테스트, TypeScript/Vite production build, 1440px/500px 브라우저 렌더링 통과.

# 2026-07-15 Worker stale job 자동 회수

- 브랜치: `fix/stale-job-recovery`
- 중단된 job `ca375d25-3fd7-470f-a6de-eb4f6671a2d6`과 비-cascade operation/quota 기록을 transaction으로 삭제했다.
- 사용되지 않던 `WORKER_STALE_AFTER_SECONDS`를 worker claim 경로에 연결했다.
- step heartbeat와 RAG item별 갱신을 추가하고 stale step만 같은 job에서 재실행하도록 했다.
- active heartbeat는 회수하지 않고 recovery attempt와 operation log를 보존한다.
- 상세 동작과 향후 분산 처리 경계는 `docs/21_stale_job_recovery.md`에 기록했다.
- 검증: diff check, Ruff, compileall, backend 76개 테스트, SQLite/PostgreSQL migration 왕복, dev/test/prod Compose config 통과.
- 개발 PostgreSQL을 heartbeat migration head로 올리고 stale recovery 설정과 코드가 포함된 worker를 재빌드·재기동했다.

# 2026-07-15 RAG 병렬 처리 계획

- 브랜치: `docs/rag-parallel-processing-plan`
- 현재 순차 RAG loop, 단일 SQLAlchemy session, 원자 증가 progress counter와 stale step recovery의 병렬화 제약을 확인했다.
- item ledger, lease token, idempotent result persistence와 terminal item 기반 progress projection을 병렬 실행의 선행 조건으로 정했다.
- 동기 provider adapter에 맞춘 bounded thread executor, provider별 concurrency gate, 429 backoff와 sequential rollback 경로를 단계화했다.
- 최초 계획에는 단일 worker 병렬화 뒤 여러 worker 분산 claim으로 확장하는 범위도 포함했다. 아래 범위 교정에서 사용자 요구에 맞게 제거했다.
- 검증: diff check, 문서 교차 참조, job progress/pipeline 회귀 테스트 6개 통과.

# 2026-07-15 RAG 병렬 처리 범위 교정

- 브랜치: `docs/scope-rag-intra-job-parallelism`
- 기존 job 비동기 처리 안에서 `analyze_comments`, `analyze_script`의 RAG item 호출만 병렬화하는 것으로 범위를 고정했다.
- 여러 worker의 item 분산 claim, RAG 전용 queue/service와 별도 item lease table을 계획에서 제거했다.
- 기존 결과 unique constraint를 재시작 checkpoint로 사용하고, thread는 외부 호출만 수행하며 coordinator가 item별 짧은 transaction으로 저장하도록 단순화했다.
- RAG가 아닌 pipeline step은 계속 순차 실행하고, 모든 RAG future의 결과 저장이 끝난 뒤에만 다음 step으로 이동하도록 성공 기준을 보강했다.
- 검증: diff check, 범위 문구 교차 확인, job progress/pipeline 회귀 테스트 6개 통과.

# 2026-07-15 RAG 병렬 처리 효율 계획 보강

- 브랜치: `docs/refine-rag-parallel-efficiency`
- 사용자 수용에 따라 병렬화 전에 동일 query embedding을 dual collection에 재사용하고 외부 client 연결을 재사용하는 단계를 추가했다.
- item 결과의 실제 insert와 progress 증가를 같은 transaction으로 묶고, step 시작·종료 때만 전체 결과와 재조정하도록 DB 작업량을 제한했다.
- baseline, retrieval 중복 제거, item checkpoint, bounded parallelism, provider rollout 순서로 구현 단계를 재배치했다.
- item 950개 기준 embedding 호출 1,900회에서 950회로 감소, classifier 생명주기당 client 1회 생성이라는 정량 검증 기준을 추가했다.
- 검증: diff check, 단계·정량 기준 교차 확인, job progress/pipeline 회귀 테스트 6개 통과.

# 2026-07-15 RAG 병렬 처리 기술 구현안

- 브랜치: `docs/rag-parallel-technical-design`
- 현재 Settings, worker/orchestrator, analyzer, progress, 결과 unique constraint, Chroma 1.5.9와 SQLAlchemy 2.0.51 계약을 기준으로 세부 설계를 작성했다.
- dual retriever, classifier pool, bounded coordinator, result store와 attempt fencing의 인터페이스 및 transaction 순서를 정의했다.
- provider gate/retry, SIGTERM drain, jobs 진행 로그, 기존 job 호환과 sequential rollback 방식을 확정했다.
- 구현을 retrieval 재사용, item checkpoint, job 내부 병렬화, provider backpressure 네 브랜치로 나누고 단계별 merge gate를 기록했다.
- 검증: diff check, 문서 교차 참조와 code fence 확인, 현재 job/RAG/embedding/vector store 회귀 테스트 17개 통과.

# 2026-07-15 RAG dual retrieval 재사용 구현

- 브랜치: `perf/rag-dual-retrieval-reuse`
- query embedding 1회 재사용, 장기 provider/Chroma client 생명주기와 worker resource 정리를 구현했다.
- 상세 변경과 검증은 `docs/24_rag_parallel_delivery.md`에 누적 기록한다.
- 검증: diff check, Ruff, compileall, 집중 테스트 14개와 backend 전체 테스트 79개 통과.

# 2026-07-15 RAG item checkpoint와 fencing 구현

- 브랜치: `feat/rag-item-checkpoints`
- item별 멱등 결과 저장, progress atomic update/reconcile, 누락 item resume와 stale attempt fencing을 구현했다.
- SQLite 집중 테스트와 실제 개발 PostgreSQL의 동시 duplicate insert race를 검증했다.
- 검증: diff check, Ruff, compileall, 집중 테스트 11개, PostgreSQL integration 1개, backend 전체 테스트 82개 통과(기본 opt-in 1개 skip).

# 2026-07-15 Job 내부 RAG bounded parallelism 구현

- 브랜치: `feat/rag-intra-job-parallelism`
- classifier pool, bounded executor, 동일 sequential rollback 경로와 signal 기반 step release를 구현했다.
- RAG 실행 모드/item 동시성/heartbeat/timeout을 환경과 runtime에 연결하고 run provenance에 기록했다. provider gate/retry는 다음 구현 단계로 남겼다.
- 검증: diff check, Ruff, compileall, 집중 테스트 21개, dev/test/prod Compose config, backend 전체 테스트 87개 통과(기본 opt-in 1개 skip).

# 2026-07-15 RAG provider backpressure와 관측성 구현

- 브랜치: `feat/rag-provider-backpressure`
- Upstage/Anthropic별 semaphore, retry 분류, `Retry-After`/backoff와 stop-aware retry를 구현했다.
- RAG 진행 상황, provider retry와 token usage를 throttled operation log로 저장했다.
- 검증: diff check, Ruff, compileall, 집중 테스트 26개, dev/test/prod Compose config, backend 전체 테스트 94개 통과(기본 opt-in 1개 skip).

# 2026-07-15 RAG 병렬 처리 배포 전 통합 검증

- 브랜치: `chore/rag-parallel-predeploy-validation`
- 개발 worker image를 재빌드하고 `parallel`, item/Upstage/Anthropic 동시성 2가 container에 적용됐는지 확인했다.
- 실제 Upstage/Anthropic 병렬 smoke 2건이 모두 성공했으며 input 3,662/output 445 token과 provider retry 0회를 확인했다.
- 실행 중인 worker와 공유 PostgreSQL 통합 테스트의 job claim 경합을 별도 `test/rag-postgres-worker-isolation` 브랜치에서 격리하고 병합했다.
- 검증: diff check, Ruff, compileall, dev/test/prod Compose config, backend 전체 테스트 94개 통과(기본 opt-in 1개 skip), 실제 PostgreSQL duplicate insert race 1개 통과, worker container 정상 기동.
- 외부 환경 배포와 트래픽 전환 직전 단계에서 종료했다.

# 2026-07-16 상호작용 댓글 네트워크

- 브랜치: `feat/interactive-comment-network`
- 보고서의 정적 네트워크 플레이스홀더를 실제 `/api/reports/{id}/network` node/edge 데이터로 교체했다.
- Cytoscape.js CoSE layout으로 node drag, pan, zoom, fit, relayout과 node 상세 panel을 구현했다.
- 혐오표현 포함 node/edge를 구분하고 연결 중심/전체 node 전환으로 고립 작성자가 많은 그래프의 가독성을 확보했다.
- 그래프 엔진을 dynamic import해 일반 화면의 초기 bundle과 분리했다.
- 상세 설계와 검증 증적은 `docs/25_interactive_comment_network.md`에 기록했다.

# 2026-07-16 보고서 카테고리 한국어 표시

- 브랜치: `feat/korean-category-labels`
- API와 저장소의 13개 canonical 영문 category code는 변경하지 않고 보고서 표시 계층에만 한국어 label을 적용했다.
- 카테고리 분포와 대표 탐지 사례가 같은 공통 mapping을 사용하도록 했다.
- RAG 방법론의 prompt contract code는 재현성을 위해 영문을 유지했다.
- 알 수 없는 미래 category는 원본 code를 포함한 한국어 fallback으로 표시해 데이터 손실을 막았다.

# 2026-07-16 전체 혐오 댓글 좋아요순 표시

- 브랜치: `feat/all-hate-comments-by-likes`
- 보고서 snapshot의 대표 5건 대신 comments API에서 전체 혐오 댓글을 조회하도록 변경했다.
- comments API에 `sort=like_count`와 응답 `total`을 추가해 좋아요 내림차순과 안정적인 offset pagination을 제공했다.
- 프론트는 최대 200건씩 불러와 scroll 목록으로 표시하고 초과 데이터는 이어서 불러온다.
- canonical category의 한국어 표시와 빈 목록·오류·loading 상태를 유지했다.
- 검증: 실제 보고서 66/66건과 상위 좋아요 232→155→65→53→45 확인, frontend 10개·backend 95개 테스트, Ruff, compileall, dev/test/prod Compose config와 production frontend image build 통과.

# 2026-07-16 보고서 레이아웃과 History 썸네일

- 브랜치: `feat/report-layout-history-thumbnails`
- 카테고리 분포와 전체 혐오 댓글 panel 높이를 고정해 같은 높이로 맞췄다.
- 카테고리 label/count 글자 크기를 키우고 7개 이하는 그대로, 8개 이상은 category 영역에만 scroll을 적용했다.
- History가 완료 job의 report를 조회해 실제 YouTube thumbnail과 영상 제목을 표시하도록 수정했다.

# 2026-07-16 네트워크 전체 지표와 edge 상세

- 브랜치: `feat/network-metrics-edge-details`
- 네트워크 영역의 좌측 1/3에 전체/연결/고립 작성자, 답글·혐오 관계, 평균 차수와 방향 밀도를 표시했다.
- 같은 source/target의 답글 edge를 집계해 빈도에 따라 굵기를 조절하고 혐오 포함 edge를 구분했다.
- edge 선택 시 작성자 방향, 답글 빈도, 혐오 답글 수·비율과 실제 선 굵기를 표시하도록 했다.

# 2026-07-16 한국어 분석 사유와 Excel 표시

- 브랜치: `feat/korean-reasoning-excel`
- RAG prompt를 `category-rag-v0.3.0`으로 올리고 `reasoning`을 1~2문장 한국어 보고서 요약으로 생성하도록 명시했다.
- validator가 한글 없는 `reasoning`을 거부해 기존 분류 재시도 경로로 보내도록 했다.
- Excel 댓글·자막 sheet의 `reasoning` 열 제목을 `분석 사유`로 변경했다.
- 기존 저장 결과는 원문 보존을 위해 소급 번역하지 않으며 변경 이후 분석부터 한국어 계약을 적용한다.

# 2026-07-17 문장 경계 우선 자막 분석 노출

- 브랜치: `feat/sentence-aware-script-report`
- 자막 cue에 문장 종결부호가 있으면 segment 경계로 우선하고, 없으면 기존 45초·800자 상한을 fallback으로 유지했다.
- 보고서에 시간순 자막, 판정 상태, 한국어 카테고리, 분석 사유와 pagination을 노출했다.
- 기존 segment/API/DB 계약을 유지해 과거 보고서도 표시하며, 새 분할 규칙은 신규 job부터 적용된다.
- 상세 설계·순서·검증 기준은 `docs/32_sentence_aware_script_report.md`에 기록했다.
- 검증: backend 102 passed/1 skipped, frontend 13 passed, Ruff·compileall·Compose config·production image build 통과.

# 2026-07-16 RAG 사회과학적 함의와 해석 경계

- 브랜치: `feat/rag-social-science-implications`
- 방법론 화면에 발화 단위, 개념 조작화, 관계적 맥락과 RAG 근거의 사회과학적 역할을 추가했다.
- 혐오 비율·category 분포·network 지표·RAG 근거별로 허용되는 해석과 금지되는 주장을 대응시켰다.
- 구성타당도, 선택 편향, 차별적 측정 오차, 시간 비교, 인과관계와 연구 윤리의 한계를 문서와 화면에 동일하게 반영했다.
- 현재 RAG item 병렬 실행 계약과 재현 문서에 남아 있던 과거 순차 실행 설명을 실제 구현에 맞게 수정했다.

# 2026-07-16 보고서·RAG 개선 배포 전 통합 검증

- 브랜치: `chore/report-analysis-predeploy-validation`
- Ruff, compileall, backend 전체 `96 passed, 1 skipped`, frontend `11 passed`와 production build를 통과했다.
- dev/test/prod Compose 정합성을 확인하고 개발 frontend/web/worker를 새 이미지로 재생성했다.
- 실제 Upstage+Anthropic 호출에서 prompt v0.3.0, 한국어 사유, validator 통과를 확인했다.
- 실제 XLSX의 두 `분석 사유` header와 브라우저 History의 실제 thumbnail/title을 확인했다.
- 상세 요구사항 대응과 검증 증적은 `docs/26_report_analysis_predeploy_validation.md`에 기록했다.

# 2026-07-16 Figma 기반 RAG 호출 흐름도

- 브랜치: `feat/figma-rag-pipeline-flowchart`
- Figma MCP로 비동기 Job, item 병렬 RAG, 집계·보고서의 세 phase FigJam flowchart를 설계했다.
- 기존 8개 card 나열을 실제 fan-out/fan-in, similarity 분기, JSON validation과 교정 retry, 부분 성공 합류가 보이는 SVG로 교체했다.
- 데스크톱은 전체 흐름을 한 번에 표시하고 모바일은 글자 크기를 유지한 채 diagram 영역만 좌우 이동하도록 했다.
- FigJam 원본과 코드 대응, 도형·edge 의미는 `docs/27_figma_rag_pipeline_flowchart.md`에 기록했다.

# 2026-07-16 사용자 수정 FigJam 동기화

- 브랜치: `feat/sync-refined-figjam-rag-flow`
- 사용자가 재배치한 동일 FigJam root를 다시 읽고 store 순서와 validation retry 흐름의 차이를 확인했다.
- 사례 Store와 similarity gate를 상단 우선 경로로, 정의 Store를 독립 합류 경로로 옮겼다.
- 재시도 판단, 교정 Prompt, Claude 재호출을 수정본과 같은 읽기 순서로 재배치하고 실제 화면을 재검증했다.

# 2026-07-16 상세 Taxonomy v0.3

- 브랜치: `feat/detailed-taxonomy-v03`
- 13개 category를 정의, 포함·제외 기준, 인접 경계, 검색 cue를 가진 구조화 card로 확장했다.
- 공통 hate threshold, 인용·풍자 예외, 정치적 2축, 복수 선택, `hate_type`, `target_group`을 포함해 내부 taxonomy를 규칙 10개 + category 13개로 구성했다.
- `no_target` 충돌을 validator에서 강제하고 새 run이 taxonomy version을 저장하도록 했다.
- RAG 방법론 화면과 기준 문서에 13개 상세 판정 가이드를 공개했다.
- corpus reset 중 발견한 공백-only example을 loader에서 제외하고 production collection 재생성 절차를 검증했다.
- 상세 작업 순서와 검증 증적은 `docs/28_detailed_taxonomy_v03.md`에 기록했다.

# 2026-07-16 Upstage Embed 2 전환 사전 문서화

- 브랜치: `feat/detailed-taxonomy-v03`
- legacy Embed의 2026-08-31 UTC 종료, USD 0.10/1M token과 Embed 2의 2026-07-20 UTC까지 무료·이후 USD 0.02/1M token 정책을 Upstage 공식 가격표로 확인했다.
- 진행 중이던 legacy 전체 vector 적재를 중단하고, RAG 방법론 화면에 비용·종료 일정과 migration gate를 추가했다.
- model ID/API 계약 확인, 고정 평가셋 비교, 별도 collection 전량 재색인, blue/green 전환과 rollback 보존을 후속 순서로 명시했다.
- 서로 다른 embedding model의 vector를 같은 collection에 혼합하지 않는 것을 정합성 원칙으로 고정했다.

# 2026-07-17 Upstage Embed 2 전환 완료

- 브랜치: `feat/upstage-embed2-migration`
- production 기본 model을 `embedding`으로, endpoint를 `https://api.upstage.ai/v1/embeddings`로 변경하고 passage/query alias를 용도별로 적용했다.
- worker를 중지한 뒤 definition 31건과 example 172,157건을 4096차원 Embed 2 vector로 전량 재색인했으며 background container의 exit code 0을 확인했다.
- collection metadata/count와 정치 공동체·정체성·대상 없는 욕설 검색 smoke를 검증했다.
- 실제 Upstage 검색과 Anthropic 분류를 연결해 `rag_context_status=complete`, output schema, 한국어 reasoning을 확인했다.
- backend 99 passed/1 skipped, frontend 11 passed와 production build를 통과한 뒤 worker를 Embed 2 설정으로 재빌드·재기동했다.
- 실행 순서와 완료 증적은 `docs/29_embed2_background_reindex.md`에 기록했다.

# 2026-07-17 Google OAuth/BYOK 설계 정합성

- 브랜치: `docs/google-oauth-byok-consistency`
- Google OAuth, DB session, 사용자별 Anthropic/Upstage BYOK와 Fernet 암호화 계약을 `docs/30_auth_oauth_byok.md`에 구체화했다.
- 프로젝트 범위, HLD, data model, API, backend 설계, 구현 계획, 결정 로그, Docker 환경과 배포 전 runbook의 필드·경로·오류 코드·환경변수를 동일 계약으로 맞췄다.
- `GET /api/admin/settings` 예시의 LLM provider를 실제 기본값인 `anthropic`으로 바로잡았다.
- 이 변경은 구현 전 설계 문서 확정이며 실제 OAuth endpoint와 migration은 후속 구현 브랜치에서 추가한다.

# 2026-07-17 공개 개발 표면 비노출

- 브랜치: `harden/public-developer-surfaces`
- Swagger, ReDoc, OpenAPI schema는 기본 비활성화하고 production에서는 설정값과 관계없이 생성하지 않도록 했다.
- public frontend에서 RAG 방법론 route와 navigation, Swagger와 readiness 링크를 제거했다.
- 내부 RAG 방법론 문서와 frontend source는 개발·감사 자료로 유지하지만 production bundle과 public route에서는 제외한다.
- backend 101 passed/1 skipped, frontend 12 passed, production build와 bundle 개발 문자열 검사를 통과했다.
- 설정, 테스트, production bundle 문자열 검사와 배포 전 확인 절차는 `docs/31_public_surface_hardening.md`에 기록했다.

# 2026-07-17 공개 RAG 포트폴리오 화면 복원

- 브랜치: `feat/public-rag-portfolio-page`
- 사용자 피드백에 따라 `/rag-methodology` route와 navigation을 복원했다.
- Dual-vector 근거 결합, 판정·검증 흐름, 13개 taxonomy, 사회과학적 함의와 타당도 한계는 포트폴리오 정보로 유지했다.
- embedding migration·가격·종료 일정, 모델 ID, prompt 원문, collection 이름, 검색 수치, 오류 코드와 내부 FigJam 링크는 공개 화면에서 제거했다.
- Swagger/ReDoc/OpenAPI의 기본 및 production 비노출 정책은 유지했다.

# 2026-07-17 보고서 카테고리 목록 높이 정렬

- 브랜치: `style/report-category-list-fill-panel`
- 카테고리 분포 패널을 세로 flex layout으로 바꾸고 목록이 패널의 남은 높이를 채우도록 했다.
- 7개 이하 항목은 상단부터 스크롤 없이 표시하고, 8개 이상일 때만 확장된 목록 영역에서 세로 스크롤을 사용한다.

# 2026-07-17 Google 로그인 전 공개 샘플 Stitch 설계

- 브랜치: `design/prelogin-public-samples`
- 문서에만 있던 비로그인 공개 샘플 흐름이 실제 frontend/backend에는 없음을 확인했다.
- 기존 Stitch project와 VoxGuard design system에 desktop 공개 랜딩·샘플 탐색 화면을 생성했다.
- 초안에 생성된 영문 메뉴, API Documentation, 가상 회사명, 2024 표기를 제거하고 한국어 용어·해석 경계·2026 푸터로 수정했다.
- 390px single-column, 44px touch target을 기준으로 mobile 스크린을 별도 생성했다.
- Stitch의 가상 샘플은 layout 참조로만 사용하고, 실제 구현은 운영자가 검토해 `is_public_sample=true`로 지정한 report만 API에서 표시하도록 계약을 고정했다.
- 화면 ID·권한 경계·data contract·후속 구현 순서는 `docs/33_prelogin_public_samples_stitch.md`에 기록했다.

# 2026-07-17 HateScope 메인·공개 샘플 전환

- 브랜치: `feat/hatescope-home-public-sample`
- 기존 `/analyze` 분석 UI를 `/` 메인으로 옮기고 `/analyze`는 호환 리다이렉트로 유지했다.
- 공개 샘플 랜딩을 `/samples`로 분리하고, 로그인된 경우 Google 로그인 버튼 대신 계정명·설정 링크·로그아웃 버튼을 표시했다.
- 사용자 노출 브랜드와 frontend package 이름을 `SENTINEL-YT`에서 `HateScope`로 변경했다. DB·쿠키·CSRF header·Docker project/volume 같은 호환성 식별자는 유지했다.
- `lecielgris1@gmail.com`의 Anthropic·Upstage BYOK로 영상 `hIwABxM30Ds`를 새로 분석하고, 완료 보고서를 공개 샘플로 지정하는 절차를 수행했다.
- 상세 실행·검증 증적은 `docs/38_hatescope_home_public_sample_delivery.md`에 기록한다.

# 2026-07-17 댓글 RAG 근거 공개와 다국어 corpus 사전 감사

- 브랜치: `feat/comment-evidence-corpus-audit`
- 전체 혐오 댓글 card를 클릭하면 한국어 분석 사유, 공격 대상·표현 유형·RAG 상태, 결과에 기록된 사례·정의 문서 ID를 펼쳐 볼 수 있게 했다.
- 실제 production Chroma의 정의 31건과 사례 172,157건을 읽기 전용으로 전수 집계했다.
- 한국어 서비스에는 조건부 사용 가능하지만 영어 입력 분석에는 부적합하다고 판정했다. 언어 metadata, K-HATERS label mapping, source 다양성, citation 검증과 CC-BY attribution을 다국어 구현 계획의 선행 gate로 고정했다.
- 상세 수치·판정·후속 계획 작성 조건은 `docs/39_comment_evidence_multilingual_corpus_audit.md`에 기록했다.
