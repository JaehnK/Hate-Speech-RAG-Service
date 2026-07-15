# Docker 환경 분리

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.0 |
| 작성일시 | 2026-07-08 08:35:46 KST |

## 문서 목적

이 문서는 FastAPI 기반 YouTube 혐오표현 분석 MVP의 Docker 실행 환경 분리 방식을 정의한다.

목표는 개발, 테스트, 운영 환경이 같은 서비스 경계를 공유하되, volume, command, secret, 외부 노출 범위를 환경별로 다르게 관리하는 것이다.

## 핵심 결정

- Python dependency 관리는 `uv`를 사용한다.
- Docker image는 web과 worker가 공유한다.
- web과 worker는 같은 코드베이스를 사용하지만 별도 container로 실행한다.
- PostgreSQL은 container service로 실행한다.
- Chroma는 MVP 권장 기본값으로 persistent directory 기반으로 시작한다.
- report export와 자막 원문은 파일 저장소 volume에 저장한다.
- 개발 환경은 bind mount와 reload를 허용한다.
- 테스트 환경은 가능한 한 fake YouTube, fake LLM을 기본값으로 사용한다.
- 운영 환경은 source bind mount를 사용하지 않는다.

## Compose 파일 구성

권장 파일 구성:

```text
compose.yaml
compose.dev.yaml
compose.test.yaml
compose.prod.yaml
Dockerfile
.dockerignore
.env.example
.env.dev.example
.env.test.example
.env.prod.example
```

### compose.yaml

공통 service, network, volume을 정의한다.

포함 대상:

- `web`
- `worker`
- `postgres`
- `migrate`

공통 volume:

- `postgres_data`
- `report_storage`
- `chroma_data`

공통 network:

- `app_net`

정책:

- `web`과 `worker`는 같은 image를 사용한다.
- `web`만 host port를 노출한다.
- `postgres`는 기본적으로 내부 network에만 노출한다.
- migration은 `migrate` one-shot service로 실행한다.

### compose.dev.yaml

개발 편의성을 위한 override 파일이다.

차이점:

- source bind mount 사용
- `uv sync` 후 reload 실행
- `web`은 `uv run uvicorn app.main:app --reload`로 실행
- `worker`는 reload 없이 polling loop 실행
- PostgreSQL host port 노출 허용
- 로그 레벨은 `debug`
- `.env.dev` 사용

개발 실행 예:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

### compose.test.yaml

테스트 전용 override 파일이다.

차이점:

- 테스트 DB volume은 ephemeral로 사용
- fake YouTube client와 fake LLM classifier를 기본값으로 사용
- 외부 API key 없이도 테스트가 가능해야 한다.
- command는 `uv run pytest`
- report와 Chroma 데이터는 테스트 종료 후 폐기 가능해야 한다.

테스트 실행 예:

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm test
```

### compose.prod.yaml

운영 또는 운영 유사 환경 override 파일이다.

차이점:

- source bind mount 금지
- image tag를 명시한다.
- `.env.prod` 또는 secret manager를 사용한다.
- `web`은 reload 없이 실행한다.
- `postgres` host port를 노출하지 않는다.
- named volume을 사용한다.
- 로그 레벨은 `info` 이상을 기본값으로 둔다.

운영 유사 실행 예:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

## Service 분리

### web

책임:

- FastAPI HTTP API 제공
- server-side template 보고서 렌더링
- export 다운로드 제공
- 관리자 API 제공

command 후보:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

개발 환경 command 후보:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### worker

책임:

- PostgreSQL polling으로 pending job 점유
- 수집, 분석, network, report snapshot step 실행
- operation log 기록

command 후보:

```bash
uv run python -m app.jobs.worker
```

정책:

- worker는 HTTP port를 노출하지 않는다.
- worker는 web과 같은 image를 사용한다.

### migrate

책임:

- Alembic migration 실행

command 후보:

```bash
uv run alembic upgrade head
```

정책:

- web과 worker 시작 전에 실행한다.
- 운영에서는 수동 승인 또는 배포 pipeline 단계로 분리할 수 있다.

### postgres

책임:

- 기준 관계형 저장소

정책:

- dev에서는 host port 노출을 허용할 수 있다.
- prod에서는 app network 내부에서만 접근한다.
- 데이터는 named volume에 저장한다.

### chroma

MVP 권장 기본값에서는 별도 Chroma server container를 두지 않는다.

정책:

- Chroma persistent directory를 `chroma_data` volume에 둔다.
- 같은 persistent directory 안에 예시 collection과 정의 문서 collection을 둔다.
- web과 worker가 같은 persistent directory 경로를 참조할 수 있어야 한다.
- Chroma server mode가 필요해지면 별도 service로 분리한다.

## uv 사용 방식

### 로컬 개발

기본 명령:

```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

정책:

- dependency는 `pyproject.toml`에 정의한다.
- lock file은 `uv.lock`을 사용한다.
- CI와 Docker build는 `uv sync --frozen`을 사용한다.

### Docker build

Dockerfile 원칙:

- Python 3.11 기반 image를 사용한다.
- `uv`를 image 안에 설치하거나 uv 제공 base를 사용한다.
- `pyproject.toml`, `uv.lock`을 먼저 복사해 dependency layer cache를 활용한다.
- 운영 image에서는 dev dependency를 제외한다.
- source bind mount는 dev override에서만 사용한다.

Dockerfile 흐름 후보:

```text
1. base image 준비
2. uv 설치
3. pyproject.toml, uv.lock 복사
4. uv sync --frozen --no-dev
5. app source 복사
6. web 또는 worker command 실행
```

## 환경변수 분리

공통 환경변수:

| 이름 | 설명 |
| --- | --- |
| `APP_ENV` | `dev`, `test`, `prod` |
| `DATABASE_URL` | PostgreSQL 접속 URL |
| `ADMIN_TOKEN` | 관리자 API token |
| `WORKER_STALE_AFTER_SECONDS` | heartbeat가 멈춘 running job을 재대기시키는 기준. 기본 900초 |
| `RAG_EXECUTION_MODE` | RAG item 실행 방식. 기본 `sequential`, 검증 후 `parallel` |
| `RAG_ITEM_CONCURRENCY` | RAG step의 최대 in-flight item/classifier slot 수. 기본 2 |
| `RAG_EMBEDDING_CONCURRENCY` | Upstage 최대 동시 호출 수. 기본 2 |
| `RAG_LLM_CONCURRENCY` | Anthropic 최대 동시 호출 수. 기본 2 |
| `RAG_ITEM_MAX_ATTEMPTS` | 일시적 provider 오류의 최대 시도 수. 기본 3 |
| `RAG_HEARTBEAT_INTERVAL_SECONDS` | 완료 item이 없을 때 RAG heartbeat 간격. 기본 30초 |
| `RAG_SHUTDOWN_GRACE_SECONDS` | 종료 요청 시 active item drain 상한. 기본 30초 |
| `RAG_REQUEST_TIMEOUT_SECONDS` | embedding/LLM 요청 timeout. 기본 30초 |
| `YOUTUBE_API_KEY` | YouTube Data API key |
| `LLM_PROVIDER` | LLM provider |
| `LLM_MODEL` | LLM model |
| `LLM_API_KEY` | LLM API key |
| `EMBEDDING_PROVIDER` | embedding provider |
| `EMBEDDING_MODEL` | embedding model |
| `EMBEDDING_API_KEY` | embedding API key |
| `CHROMA_PERSIST_DIRECTORY` | Chroma persistent directory |
| `EXAMPLE_VECTOR_COLLECTION` | 혐오표현 예시 collection |
| `DEFINITION_VECTOR_COLLECTION` | 혐오표현 정의 문서 collection |
| `DEFINITION_CORPUS_VERSION` | 정의 문서 corpus version |
| `REPORT_STORAGE_DIR` | report export 저장 경로 |
| `LOG_LEVEL` | 로그 레벨 |

파일 정책:

- `.env.example`은 commit한다.
- `.env.dev.example`, `.env.test.example`, `.env.prod.example`은 commit한다.
- 실제 `.env.dev`, `.env.test`, `.env.prod`는 commit하지 않는다.
- secret 원문은 문서, 로그, 보고서에 기록하지 않는다.

## Volume 분리

권장 volume:

| Volume | 용도 | dev | test | prod |
| --- | --- | --- | --- | --- |
| `postgres_data` | PostgreSQL 데이터 | 유지 | 폐기 가능 | 유지 |
| `report_storage` | HTML, Excel export | 유지 | 폐기 가능 | 유지 |
| `chroma_data` | Chroma persistent directory | 유지 | fixture 가능 | 유지 |

정책:

- test volume은 독립 이름을 사용하거나 anonymous volume로 둔다.
- prod volume은 명시적으로 backup 대상에 포함한다.
- raw 프로젝트 디렉토리는 runtime volume으로 mount하지 않는다.

## Network 분리

권장 network:

- `app_net`: web, worker, postgres 내부 통신

노출 정책:

- dev: `web:8000`, 필요 시 `postgres:5432` 노출
- test: 기본적으로 host port 노출 없음
- prod: `web`만 reverse proxy 또는 host port로 노출

## 외부 의존성 모드

환경별 외부 의존성 정책:

| 환경 | YouTube | LLM | Chroma |
| --- | --- | --- | --- |
| dev | real 또는 fixture 선택 | fake 또는 real 선택 | persistent directory |
| test | fake 기본 | fake 기본 | fixture 또는 temp |
| prod | real | real | persistent directory |

정책:

- test는 외부 API key 없이 실행 가능해야 한다.
- E2E 검증은 별도 opt-in profile에서 real YouTube, real LLM을 사용한다.

## Profile 제안

선택 profile:

- `dev`: 개발 서버와 worker
- `test`: 테스트 실행
- `admin`: dev에서 DB 관리 도구가 필요할 때만 사용
- `e2e`: 실제 YouTube와 LLM을 사용하는 통합 검증

예시:

```bash
docker compose --profile dev -f compose.yaml -f compose.dev.yaml up
docker compose --profile e2e -f compose.yaml -f compose.test.yaml run --rm e2e
```

## 구현 순서

1. `pyproject.toml`과 `uv.lock` 생성
2. FastAPI skeleton 작성
3. `Dockerfile` 작성
4. `compose.yaml` 작성
5. `compose.dev.yaml` 작성
6. `compose.test.yaml` 작성
7. `compose.prod.yaml` 작성
8. `.env*.example` 작성
9. web, worker, migrate command 검증
10. fake dependency 기반 test profile 검증

## 보류 사항

다음 항목은 구현 중 확정한다.

- Docker base image tag
- prod에서 reverse proxy를 compose에 포함할지 여부
- dev DB 관리 도구를 포함할지 여부
- Chroma server mode 전환 시점
- e2e profile에서 실제 API 호출 비용 제한 방식

## 검증 기준

Docker 환경은 다음 조건을 만족해야 한다.

- `docker compose -f compose.yaml -f compose.dev.yaml up --build`로 web과 worker가 실행된다.
- `uv sync --frozen` 기반으로 dependency가 재현된다.
- web과 worker는 같은 image에서 다른 command로 실행된다.
- dev 환경은 reload와 source bind mount를 지원한다.
- test 환경은 외부 API key 없이 실행 가능하다.
- prod 환경은 source bind mount를 사용하지 않는다.
- PostgreSQL, report storage, Chroma data volume이 분리되어 있다.
