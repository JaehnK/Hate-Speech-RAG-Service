# Railway 배포 역할 분담 체크리스트

## 작업 계약

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-07-18 |
| 브랜치 | `docs/railway-deploy-checklist` |
| 기준 배포 | 한국어판 HateScope |
| 목적 | Railway 웹 작업과 Codex 작업을 분리해 배포 직전 누락을 줄인다 |

## 0. 배포 범위 고정

- [ ] 한국어판 분석만 이번 배포 범위로 둔다.
- [ ] 영문 분석은 이번 배포에서 제외한다.
- [ ] 분석 사유, report, Excel의 주요 설명은 한국어 기준으로 유지한다.
- [ ] 영어 댓글·영어 자막이 들어오더라도 영어권 분석 품질을 보장한다고 표시하지 않는다.

담당: Codex 문서화, 사용자 최종 승인

## 1. Codex가 먼저 준비할 항목

### 1.1 코드·문서 정합성

- [ ] `docs/44_korean_railway_predeploy_plan.md` 기준으로 배포 범위를 재확인한다.
- [ ] README와 runbook의 실행 명령이 현재 코드와 맞는지 확인한다.
- [ ] production에서 Swagger surface가 닫히는지 확인한다.
- [ ] Google OAuth/BYOK 문서와 실제 endpoint가 어긋나지 않는지 확인한다.
- [ ] JWT를 쓰지 않고 opaque server session을 쓰는 정책을 유지한다.

### 1.2 Railway 실행 명령 정리

- [ ] `web` service start command를 확정한다.
- [ ] `worker` service start command를 확정한다.
- [ ] `frontend` service build/start 방식을 확정한다.
- [ ] `migrate` one-shot command를 확정한다.
- [ ] `corpus` one-shot command를 확정한다.

초안:

```bash
# web
uvicorn app.main:app --host 0.0.0.0 --port ${PORT}

# worker
python -m app.worker_main

# migrate
alembic upgrade head

# corpus
python -m scripts.bootstrap_corpus --persist-directory $CHROMA_PERSIST_DIRECTORY --reset
```

### 1.3 환경변수 최종표 작성

- [ ] 필수 production 변수 목록을 확정한다.
- [ ] Railway 서비스별로 필요한 변수를 나눈다.
- [ ] 사용자 BYOK와 운영자 공용 key의 경계를 명시한다.
- [ ] `SESSION_COOKIE_DOMAIN`을 설정할지 생략할지 운영 도메인 기준으로 판단한다.

### 1.4 로컬/staging 검증

- [ ] `uv sync --frozen`
- [ ] `uv run ruff check app tests experiments scripts`
- [ ] `uv run python -m compileall -q app tests experiments scripts alembic`
- [ ] `uv run pytest -q`
- [ ] `uv run pip-audit --ignore-vuln PYSEC-2026-311`
- [ ] `cd frontend && npm ci`
- [ ] `cd frontend && npm run test`
- [ ] `cd frontend && npm run build`
- [ ] production `Settings()` validation smoke 통과
- [ ] `docker compose -f compose.yaml -f compose.prod.yaml config --quiet`

### 1.5 배포 후 검증 준비

- [ ] `/health` 확인 절차 준비
- [ ] Google 로그인 확인 절차 준비
- [ ] API key 등록/BYOK 확인 절차 준비
- [ ] job 생성/polling/report 확인 절차 준비
- [ ] 공개 sample 지정 절차 준비
- [ ] secret scan 확인 절차 준비

## 2. 사용자가 Railway 웹에서 해야 할 항목

### 2.1 프로젝트와 서비스 생성

- [ ] Railway 프로젝트를 생성한다.
- [ ] GitHub repository를 연결한다.
- [ ] Railway PostgreSQL service를 생성한다.
- [ ] backend `web` service를 생성한다.
- [ ] backend `worker` service를 생성한다.
- [ ] frontend service를 생성하거나 단일 도메인 serving 방식을 확정한다.
- [ ] Chroma 저장용 persistent volume을 생성한다.
- [ ] report export 저장용 persistent volume을 생성한다.

### 2.2 서비스별 command 설정

- [ ] `web` start command를 입력한다.
- [ ] `worker` start command를 입력한다.
- [ ] `frontend` build/start 설정을 입력한다.
- [ ] migration을 one-shot으로 실행할 수 있는 방법을 준비한다.
- [ ] corpus bootstrap을 one-shot으로 실행할 수 있는 방법을 준비한다.

### 2.3 환경변수/secret 입력

공통 production 변수:

- [ ] `APP_ENV=production`
- [ ] `PIPELINE_MODE=production`
- [ ] `API_DOCS_ENABLED=false`
- [ ] `DATABASE_URL=<Railway PostgreSQL URL>`
- [ ] `ADMIN_TOKEN=<strong random token>`
- [ ] `YOUTUBE_API_KEY=<server youtube api key>`
- [ ] `FRONTEND_ORIGIN=https://<운영도메인>`
- [ ] `GOOGLE_OAUTH_REDIRECT_URI=https://<운영도메인>/api/auth/google/callback`
- [ ] `SESSION_COOKIE_SECURE=true`
- [ ] `API_KEY_ENCRYPTION_KEY=<Fernet key>`
- [ ] `EMBEDDING_PROVIDER=upstage`
- [ ] `EMBEDDING_MODEL=embedding`
- [ ] `UPSTAGE_API_KEY=<bootstrap/fallback key>`
- [ ] `LLM_PROVIDER=anthropic`
- [ ] `LLM_MODEL=claude-haiku-4-5-20251001`
- [ ] `RAG_EXECUTION_MODE=parallel`
- [ ] `RAG_ITEM_CONCURRENCY=4`
- [ ] `RAG_EMBEDDING_CONCURRENCY=4`
- [ ] `RAG_LLM_CONCURRENCY=2`

Google OAuth:

- [ ] `GOOGLE_CLIENT_ID=<google oauth client id>`
- [ ] `GOOGLE_CLIENT_SECRET=<google oauth client secret>`

선택/도메인 구조에 따라 결정:

- [ ] `SESSION_COOKIE_DOMAIN=<필요 시만>`
- [ ] `REPORT_STORAGE_DIR=<Railway volume mount path>`
- [ ] `CHROMA_PERSIST_DIRECTORY=<Railway volume mount path>`
- [ ] frontend service를 별도 배포할 경우 `API_UPSTREAM=<backend web service URL>`

### 2.4 도메인과 OAuth 설정

- [ ] Railway public URL 또는 custom domain을 확정한다.
- [ ] HTTPS 접속이 되는지 확인한다.
- [ ] Google Cloud Console OAuth consent screen을 확인한다.
- [ ] Google OAuth redirect URI에 `https://<운영도메인>/api/auth/google/callback`을 등록한다.
- [ ] Railway의 `FRONTEND_ORIGIN`과 Google redirect URI가 같은 origin인지 확인한다.

### 2.5 one-shot 작업 실행

- [ ] Alembic migration을 실행한다.
- [ ] corpus bootstrap을 실행한다.
- [ ] Chroma volume이 재시작 후에도 유지되는지 확인한다.
- [ ] report storage volume이 web/worker 양쪽에서 접근되는지 확인한다.

## 3. 함께 확인할 배포 후 E2E

### 3.1 기본 health/auth

- [ ] `GET /health`가 성공한다.
- [ ] `/docs`가 production에서 열리지 않는다.
- [ ] `/redoc`이 production에서 열리지 않는다.
- [ ] `/openapi.json`이 production에서 열리지 않는다.
- [ ] Google 로그인 버튼이 정상 동작한다.
- [ ] OAuth callback 후 `hsr_session` 쿠키가 발급된다.
- [ ] 로그아웃 후 같은 세션으로 인증 요청이 실패한다.

### 3.2 BYOK

- [ ] 로그인한 계정에서 Anthropic key를 등록한다.
- [ ] 로그인한 계정에서 Upstage key를 등록한다.
- [ ] 잘못된 key 등록 시 저장되지 않고 오류가 뜬다.
- [ ] 등록된 key 응답에는 fingerprint만 표시된다.
- [ ] DB, 로그, report, export에 key 원문이 노출되지 않는다.

### 3.3 분석 job

- [ ] 댓글과 공개 자막이 있는 영상으로 job을 생성한다.
- [ ] job page에서 댓글 RAG 진행 수가 표시된다.
- [ ] job page에서 자막 RAG 진행 수가 표시된다.
- [ ] job이 완료되면 report 링크가 표시된다.
- [ ] 댓글 비활성 영상은 partial success로 처리된다.
- [ ] 자막 없는 영상은 partial success로 처리된다.

### 3.4 report

- [ ] category 분포가 한국어 label로 표시된다.
- [ ] 전체 혐오 댓글 목록이 좋아요 순으로 표시된다.
- [ ] 댓글 card를 펼치면 한국어 분석 근거가 보인다.
- [ ] 댓글 네트워크 그래프가 표시된다.
- [ ] node 클릭 정보가 표시된다.
- [ ] edge 클릭 정보가 표시된다.
- [ ] HTML export가 생성된다.
- [ ] XLSX export가 생성된다.
- [ ] XLSX의 분석 사유가 한국어로 표시된다.

### 3.5 공개 sample과 권한

- [ ] 운영자가 검토한 report만 공개 sample로 지정한다.
- [ ] 로그아웃 상태에서 `/samples`가 열린다.
- [ ] 로그아웃 상태에서 공개 sample report가 열린다.
- [ ] 로그아웃 상태에서 비공개 report는 열리지 않는다.
- [ ] A 계정의 job/report를 B 계정이 직접 URL로 열면 거부된다.
- [ ] 로그인 상태의 `/samples` 우측 상단에는 Google 로그인 버튼 대신 계정명이 표시된다.

## 4. 배포 시작 전 최종 판정

아래 항목이 모두 체크되면 Railway production 배포를 시작할 수 있다.

- [ ] 한국어판 scope 고정
- [ ] 영문 분석 제외
- [ ] production 설정 validation 통과
- [ ] Railway 서비스 경계 확정
- [ ] Railway secret 입력 완료
- [ ] PostgreSQL 연결 확인
- [ ] Chroma volume 유지 확인
- [ ] report storage volume 유지 확인
- [ ] migration 완료
- [ ] corpus bootstrap 완료
- [ ] backend test 통과
- [ ] frontend test/build 통과
- [ ] Google OAuth E2E 통과
- [ ] BYOK E2E 통과
- [ ] 실제 영상 분석 E2E 통과
- [ ] 공개 sample 확인
- [ ] 소유권 격리 확인
- [ ] secret 미노출 확인

## 5. 막히면 사용자에게 요청할 것

Codex는 다음 경우에만 사용자에게 입력을 요청한다.

- Railway 웹 UI에서만 가능한 프로젝트/service/volume/domain 생성이 필요할 때
- Google Cloud Console에서 OAuth redirect URI 등록이 필요할 때
- API key 또는 secret 값이 비어 있을 때
- Railway billing/resource plan 조정이 필요할 때
- 운영 도메인 결정이 필요할 때
- 실제 Google 계정 로그인 확인이 필요할 때
