# YouTube Hate Speech Report

단일 YouTube 영상의 metadata, 전체 댓글·대댓글, 공개 자막을 수집하고 three-vector RAG로 분류해 웹/JSON/Excel 보고서를 생성하는 FastAPI 서비스다.

## 분류 정확도

공개 한국어 혐오표현 benchmark의 held-out split(K-HATERS test 499건, BEEP dev 471건, 데이터셋 원작자의 사람 라벨)으로 평가했다. 프롬프트와 taxonomy는 별도 튜닝셋(K-HATERS val·BEEP train 1,000건)에서만 고르고, 이 평가셋은 최종 구성을 정한 뒤 한 번만 썼다. 괄호 안은 95% bootstrap 구간이다.

| 구성 | 정확도 | precision | 혐오 여부 F1 | 판정 근거 인용 | 댓글 1,000개당 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 이전: Haiku 4.5 + 프롬프트 v0.3.1 | 0.748 | 0.947 | 0.804 (0.779–0.829) | 없음 | $6.13 |
| **현재: Haiku 5.5 + 프롬프트 v0.6.2** | **0.767** | **0.964** | **0.818** (0.795–0.841) | **94%** | **$1.45** |
| 절약: Jev + Haiku 5.5 | 0.767 | 0.964 | 0.818 | 94% | $1.25 |
| 참고: Sonnet 5.5 + 프롬프트 v0.6.2 | 0.779 | 0.965 | 0.830 | 97% | $24.46 |

- 비용을 약 76% 줄이면서 정확도는 동등 이상이다. precision은 유의하게 올랐고(+0.017, 95% 구간 +0.001~+0.034), F1 차이(+0.014)는 오차 범위 안이다.
- 혐오로 판정한 댓글의 94%가 방송미디어통신심의위원회 정보통신심의규정, 정보통신망법, 형법 모욕죄, 국가인권위원회 기준 등을 근거로 인용한다.
- Sonnet 5.5는 비용 17배에 유의한 향상이 없어(F1 +0.011, 95% 구간 −0.004~+0.028) 선택지로 두지 않았다.
- 데이터셋별(K-HATERS / corpus에 없는 BEEP)·혐오 정의별(offensive 포함 / 제외)로 다시 채점해도 결론은 같다.
- 공개 benchmark 성능이며 실제 YouTube 댓글·자막 정확도가 아니다. 실제 YouTube 정답셋은 아직 없다.

최신 모델이 기존 프롬프트에서 정확도가 떨어진 원인(문서마다 다른 혐오 기준) 분석, 튜닝 과정, 검색 층별 효과, category 점수의 한계와 재현 명령은 `docs/49_v062_benchmark_results.md`에 있다. 이전 구성의 RAG 구성요소별 검정과 K-HATERS category 매핑 수정은 `docs/46_public_benchmark_accuracy_results.md`에 있다.

### Jev 사전 필터 (선택)

경량 결정 모델 TypeSafe Jev(`jev-1.14.0`)가 혐오 확률이 낮다고 본 댓글은 LLM 없이 "혐오 아님"으로 판정하고, 나머지만 three-vector RAG로 보낸다. 분석 화면의 "절약" 방식이다. 목표는 정확도를 유지하면서 LLM 호출을 줄이는 것이다. 그래서 비열등성 기준(F1 차이 95% 구간 하한 > −0.01)을 미리 정했고, threshold(0.07)는 test가 아닌 튜닝셋(K-HATERS val·BEEP train 1,000건)에서 골랐다.

| 평가 | 결과 |
| --- | --- |
| benchmark 970건 | LLM 생략 13.9%. Haiku 4.5 기준 F1 0.804 → 0.803(차이 −0.001, 95% 구간 [−0.003, 0.000]), Haiku 5.5 기준 차이 0 |
| 실제 YouTube 댓글 표본 1,000건 | 17.4%를 걸러 분석 비용 약 17% 절감 |
| 걸러진 YouTube 댓글 174건 재분류 | RAG가 혐오로 보는 것 1건(0.6%, 공손한 어조 속 민족 멸칭) |

남은 누락은 사전 기준 안이라 사후 규칙으로 막지 않고 알려진 위험으로 기록했다. 기본은 꺼져 있고 `JEV_PREFILTER_ENABLED=true`와 서버 공용 `TYPESAFE_API_KEY`로 켠다. 걸러진 항목은 보고서에 "Jev 사전 필터로 혐오 아님 판정"으로 표시된다. Jev 비용은 댓글 1,000건당 약 $0.02다. 상세 내용은 `docs/47_jev_cascade_experiment.md`에 있다.

## 벡터 저장소

taxonomy(21)와 규범·기준 문서(66)는 Chroma에, 유사 사례(K-HATERS train 172,157건, Upstage 4096차원)는 디스크 기반 usearch 인덱스에 둔다.

Chroma는 컬렉션을 건드리면 HNSW 인덱스 전체를 메모리에 올린다. 유사 사례 인덱스는 2.9GB라 운영 VM(e2-micro, RAM 1GB)에서 swap을 붙잡고 멈췄다. 처음에는 유사 사례를 10%로 줄여 봤지만 dev F1이 0.831에서 0.806으로 유의하게 떨어졌다(McNemar p=0.002). 그래서 데이터는 그대로 두고 저장 방식을 바꿨다.

- int8로 양자화한 HNSW 인덱스(0.7GB)를 메모리 매핑으로 열어, 검색이 방문하는 페이지만 읽는다.
- int8 검색으로 후보 48건을 뽑고 float16 벡터(1.4GB, 역시 메모리 매핑)로 정확한 cosine 유사도를 계산해 상위 6건을 고른다(rescoring).

| 항목 | Chroma | 디스크 기반 인덱스 |
| --- | ---: | ---: |
| 필요 메모리 | 2.9GB | 400MB 제한에서 동작 |
| 정확한 전수 검색 대비 recall@6 | 0.858 | 0.936 |
| dev 1,000건 F1 (Haiku 5.5) | 0.831 | 0.830 (한쪽만 맞힌 문항 17 : 17) |

### 다른 후보와 비교

| 후보 | 형태 | 판단 |
| --- | --- | --- |
| **usearch (채택)** | 프로세스 내장 라이브러리 | 별도 서버가 없고 메모리 매핑으로 RAM을 거의 쓰지 않는다 |
| LanceDB | 내장, 디스크 기반 | 같은 계열의 대안. IVF-PQ 양자화가 내장되어 있고 메타데이터 관리가 더 편하다 |
| Qdrant (VM 설치) | 서버(Rust) | 원본 벡터는 디스크에 둘 수 있지만 양자화 벡터는 기본이 RAM 상주(int8 약 0.7GB)라, 서버 메모리까지 더하면 1GB VM에 빠듯하다 |
| Qdrant Cloud 무료 | 관리형 | 무료 클러스터 RAM이 1GB 수준이라 int8로 겨우 들어간다. 무료 조건과 네트워크 지연을 따져야 한다 |
| pgvector | Postgres 확장 | HNSW 인덱스 차원 한도(`vector` 2,000, `halfvec` 4,000)보다 4096차원이 커서 인덱스를 만들 수 없다 |
| FAISS | 라이브러리 | IVF-PQ 등 양자화는 강력하지만 디스크 기반 사용이 번거롭고 의존성이 크다 |
| Milvus, Weaviate | 서버 | 부속 서비스나 서버 메모리가 1GB VM에 무겁다 |
| sqlite-vec | SQLite 확장 | 전수 비교라 172k × 4096에서 느리다 |

Qdrant는 양자화 3종과 rescoring, 필터, 스냅샷을 기본 기능으로 갖춰 완성도가 가장 높다. 다만 지금은 worker 하나가 고정된 데이터를 읽기만 하므로, 서버를 하나 더 운영하는 비용이 이점보다 크다. VM을 필요할 때만 켜는 구조로 바꾸거나, 데이터가 수백만 건으로 늘거나, 여러 서비스가 검색을 공유해야 할 때 분리를 검토한다.

측정 방법과 재현 명령은 `docs/51_example_index_memory.md`에 있다.

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

기본 `PIPELINE_MODE=fake`는 외부 API 없이 backend job/report 경로를 검증한다. 로그인 UI를 사용하려면 Google OAuth client와 `API_KEY_ENCRYPTION_KEY`를 설정한다. 실제 수집에는 서버 공용 `YOUTUBE_API_KEY`가 필요하다. 임베딩은 서버 공용 `UPSTAGE_API_KEY`로 처리하고, Anthropic 키는 로그인한 사용자가 `/settings`에서 직접 등록한다.

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
# 선택: 유사 사례를 디스크 기반 인덱스로 (있으면 retriever가 이것을 쓴다)
uv run python -m app.analysis.example_index --source .chroma --target .chroma/example_index
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
