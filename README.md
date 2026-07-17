# YouTube Hate Speech Report

단일 YouTube 영상의 metadata, 전체 댓글·대댓글, 공개 자막을 수집하고 dual-vector RAG로 분류해 웹/JSON/Excel 보고서를 생성하는 FastAPI 서비스다.

## 로컬 실행

```bash
cp .env.example .env
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

별도 터미널에서 worker를 실행한다.

```bash
uv run python -m app.worker_main
```

기본 `PIPELINE_MODE=fake`는 외부 API 없이 backend job/report 경로를 검증한다. 로그인 UI를 사용하려면 Google OAuth client와 `API_KEY_ENCRYPTION_KEY`를 설정한다. 실제 수집에는 서버 공용 `YOUTUBE_API_KEY`가 필요하고, Anthropic/Upstage 키는 로그인한 사용자가 `/settings`에서 직접 등록한다.

## Docker Compose

개발 환경:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

분석 메인 화면은 `http://localhost:3000`, 공개 샘플은 `http://localhost:3000/samples`, RAG 방법론은 `http://localhost:3000/rag-methodology`에서 확인한다. 기존 `/analyze` 주소는 메인 화면으로 호환 리다이렉트한다. 개발용 API 문서는 `API_DOCS_ENABLED=true`일 때만 `http://localhost:8000/docs`에 열린다. 호스트 포트가 사용 중이면 `FRONTEND_PORT=13000`, `WEB_PORT=18000` 또는 `POSTGRES_PORT=15432`로 변경한다.

프론트만 다시 빌드하고 시작하려면 다음을 실행한다.

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build frontend
```

테스트 환경:

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm test
```

운영 후보 설정 검증:

```bash
APP_ENV=production PIPELINE_MODE=production ADMIN_TOKEN='<strong-token>' \
YOUTUBE_API_KEY='<key>' GOOGLE_CLIENT_ID='<client-id>' GOOGLE_CLIENT_SECRET='<secret>' \
API_KEY_ENCRYPTION_KEY='<fernet-key>' SESSION_COOKIE_SECURE=true \
FRONTEND_ORIGIN='https://service.example' \
GOOGLE_OAUTH_REDIRECT_URI='https://service.example/api/auth/google/callback' \
docker compose -f compose.yaml -f compose.prod.yaml config --quiet
```

운영 배포에서는 PostgreSQL 비밀번호와 모든 secret을 플랫폼 secret manager로 주입하고, `web` 앞에 TLS reverse proxy 또는 managed ingress를 둔다.

## Corpus 준비

```bash
uv run python -m app.analysis.rag_ingest --persist-directory .chroma --reset
uv run python -m app.analysis.definition_ingest --persist-directory .chroma
uv run python -m app.analysis.example_ingest --persist-directory .chroma
```

기본 ingest는 `commercial_ok` license tier만 허용한다. raw dataset과 vector store는 Git에 커밋하지 않는다.

## 개발용 요청 흐름

```bash
curl -X POST http://localhost:8000/api/analysis-jobs \
  -H 'Content-Type: application/json' \
  -d '{"input_value":"https://www.youtube.com/watch?v=VIDEO_ID"}'
```

이 curl은 OAuth 설정이 없는 `fake` 호환 모드에서만 사용한다. OAuth가 설정된 서비스에서는 브라우저 로그인·BYOK 등록 후 same-origin frontend가 CSRF header와 세션 쿠키를 포함해 요청한다. 반환된 `status_url`을 polling하고, 완료 후 report route를 연다. 관리자 API에는 별도의 `X-Admin-Token`이 필요하다.

## 검증

```bash
uv run ruff check app tests experiments scripts
uv run python -m compileall -q app tests experiments scripts alembic
uv run pytest -q
uv run pip-audit --ignore-vuln PYSEC-2026-311
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.test.yaml config --quiet
docker compose -f compose.yaml -f compose.prod.yaml config --quiet
```

실제 API E2E 절차와 배포 전 체크리스트는 `docs/15_predeploy_runbook.md`, 최종 외부 검증 증적은 `docs/17_live_validation_evidence.md`를 따른다.

Google OAuth·BYOK·로그인 전 공개 샘플의 구현과 운영 절차는 `docs/34_google_oauth_public_samples_delivery.md`를 따른다.

Stitch 기반 프론트 구조, 화면/API 매핑, Docker 실행 및 검증 기록은 `docs/18_stitch_frontend_delivery.md`에 정리되어 있다.

실제 dual-vector 검색, 전체 prompt, validation/retry, 저장되는 provenance와 재현 절차는 `docs/19_rag_methodology_reproducibility.md`를 따른다.

단일 job worker 내부의 RAG item 병렬 처리, checkpoint, rate limit과 단계별 검증 계획은 `docs/22_rag_parallel_processing_plan.md`를 따른다.

RAG 병렬화의 실제 클래스·transaction·thread 경계와 구현 브랜치별 merge gate는 `docs/23_rag_parallel_technical_design.md`에 정의한다.

단계별 실제 구현, 테스트 수치와 merge 증적은 `docs/24_rag_parallel_delivery.md`에 누적 기록한다.
