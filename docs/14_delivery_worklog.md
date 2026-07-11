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

## 외부 검증 대기 항목

- YouTube Data API 실제 metadata/comment 수집: `YOUTUBE_API_KEY` 필요
- 실제 LLM RAG 품질 실험: `ANTHROPIC_API_KEY` 필요
- Upstage embedding 실제 corpus ingest: `UPSTAGE_API_KEY` 필요
- API 키 없이 fake client와 deterministic embedding으로 전체 경로를 먼저 검증한다.
