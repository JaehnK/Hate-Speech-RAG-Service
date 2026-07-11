# 배포 전 완료 감사

| 항목 | 값 |
| --- | --- |
| 감사일 | 2026-07-11 |
| 대상 | `docs/08_mvp_plan.md`의 MVP 완료 정의와 Phase 0–14 |
| 완료 기준 | 외부 secret 주입 후 실제 API E2E만 실행하면 되는 배포 직전 상태 |

## 단계별 증적

| 단계 | 판정 | 구현/검증 증적 | 남은 외부 검증 |
| --- | --- | --- | --- |
| Phase 0 결정 | 완료 | `docs/09_implementation_decisions.md`, `.env.example`, 분리된 Compose | 없음 |
| Phase 0.5 RAG PoC | 완료 | dual collection ingest, license gate, prompt validator, retrieval tests, experiment/evaluation runner | 실제 모델 품질 수치는 API key와 실제 gold set 필요 |
| Phase 1 scaffold | 완료 | FastAPI app factory, health/readiness, web/worker entrypoint, runtime image | 없음 |
| Phase 2 DB | 완료 | 전체 SQLAlchemy 모델, 불변 Alembic revision, SQLite/PostgreSQL up/down | 없음 |
| Phase 3 job/worker | 완료 | Job API, `FOR UPDATE SKIP LOCKED`, 10-step orchestrator, fake E2E | 없음 |
| Phase 4 metadata | 구현 완료 | YouTube Data API adapter, snapshot, 오류 변환, mock integration | 실제 video 호출에 YouTube key 필요 |
| Phase 5 comments | 구현 완료 | thread/reply pagination, partial 보존, retry upsert, quota event | 실제 전체 댓글 수 대조에 YouTube key 필요 |
| Phase 6 transcript | 구현 완료 | 공개 자막 adapter, 정규화/segment, 없음/오류 처리 | 공개 영상 live 검증 필요 |
| Phase 7 RAG adapter | 구현 완료 | dual retrieval, degraded context, collection/corpus metadata, LLM error 변환 | Anthropic/Upstage key로 live 검증 필요 |
| Phase 8–9 분석 | 완료 | comment/script 전 항목 결과 저장과 부분 실패 테스트 | 실제 모델 품질 검증 필요 |
| Phase 10 network | 완료 | node/edge/degree/혐오 비율, self-edge summary | 없음 |
| Phase 11 report | 완료 | immutable snapshot, summary/detail/network API | 없음 |
| Phase 12 web/export | 완료 | escaped HTML, HTML/XLSX, 5개 sheet, download | container export 검증 완료 |
| Phase 13 admin | 완료 | token 인증, masking, retry, logs/quota/settings | 없음 |
| Phase 14 E2E | 조건부 완료 | PostgreSQL+web+worker fake Compose E2E 성공 | 정상/댓글 비활성/자막 없음 실제 영상은 API keys 필요 |

## 명시적 불변 조건

- 같은 video ID 요청은 새 job을 만든다.
- 댓글 수집이 완료되지 않으면 부분 snapshot은 보존하지만 댓글 분석은 실행하지 않는다.
- 자막 실패는 댓글 분석을 무효화하지 않는다.
- 분석 결과는 원천 snapshot을 수정하지 않는다.
- report snapshot은 생성 후 수정하지 않고 재시도 시 새 snapshot을 만든다.
- secret 원문은 DB/API/report/log에 저장하거나 반환하지 않는다.
- permission/review license tier corpus는 기본 retrieval에서 제외한다.
- Chroma HTTP server와 model repository 입력은 공개 surface에 존재하지 않는다.

## 자동 검증 게이트

```bash
uv run ruff check app tests experiments alembic
uv run python -m compileall -q app tests experiments alembic
uv run pytest -q
uv run pip-audit --ignore-vuln PYSEC-2026-311
docker compose --env-file /dev/null -f compose.yaml -f compose.dev.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.test.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.prod.yaml config --quiet
```

## 배포 승인 전 외부 증적

다음만 repository 내부에서 secret 없이 검증할 수 없다.

1. YouTube 정상 영상 metadata/전체 댓글/대댓글 수 대조
2. 댓글 비활성 영상의 `partial_success`
3. 공개 자막 없는 영상의 `partial_success`
4. Anthropic + Upstage 실제 dual-RAG 분류
5. 실제 익명화 gold set의 baseline 대비 dual-RAG 품질과 3회 안정성

외부 검증 결과는 별도 `chore/live-e2e-validation` 브랜치에서 이 문서에 기록하고 검증 후 `main`에 병합한다.
