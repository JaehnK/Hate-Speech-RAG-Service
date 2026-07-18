# 한국어판 Railway 배포 전 준비 계획

## 작업 계약

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-07-18 |
| 브랜치 | `chore/korean-predeploy-railway-plan` |
| 배포 범위 | 한국어 혐오표현 분석 서비스 |
| 배포 목표 | Railway 배포 시작 직전까지 필요한 코드·데이터·운영 조건 확정 |
| 제외 범위 | 영문 분석, 영문 RAG corpus, 영문 평가셋, 영문 report 생성 |

## 결정 사항

이번 배포 후보는 한국어판으로 고정한다.

- 입력은 YouTube 댓글·대댓글·공개 자막을 수집한다.
- 분석 기준은 현재 한국어 taxonomy와 한국어 중심 RAG corpus를 사용한다.
- 분석 사유와 Excel/report의 주요 설명은 한국어로 유지한다.
- 영어 자막이나 영어 댓글이 수집될 수는 있지만, 영어권 hate-speech 분석 품질을 보장한다고 표시하지 않는다.
- 영문 분석은 `docs/39_comment_evidence_multilingual_corpus_audit.md`의 gate가 해결된 뒤 별도 release로 다룬다.

## 배포 전 남은 태스크

### 1. Railway 서비스 경계 확정

Railway에서는 local compose의 여러 service를 다음 runtime 경계로 나눠 배포한다.

| Railway 단위 | 역할 | 실행 명령 후보 |
| --- | --- | --- |
| `web` | FastAPI API, auth callback, report/export API | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `worker` | pending job polling, 수집·RAG 분석·report 생성 | `python -m app.worker_main` |
| `frontend` | React 정적 UI 또는 reverse proxy | frontend Dockerfile production stage |
| `postgres` | 운영 DB | Railway PostgreSQL |
| `volume` | Chroma와 report export 저장소 | Railway volume 또는 외부 persistent storage |
| one-shot `migrate` | Alembic migration | `alembic upgrade head` |
| one-shot `corpus` | Chroma corpus bootstrap | `python -m scripts.bootstrap_corpus --persist-directory $CHROMA_PERSIST_DIRECTORY --reset` |

검증:

- `web`과 `worker`가 같은 `DATABASE_URL`, `CHROMA_PERSIST_DIRECTORY`, `REPORT_STORAGE_DIR`를 본다.
- `worker`만 장시간 job을 수행하고 HTTP port를 노출하지 않는다.
- migration은 `web`/`worker` 시작 전에 1회 실행한다.

### 2. 운영 환경변수 확정

필수 secret:

- `APP_ENV=production`
- `PIPELINE_MODE=production`
- `API_DOCS_ENABLED=false`
- `DATABASE_URL`
- `ADMIN_TOKEN`
- `YOUTUBE_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI=https://<운영도메인>/api/auth/google/callback`
- `FRONTEND_ORIGIN=https://<운영도메인>`
- `SESSION_COOKIE_SECURE=true`
- `API_KEY_ENCRYPTION_KEY`
- `EMBEDDING_PROVIDER=upstage`
- `EMBEDDING_MODEL=embedding`
- `UPSTAGE_API_KEY`
- `LLM_PROVIDER=anthropic`
- `LLM_MODEL=claude-haiku-4-5-20251001`

BYOK 배포 정책:

- 사용자의 Anthropic/Upstage 키는 `/settings`에서 등록한다.
- 서버 공용 `ANTHROPIC_API_KEY`는 필수로 두지 않는다.
- corpus bootstrap에는 운영자 `UPSTAGE_API_KEY`가 필요하다.
- `API_KEY_ENCRYPTION_KEY`는 Fernet key여야 하며 분실 시 기존 사용자 API key 재등록이 필요하다.

검증:

- `APP_ENV=production`으로 `Settings()` 생성이 성공한다.
- `/docs`, `/redoc`, `/openapi.json`이 production에서 공개되지 않는다.
- secret 원문이 로그, report, export, Langfuse trace에 남지 않는다.

### 3. 한국어 RAG corpus 고정

현재 배포 corpus는 세 collection 구조를 사용한다.

- `hate_speech_taxonomy`
- `hate_speech_authoritative`
- `hate_speech_examples`

배포 전 corpus 준비:

1. `docs/40_public_artifact_inventory.md` 기준으로 공개 가능한 문서와 dataset만 확인한다.
2. Railway persistent volume 또는 배포 전 생성한 Chroma directory에 corpus를 적재한다.
3. collection count와 retrieval smoke test를 기록한다.
4. Embed 2 모델명과 corpus version을 배포 증적에 남긴다.

검증:

- 세 collection 모두 document count가 0보다 크다.
- 동일 한국어 sample query에서 taxonomy, authoritative, examples 검색이 모두 성공한다.
- 재시작 후에도 Chroma directory가 보존된다.

### 4. 한국어 분석 품질 gate

배포 승인용 품질 gate는 영어 분석을 제외하고 한국어 입력만 대상으로 한다.

필수 확인:

- 댓글 RAG와 자막 문장 단위 RAG가 모두 실행된다.
- reasoning은 한국어로 생성된다.
- category label은 frontend/report/export에서 한국어 표시를 제공한다.
- citation은 UI에서 “기록된 근거”로만 표시하고 최종 법적 판단처럼 보이지 않게 한다.
- synthetic smoke가 아니라 실제 한국어 comment/script 후보로 최소 1회 E2E를 실행한다.

권장 확인:

- `experiments/prepare_legacy_gold.py`로 만든 legacy 후보 queue에서 일부를 수동 검토한다.
- `three_vector_rag` 결과를 기존 legacy label 또는 수동 review와 비교한다.
- binary F1, category micro F1, 실패율, 평균 처리 시간을 배포 증적에 남긴다.

### 5. 공개 surface 정리

배포 전 사용자 노출 화면은 portfolio 성격을 유지하되 내부 구현 세부를 숨긴다.

확인 대상:

- `/`
- `/samples`
- `/rag-methodology`
- `/history`
- `/jobs/{id}`
- `/reports/{id}`
- `/settings`

노출 금지:

- API key, session token, encryption key
- raw prompt 전체
- 내부 collection 이름과 threshold
- Swagger/readiness/development link
- migration/가격/모델 전환 같은 운영상 약점으로 보일 수 있는 이력

노출 가능:

- RAG를 사용한다는 방법론 개요
- taxonomy의 공개 설명
- 근거 기반 분류의 한계
- 공개 sample report
- K-HATERS 등 공개 corpus attribution

검증:

- 로그아웃 상태에서 공개 sample만 접근 가능하다.
- 로그인 사용자는 자기 job/report만 접근 가능하다.
- 다른 계정의 job/report 직접 URL 접근은 거부된다.

### 6. Railway 배포 직전 검증 순서

로컬 또는 staging에서 다음 순서로 통과해야 한다.

```bash
uv sync --frozen
uv run ruff check app tests experiments scripts
uv run python -m compileall -q app tests experiments scripts alembic
uv run pytest -q
uv run pip-audit --ignore-vuln PYSEC-2026-311

cd frontend
npm ci
npm run test
npm run build
```

Docker 후보 검증:

```bash
docker compose -f compose.yaml -f compose.prod.yaml config --quiet
docker compose --profile tools run --rm corpus
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
```

운영 DB에서는 downgrade를 실행하지 않는다. migration 왕복 검증은 빈 staging DB에서만 수행한다.

### 7. 실제 운영 E2E

배포 시작 전 마지막으로 아래 시나리오를 실행한다.

1. Google 로그인 성공.
2. API key 발급 안내 페이지에서 Anthropic/Upstage key 등록.
3. 키 검증 성공.
4. 키 미등록 상태에서 job 생성 시 거부되는지 확인.
5. 댓글과 자막이 있는 공개 영상 분석.
6. 댓글 비활성 영상 partial success.
7. 자막 없는 영상 partial success.
8. job progress에서 댓글/자막 RAG 완료 수 확인.
9. report graph, category, 전체 혐오 댓글, 근거 펼침 확인.
10. HTML/XLSX export 확인.
11. 공개 sample report 확인.
12. 두 계정 간 소유권 격리 확인.
13. secret scan 확인.

검증 증적은 raw 댓글·자막을 포함하지 않는 요약 JSON 또는 문서로 보관한다.

## 배포 시작 가능 조건

아래 조건이 모두 참이면 Railway 배포를 시작한다.

- 한국어판 scope가 고정되어 영문 분석이 제외됐다.
- production `Settings()` validation이 성공한다.
- Railway service 경계와 command가 확정됐다.
- PostgreSQL, Chroma, report storage 영속성 전략이 확정됐다.
- corpus bootstrap 결과와 retrieval smoke 결과가 기록됐다.
- backend/frontend test와 build가 통과했다.
- Google OAuth redirect URI가 운영 도메인으로 등록됐다.
- 공개 sample report가 운영자 검토 후 지정됐다.
- BYOK 저장·암호화·계정 격리 E2E가 통과했다.
- `/docs`, `/redoc`, `/openapi.json`이 production에서 닫혀 있다.
- secret이 로그/report/export에 남지 않는다는 점을 확인했다.

## 후속으로 분리된 작업

- 영문 UI 전환
- 영문 hate-speech 분석
- 영어 authoritative corpus와 example corpus 구축
- 영어 gold set 평가
- Chroma server mode 또는 외부 vector DB 이전
- production monitoring/alerting 고도화
