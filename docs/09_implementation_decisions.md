# 구현 결정 로그

| 항목 | 값 |
| --- | --- |
| 버전 | v0.5.0 |
| 작성일시 | 2026-07-09 01:11:43 KST |

## 문서 목적

이 문서는 MVP 구현 전에 확정하거나 추적해야 하는 기술 결정을 한 곳에 기록한다.

HLD, 데이터 모델, pipeline, API 명세, 보고서 명세에 흩어진 결정을 모아 구현자가 같은 질문을 반복하지 않도록 하는 것이 목적이다.

## 사용 방식

- 새 결정은 `DEC-###` ID를 부여한다.
- 결정 상태는 `확정`, `권장`, `보류`, `변경됨` 중 하나로 표시한다.
- `권장`은 문서 작성자가 제안한 기본값이다.
- `확정`은 사용자가 명시적으로 승인했거나 이전 대화에서 결정된 항목이다.
- 구현 중 결정이 바뀌면 기존 항목을 삭제하지 않고 상태를 `변경됨`으로 바꾼 뒤 새 항목을 추가한다.
- 관련 문서에는 필요한 경우 별도 업데이트를 수행한다.

## 결정 상태 정의

| 상태 | 의미 |
| --- | --- |
| `확정` | MVP 기준으로 사용한다. |
| `권장` | 현재 설계상 추천 기본값이다. 구현 착수 전 사용자 확인이 필요할 수 있다. |
| `보류` | 지금 결정하지 않아도 문서 작업은 계속 가능하다. |
| `변경됨` | 더 이상 현재 기준이 아니다. 변경 사유와 대체 결정을 남긴다. |

## 결정 목록

### DEC-001 Python 버전

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | Python 3.11 |
| 근거 | FastAPI, SQLAlchemy, Chroma, LLM client 계열 라이브러리 호환성을 우선한다. |
| 영향 문서 | `07_backend_design.md`, `08_mvp_plan.md` |

확인 필요:

- 배포 환경에서 Python 3.11을 기본 런타임으로 사용할 수 있는지 확인한다.

### DEC-002 Dependency 관리 도구

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | `pyproject.toml` + lock file 기반 관리 |
| 도구 | `uv` |
| 근거 | 설치 속도, lock 재현성, 단순한 CLI를 우선한다. |
| 영향 문서 | `07_backend_design.md`, `08_mvp_plan.md`, `10_docker_environment.md` |

정책:

- dependency는 `pyproject.toml`에 정의한다.
- lock file은 `uv.lock`을 사용한다.
- Docker build와 CI는 `uv sync --frozen`을 사용한다.

### DEC-003 DB 접근 방식

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | sync SQLAlchemy 2.x + Alembic |
| 근거 | MVP worker가 PostgreSQL polling 방식이므로 sync stack이 단순하다. |
| 영향 문서 | `03_data_model.md`, `07_backend_design.md`, `08_mvp_plan.md` |

정책:

- 기존 raw 프로젝트의 `psycopg2` DAO를 서비스 런타임에서 직접 사용하지 않는다.
- migration은 Alembic으로 관리한다.

### DEC-004 Worker 방식

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | PostgreSQL polling worker |
| 근거 | MVP에서 broker 운영 복잡도를 줄인다. |
| 영향 문서 | `04_pipeline_jobs.md`, `07_backend_design.md`, `08_mvp_plan.md` |

정책:

- `FOR UPDATE SKIP LOCKED` 방식으로 pending job을 점유한다.
- Celery, RQ, Redis broker는 처리량 요구가 생기면 도입한다.

### DEC-005 Chroma 실행 형태

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | persistent directory 기반 Chroma |
| 근거 | MVP에서 별도 vector DB 서버 운영을 줄인다. |
| 영향 문서 | `02_hld.md`, `03_data_model.md`, `07_backend_design.md`, `08_mvp_plan.md` |

정책:

- MVP 구현에서는 하나의 Chroma persistent directory 안에 목적별 collection을 둔다.
- 혐오표현 예시 검색 collection은 `hate_speech_examples`를 기본값으로 둔다.
- 혐오표현 정의 문서 검색 collection은 `hate_speech_definitions`를 기본값으로 둔다.
- embedding provider와 collection 이름 목록은 `analysis_runs`에 저장한다.

### DEC-006 Raw 프로젝트 포함 방식

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | 추후 git submodule로 포함 |
| 대상 | `YouTubeHateSpeech/`, `hateSpeechRAG/` |
| 근거 | 현재 디렉토리는 raw 참조 자료이며, 서비스 런타임 코드와 분리해야 한다. |
| 영향 문서 | `02_hld.md`, `07_backend_design.md`, `08_mvp_plan.md` |

정책:

- submodule은 서비스 구현 코드가 아니라 참조 코드 위치로 둔다.
- 기존 DAO와 기존 DB schema는 서비스 런타임에서 직접 사용하지 않는다.
- 필요한 로직은 adapter로 감싸거나 새 `app/` 코드로 옮긴다.

확인 필요:

- submodule 경로를 `external/`, `vendor/`, `raw/` 중 어디로 둘지 결정한다.

### DEC-007 관리자 인증

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | `X-Admin-Token` 헤더 |
| 근거 | MVP에서 관리자 웹 화면과 계정 시스템을 제외했기 때문이다. |
| 영향 문서 | `05_api_spec.md`, `08_mvp_plan.md` |

정책:

- 관리자 API는 token 없이 접근할 수 없다.
- token 원문은 로그와 보고서에 저장하지 않는다.

### DEC-008 웹 보고서 렌더링

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | FastAPI server-side template |
| 근거 | React 기반 frontend 분리는 MVP 제외 범위다. |
| 영향 문서 | `06_report_spec.md`, `07_backend_design.md`, `08_mvp_plan.md` |

정책:

- 보고서 화면은 `report_snapshots.payload`를 기준으로 렌더링한다.
- React 분리는 MVP 이후 검토한다.

### DEC-009 파일 저장소

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | 로컬 파일 저장소 adapter |
| 저장 대상 | HTML export, Excel export, 자막 원문 파일 |
| 근거 | MVP에서 object storage 운영을 줄인다. |
| 영향 문서 | `02_hld.md`, `03_data_model.md`, `07_backend_design.md` |

정책:

- 파일 경로는 DB에 `file_uri` 또는 `source_uri`로 저장한다.
- object storage는 배포 요구가 생기면 adapter 교체로 도입한다.

### DEC-010 동일 영상 재분석

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | 동일 영상도 항상 새 analysis job 생성 |
| 근거 | MVP에서 계정 로그 기반 재분석 판단을 제외한다. |
| 영향 문서 | `00_project_brief.md`, `01_user_scenarios.md`, `03_data_model.md`, `04_pipeline_jobs.md`, `05_api_spec.md` |

정책:

- 기존 결과를 재사용하지 않는다.
- 같은 `youtube_video_id`라도 새 job, 새 snapshot, 새 analysis run을 만든다.

### DEC-011 댓글 분석 범위

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | 댓글과 대댓글은 항상 전체 수집 및 전체 분석 |
| 근거 | 사용자 결정 사항 |
| 영향 문서 | `00_project_brief.md`, `01_user_scenarios.md`, `04_pipeline_jobs.md`, `08_mvp_plan.md` |

정책:

- MVP API에 `comment_limit`를 제공하지 않는다.
- 수집 미완료 상태에서는 댓글 분석 성공으로 표시하지 않는다.

### DEC-012 자막 입력 방식

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | 공개 자막만 사용하고 외부 자막 업로드는 제외 |
| 근거 | 사용자 결정 사항 |
| 영향 문서 | `00_project_brief.md`, `01_user_scenarios.md`, `04_pipeline_jobs.md`, `05_api_spec.md`, `06_report_spec.md` |

정책:

- 공개 자막이 없으면 스크립트 분석을 skipped 또는 부분 실패로 표시한다.
- 외부 자막 파일 업로드 endpoint를 만들지 않는다.

### DEC-013 PDF export

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | PDF export는 MVP 제외 |
| 근거 | 사용자 결정 사항 |
| 영향 문서 | `00_project_brief.md`, `01_user_scenarios.md`, `05_api_spec.md`, `06_report_spec.md`, `08_mvp_plan.md` |

정책:

- MVP export format은 `html`, `xlsx`만 허용한다.
- PDF 요청은 거부한다.

### DEC-014 네트워크 그래프 저장 단위

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | 개별 대댓글 단위 edge 저장 |
| 근거 | 원천 관계를 보존하고 report summary에서 작성자 쌍 집계를 수행하기 위함이다. |
| 영향 문서 | `03_data_model.md`, `06_report_spec.md`, `07_backend_design.md` |

정책:

- node key는 `author_channel_id`를 우선한다.
- 개별 edge의 기본 `weight`는 1이다.
- 작성자 쌍 weight는 summary에서 집계한다.

### DEC-015 Secret 관리

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | MVP는 환경변수 기반 secret 관리 |
| 근거 | 로컬/초기 배포 복잡도를 줄인다. |
| 영향 문서 | `03_data_model.md`, `05_api_spec.md`, `07_backend_design.md` |

정책:

- secret 원문은 DB, 로그, 보고서에 저장하지 않는다.
- 관리자 API는 등록 여부와 최근 오류만 반환한다.
- secret manager는 배포 환경에서 필요해지면 도입한다.

### DEC-016 Docker 환경 분리

| 항목 | 값 |
| --- | --- |
| 상태 | 권장 |
| 결정 | `compose.yaml` + `compose.dev.yaml` + `compose.test.yaml` + `compose.prod.yaml` |
| 근거 | 공통 service 경계를 유지하면서 개발, 테스트, 운영의 volume, command, secret, 외부 노출 범위를 분리한다. |
| 영향 문서 | `02_hld.md`, `07_backend_design.md`, `08_mvp_plan.md`, `10_docker_environment.md` |

정책:

- web과 worker는 같은 Docker image를 사용하고 command만 분리한다.
- dev는 source bind mount와 reload를 허용한다.
- test는 fake YouTube, fake LLM을 기본값으로 둔다.
- prod는 source bind mount를 사용하지 않는다.
- PostgreSQL, report storage, Chroma data는 별도 volume으로 분리한다.

### DEC-017 Dual Vector Store RAG

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | 혐오표현 예시 vector store와 혐오표현 정의 문서 vector store를 함께 검색한다. |
| 근거 | 예시 기반 유사도만으로 분류하면 판단 기준 설명이 약해질 수 있다. 정의 문서 검색 결과를 함께 사용해 분류 근거와 보고서 설명 가능성을 높인다. |
| 영향 문서 | `00_project_brief.md`, `01_user_scenarios.md`, `02_hld.md`, `03_data_model.md`, `04_pipeline_jobs.md`, `05_api_spec.md`, `06_report_spec.md`, `07_backend_design.md`, `08_mvp_plan.md`, `10_docker_environment.md`, `11_definition_corpus_targets.md`, `13_rag_chunking_prompt_strategy.md` |

정책:

- 입력 텍스트 하나에 대해 예시 retriever와 정의 retriever를 모두 호출한다.
- LLM prompt에는 유사 혐오표현 예시와 관련 정의 문서 발췌를 구분해서 전달한다.
- 분석 결과에는 사용된 예시, 사용된 정의 문서, 각 retriever 설정을 남긴다.
- 정의 문서 corpus는 별도 seed/version을 관리한다.
- 한쪽 retriever가 실패하면 해당 분석 항목은 degraded 상태로 기록하고, 실패한 근거 출처를 명시한다.

### DEC-018 혐오 카테고리 우선 평가

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | MVP의 핵심 분석 단위는 혐오/비혐오 이진 판정이 아니라 혐오 카테고리다. |
| 근거 | 보고서의 주요 논점은 카테고리 분포, 대표 사례, 정치 혐오 세부 분류, 네트워크상의 카테고리 확산 양상이다. |
| 영향 문서 | `02_hld.md`, `03_data_model.md`, `04_pipeline_jobs.md`, `05_api_spec.md`, `06_report_spec.md`, `07_backend_design.md`, `08_mvp_plan.md`, `12_category_taxonomy.md` |

정책:

- `categories`는 보고서와 평가의 핵심 필드다.
- `is_hate_speech`는 카테고리 판단을 요약하는 보조 필드로 본다.
- UNSMILE은 기본 혐오 카테고리 평가에 사용하되 정치 혐오 카테고리 정답셋으로 보지 않는다.
- 정치 혐오 카테고리는 서비스 전용 gold dataset을 별도로 구축해 평가한다.
- 전체 댓글과 전체 스크립트 세그먼트를 분석하므로 프롬프트에서 입력이 이미 혐오표현이라고 가정하지 않는다.

### DEC-019 RAG 청킹과 프롬프트 계약

| 항목 | 값 |
| --- | --- |
| 상태 | 확정 |
| 결정 | RAG ingest와 분류 prompt는 `13_rag_chunking_prompt_strategy.md`의 계약을 따른다. |
| 근거 | RAG 출력이 DB, API, 보고서, 평가의 기준이 되므로 FastAPI 구현 전에 chunking, retrieval slot, prompt version, output validation을 고정해야 한다. |
| 영향 문서 | `02_hld.md`, `03_data_model.md`, `04_pipeline_jobs.md`, `05_api_spec.md`, `06_report_spec.md`, `07_backend_design.md`, `08_mvp_plan.md`, `11_definition_corpus_targets.md`, `12_category_taxonomy.md`, `13_rag_chunking_prompt_strategy.md` |

정책:

- `hate_speech_examples`는 dataset row 단위로 저장하고 별도 청킹하지 않는다.
- `hate_speech_definitions`는 internal taxonomy card와 외부 정의 문서를 의미 단위로 chunk한다.
- prompt에는 `taxonomy_context`, `definition_context`, `example_context`를 분리해 전달한다.
- 초기 prompt version은 `category-rag-v0.1.0`이다.
- output validation은 저장 전 필수로 수행한다.
- license tier가 `permission_required`인 corpus는 retrieval corpus에서 제외한다.

## 구현 전 사용자 확인 필요 항목

구현 착수 전에 다음 항목을 확인한다.

1. Python 3.11을 사용할지
2. raw 프로젝트 submodule 경로를 어디로 둘지
3. Chroma를 persistent directory로 시작할지
4. 관리자 인증을 `X-Admin-Token`으로 시작할지
5. server-side template로 웹 보고서를 먼저 만들지
6. Docker prod profile에 reverse proxy를 포함할지
7. 혐오표현 정의 문서 corpus의 출처와 versioning 방식을 어떻게 둘지
8. 서비스 전용 gold dataset의 초기 라벨링 규모와 검토자를 어떻게 둘지
9. `sharealike_review` tier corpus를 public demo에 포함할지

## 관련 문서 반영 기준

결정이 바뀌면 다음 문서를 함께 확인한다.

| 결정 영역 | 확인 문서 |
| --- | --- |
| MVP 범위 | `00_project_brief.md`, `01_user_scenarios.md` |
| runtime 구성 | `02_hld.md`, `07_backend_design.md`, `08_mvp_plan.md` |
| DB와 저장 정책 | `03_data_model.md` |
| job 처리 | `04_pipeline_jobs.md` |
| API 표면 | `05_api_spec.md` |
| 보고서와 export | `06_report_spec.md` |
| Docker와 실행 환경 | `10_docker_environment.md` |
| 정의 corpus 수집 대상 | `11_definition_corpus_targets.md` |
| 카테고리와 평가 기준 | `12_category_taxonomy.md` |
| RAG 청킹과 프롬프트 | `13_rag_chunking_prompt_strategy.md` |

## 검증 기준

이 문서는 다음 조건을 만족해야 한다.

- 구현 전 결정 후보가 한 곳에 모여 있다.
- 확정된 사용자 결정과 권장 기본값이 구분된다.
- raw 프로젝트 포함 방식이 서비스 런타임 경계와 충돌하지 않는다.
- 결정 변경 시 영향 문서를 추적할 수 있다.
