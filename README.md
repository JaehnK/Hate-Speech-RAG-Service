# YouTube Hate Speech Report

단일 YouTube 영상의 metadata, 전체 댓글·대댓글, 공개 자막을 수집하고 three-vector RAG로 분류해 웹/JSON/Excel 보고서를 생성하는 FastAPI 서비스다.

## 분류 정확도

공개 한국어 혐오표현 benchmark의 held-out split(K-HATERS test 499건, BEEP dev 471건, 데이터셋 원작자의 사람 라벨)에서 검색 구성을 바꿔 가며 같은 입력을 분류했다. 모델은 `claude-haiku-4-5-20251001`, temperature 0이다. 괄호 안은 95% bootstrap 구간이다.

| 구성 | 혐오 여부 정확도 | 혐오 여부 F1 | category macro F1 |
| --- | ---: | ---: | ---: |
| RAG 미적용 | 0.573 | 0.601 | 0.390 |
| 정의 문서만 | 0.623 | 0.667 | 0.397 |
| 유사 사례만 | 0.739 | 0.795 | 0.484 |
| **three-vector RAG** | **0.748** (0.722–0.778) | **0.804** (0.779–0.829) | **0.493** |

- RAG 미적용 대비 정확도 +17.5%p (McNemar p < 0.0001). 검색 corpus에 없는 BEEP에서도 F1이 0.414에서 0.704로 오른다.
- 혐오 여부 판정의 개선은 유사 사례 검색이 주도한다. 정의 문서는 정치 category 판정을 유의하게 개선한다(유사 사례만 대비 political F1 +0.09).
- precision 0.947, recall 0.698로, 주된 오류는 대상 없는 욕설·공격적 표현을 혐오로 보지 않는 놓침이다.
- 공개 benchmark 성능이며 실제 YouTube 댓글·자막 정확도가 아니다. 실제 YouTube gold set 평가는 아직 수행하지 않았다.

평가셋 구성, 구성요소별 검정, K-HATERS category 매핑 수정의 전후 효과와 재현 명령은 `docs/46_public_benchmark_accuracy_results.md`에 있다.

### Jev 사전 필터 (선택)

경량 결정 모델 TypeSafe Jev(`jev-1.14.0`)가 혐오 확률이 낮다고 본 댓글은 LLM 없이 "혐오 아님"으로 판정하고, 나머지만 three-vector RAG로 보낸다. 목표는 정확도를 유지하면서 LLM 호출을 줄이는 것이다. 그래서 비열등성 기준(F1 차이 95% 구간 하한 > −0.01)을 미리 정했고, threshold(0.07)는 test가 아닌 튜닝셋(K-HATERS val·BEEP train 1,000건)에서 골랐다.

| 평가 | 결과 |
| --- | --- |
| benchmark 970건 | LLM 생략 13.9%, binary F1 0.804 → 0.803 (차이 −0.001, 95% 구간 [−0.003, 0.000]), 기준 충족 |
| 실제 YouTube 댓글 표본 1,000건 | 17.4%를 걸러 분석 비용 약 17% 절감 |
| 걸러진 YouTube 댓글 174건 재분류 | RAG가 혐오로 보는 것 1건(0.6%, 공손한 어조 속 민족 멸칭) |

남은 누락은 사전 기준 안이라 사후 규칙으로 막지 않고 알려진 위험으로 기록했다. 기본은 꺼져 있고 `JEV_PREFILTER_ENABLED=true`와 서버 공용 `TYPESAFE_API_KEY`로 켠다. 걸러진 항목은 보고서에 "Jev 사전 필터로 혐오 아님 판정"으로 표시된다. Jev 비용은 댓글 1,000건당 약 $0.02다. 상세 내용은 `docs/47_jev_cascade_experiment.md`에 있다.

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

실제 three-vector 검색, 전체 prompt, validation/retry, 저장되는 provenance와 재현 절차는 `docs/19_rag_methodology_reproducibility.md`를 따른다.

단일 job worker 내부의 RAG item 병렬 처리, checkpoint, rate limit과 단계별 검증 계획은 `docs/22_rag_parallel_processing_plan.md`를 따른다.

RAG 병렬화의 실제 클래스·transaction·thread 경계와 구현 브랜치별 merge gate는 `docs/23_rag_parallel_technical_design.md`에 정의한다.

단계별 실제 구현, 테스트 수치와 merge 증적은 `docs/24_rag_parallel_delivery.md`에 누적 기록한다.
