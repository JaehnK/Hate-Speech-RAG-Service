# 배포 전 실행 절차

## 1. Secret 준비

- `ADMIN_TOKEN`: 충분히 긴 무작위 값
- `POSTGRES_PASSWORD`: 운영 전용 값
- `YOUTUBE_API_KEY`: YouTube Data API v3 활성화 키(운영자 공용, BYOK 대상 아님)
- `UPSTAGE_API_KEY`: corpus bootstrap(`docker compose --profile tools run --rm corpus`)에서 정의/예시 corpus를 ingest할 때만 필요한 운영자 키
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google Cloud Console에서 발급한 OAuth 웹 애플리케이션 client. redirect URI가 운영 도메인의 `/api/auth/google/callback`과 정확히 일치해야 한다.
- `API_KEY_ENCRYPTION_KEY`: 사용자 Anthropic/Upstage API 키 암호화용 Fernet 마스터 키. `openssl rand -base64 32`로 1회 생성하고, 이 값을 잃어버리면 이미 등록된 모든 사용자 API 키를 다시 등록해야 한다.
- `SESSION_COOKIE_DOMAIN`, `SESSION_COOKIE_SECURE`, `SESSION_TTL_SECONDS`: 운영 도메인 기준으로 설정(`SESSION_COOKIE_SECURE=true` 필수)

`ANTHROPIC_API_KEY`는 운영자 공용 값을 배포에 필수로 두지 않는다. 실제 분석 job은 사용자가 등록한 BYOK 키를 사용하므로, 운영자 값은 로컬 개발/`PIPELINE_MODE=fake` 검증에서만 필요하다.

키 원문은 DB, Git, 보고서, command history에 기록하지 않는다. 배포 플랫폼의 secret manager 또는 보호된 환경변수로 주입한다. `GOOGLE_CLIENT_SECRET`과 `API_KEY_ENCRYPTION_KEY`는 특히 유출 시 전체 사용자 세션/API 키가 위험해지므로 접근 권한을 최소화한다.

## 2. Corpus 생성

라이선스가 허용된 production corpus는 다음 one-shot 서비스로 named volume에 생성한다. 실제 전체 적재는 limit 없이 실행하며, 외부 API 연결 smoke에만 `--limit-per-dataset`을 사용한다.

배포에 포함할 문서·공개 샘플·RAG 자료 목록은 `docs/40_public_artifact_inventory.md`를 기준으로 한다.

```bash
docker compose --profile tools run --rm corpus
```

1. dataset source revision과 license tier를 확인한다.
2. internal taxonomy를 `hate_speech_taxonomy`에 ingest한다.
3. 허용된 외부 definition 문서를 `hate_speech_authoritative`에 ingest한다.
4. 허용된 example dataset만 `hate_speech_examples`에 ingest한다.
5. 세 collection의 document count와 retrieval smoke test를 확인한다.

## 3. 자동 검증

```bash
uv sync --frozen
uv run ruff check app tests experiments scripts
uv run python -m compileall -q app tests experiments scripts alembic
uv run pytest -q
uv run pip-audit --ignore-vuln PYSEC-2026-311
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
cd frontend
npm ci
npm run test
npm run build
npm audit
```

운영 DB에서는 downgrade를 실행하지 않고 staging의 빈 DB에서만 왕복 검증한다.

`PYSEC-2026-311` 예외의 도달 불가능 조건과 제거 기준은 `SECURITY.md`에 고정한다. Chroma HTTP server mode는 upstream 수정 전 금지한다.

## 4. 실제 API E2E

1. 테스트용 Google 계정으로 로그인해서 세션 쿠키가 발급되는지 확인한다.
2. 해당 계정으로 Anthropic/Upstage API 키를 등록하고, 등록 시 검증 호출이 성공하는지 확인한다. 키를 등록하지 않은 상태로 job 생성을 시도해 `422`가 반환되는지도 확인한다.
3. 댓글과 공개 자막이 있는 공개 영상으로 job을 생성한다.
4. 모든 step이 끝날 때까지 status API를 polling한다.
5. metadata, 전체 댓글/대댓글, transcript segment 수를 원천 응답과 대조한다.
6. comment/script 결과 수가 각 snapshot/segment 수와 일치하는지 확인한다.
7. report page, JSON 상세 API, network, HTML/XLSX export를 확인한다.
8. 댓글 비활성 영상과 자막 없는 영상으로 `partial_success` 경로를 각각 확인한다.
9. 로그, 관리자 API, report/export 파일, Langfuse trace에서 secret 문자열(YouTube/Anthropic/Upstage 키, 세션 토큰, `API_KEY_ENCRYPTION_KEY`)이 검색되지 않는지 확인한다.
10. 두 번째 테스트용 Google 계정으로 로그인해서, 첫 번째 계정의 job/report ID를 직접 조회하면 `403` 또는 `404`로 거부되는지 확인한다.
11. 로그아웃 상태(쿠키 없음)에서 운영자가 지정한 공개 샘플 report가 정상 조회되는지 확인한다.
12. 프론트의 분석 요청, job polling, report 화면, HTML/XLSX 다운로드를 동일 출처 `/api` 경로로 확인한다.
13. `/history`, `/jobs/{id}`, `/reports/{id}`를 직접 열어 SPA fallback이 동작하는지 확인한다.

실행 중인 production 후보 서비스에 대해 다음 runner로 세 시나리오와 HTML/XLSX export, 관리자 surface, secret scan을 한 번에 검증한다. 비용을 제한하려면 정상 영상은 댓글 수가 적은 공개 영상을 선택한다.

```bash
docker compose run --rm --no-deps web python -m scripts.live_e2e \
  --base-url http://web:8000 \
  --normal-video NORMAL_VIDEO_ID \
  --comments-disabled-video COMMENTS_DISABLED_VIDEO_ID \
  --no-caption-video NO_CAPTION_VIDEO_ID \
  --evidence-path /data/reports/live_e2e_evidence.json
docker compose cp web:/data/reports/live_e2e_evidence.json \
  experiments/outputs/live_e2e_evidence.json
```

runner는 prompt version과 `example_min_similarity`까지 report snapshot에서 검증한다. 증적은 Git에서 제외된 `experiments/outputs/live_e2e_evidence.json`에 보관하고, raw 댓글/자막은 포함하지 않는다. 2026-07-14 검증 결과는 `docs/17_live_validation_evidence.md`를 참조한다.

## 5. RAG 품질 게이트

합성 smoke set은 실행 경로만 검증한다. 배포 승인에는 익명화한 실제 댓글·스크립트 gold set을 사용한다.

- 2인 독립 라벨링과 불일치 조정
- `haiku_only`, `definitions_only`, `examples_only`, `three_vector_rag` 동일 입력 비교
- binary accuracy와 category micro F1 기록
- 동일 입력 3회 반복 안정성 확인
- dual RAG가 baseline보다 악화되면 배포를 중단하고 retrieval/prompt를 조정

```bash
uv run python -m experiments.run_rag_experiment \
  --input-path REAL_INPUTS.jsonl \
  --output-path experiments/outputs/live_rag_results.jsonl \
  --repeat 3
uv run python -m experiments.evaluate_results \
  --results-path experiments/outputs/live_rag_results.jsonl \
  --gold-path REAL_GOLD.jsonl
```

## 6. 배포 승인 체크리스트

- production 설정 validation 통과
- migration backup/rollback 절차 확인
- TLS ingress와 request size/timeouts 설정
- PostgreSQL, Chroma, report volume 영속성 확인
- API quota와 LLM 비용 한도 설정
- 관리자 token 교체 및 접근 제한
- worker 단일 job claim 동시성 확인
- 정상/부분 실패 E2E 증적 보관
- 프론트 production 이미지의 read-only 기동, healthcheck, CSP와 API reverse proxy 확인
- Google OAuth consent screen이 운영 도메인으로 설정되고, redirect URI가 정확히 등록되어 있다
- `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_DOMAIN`이 운영 도메인 기준으로 설정되어 있다(HTTPS 미적용 상태로 배포하지 않는다)
- `API_KEY_ENCRYPTION_KEY`가 secret manager/보호된 환경변수로만 주입되고, 별도 안전한 위치에 백업되어 있다(분실 시 전체 사용자 API 키 재등록 필요)
- `APP_ENV=production`, `API_DOCS_ENABLED=false`이며 `/docs`, `/redoc`, `/openapi.json`이 모두 `404`를 반환한다.
- public `/rag-methodology`에 모델 ID, prompt 원문, collection 이름, 검색 임계값, migration·가격 이력이 노출되지 않으며 Swagger와 readiness 링크가 없다.
- 운영자가 공개 샘플로 지정할 report 후보를 사전에 검토하고 `is_public_sample`을 설정했다
- 두 계정 간 job/report 소유권 격리가 E2E에서 확인됐다(4번 절차 10번 항목)
