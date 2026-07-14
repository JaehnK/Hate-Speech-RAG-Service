# 배포 전 완료 감사

| 항목 | 값 |
| --- | --- |
| 최초 감사일 | 2026-07-11 |
| 최종 감사일 | 2026-07-14 |
| 대상 | `docs/08_mvp_plan.md`의 MVP 완료 정의와 Phase 0–14 |
| 완료 기준 | 구현·자동 게이트·실제 외부 API E2E가 통과하고, 운영 승인 항목만 남은 배포 직전 상태 |

## 단계별 판정

| 단계 | 판정 | 구현/검증 증적 |
| --- | --- | --- |
| Phase 0 결정 | 완료 | 결정 문서, `.env.example`, dev/test/prod Compose |
| Phase 0.5 RAG PoC | 구현·live smoke 완료 | dual collection, license gate, prompt/output validator, Upstage 실제 ingest/retrieval, Anthropic 3회 반복 |
| Phase 1 scaffold | 완료 | FastAPI app factory, health/readiness, web/worker entrypoint, runtime image |
| Phase 2 DB | 완료 | 전체 SQLAlchemy 모델, 불변 Alembic revision, SQLite/PostgreSQL upgrade/downgrade/upgrade |
| Phase 3 job/worker | 완료 | Job API, `FOR UPDATE SKIP LOCKED`, 10-step orchestrator, fake/live E2E |
| Phase 4 metadata | 완료 | 공식 YouTube Data API adapter와 실제 영상 호출 |
| Phase 5 comments | 완료 | thread/reply pagination, partial 보존, quota event, 정상/댓글 비활성 실제 호출 |
| Phase 6 transcript | 완료 | 공개 자막 정규화/segment, 있음/없음 실제 호출 |
| Phase 7 RAG adapter | 완료 | dual retrieval, degraded context, prompt v0.2, similarity 0.40 gate, run/report config 추적 |
| Phase 8–9 분석 | 완료 | comment/script 전 항목 결과 저장, 실제 Anthropic 분석, snapshot/result count 일치 |
| Phase 10 network | 완료 | node/edge/degree/혐오 비율, self-edge summary, live API |
| Phase 11 report | 완료 | immutable snapshot, summary/detail/network API, retriever/prompt config 기록 |
| Phase 12 web/export | 완료 | escaped HTML, HTML/XLSX, 5개 sheet, live 6개 export 다운로드 |
| Phase 13 admin | 완료 | token 인증, masking, retry, logs/quota/settings, live secret scan |
| Phase 14 E2E | 완료 | production Compose에서 정상/댓글 비활성/자막 없음 세 시나리오 통과 |

상세 수치와 교정 과정은 `docs/17_live_validation_evidence.md`에 기록한다.

## 명시적 불변 조건

- 같은 video ID 요청은 새 job을 만든다.
- 댓글 수집이 완료되지 않으면 부분 snapshot은 보존하지만 댓글 분석은 실행하지 않는다.
- 자막 실패는 댓글 분석을 무효화하지 않는다.
- 분석 결과는 원천 snapshot을 수정하지 않는다.
- report snapshot은 생성 후 수정하지 않고 재시도 시 새 snapshot을 만든다.
- secret 원문은 DB/API/report/log에 저장하거나 반환하지 않는다.
- permission/review license tier corpus는 기본 retrieval에서 제외한다.
- prompt에는 example 본문·라벨을 JSON data로 전달하고 입력/retrieval text를 지시로 신뢰하지 않는다.
- similarity 0.40 미만 example은 분류 prompt와 사용 후보에서 제외한다.
- Chroma HTTP server와 model repository 입력은 공개 surface에 존재하지 않는다.

## 최종 자동 검증 게이트

```bash
uv run ruff check app tests experiments scripts alembic
uv run python -m compileall -q app tests experiments scripts alembic
uv run pytest -q
uv run pip-audit --ignore-vuln PYSEC-2026-311
docker compose --env-file /dev/null -f compose.yaml -f compose.dev.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.test.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.prod.yaml config --quiet
```

`PYSEC-2026-311`은 Chroma HTTP server endpoint 취약점이다. 이 프로젝트는 embedded `PersistentClient`만 사용하고 해당 server/API/model repository를 노출하지 않으므로 `SECURITY.md`의 제한된 예외를 적용한다.

최종 repository gate는 Ruff, compileall, pytest 69개, dependency audit(문서화된 예외 1건), dev/test/prod Compose config를 모두 통과했다.

## 실제 외부 검증 판정

- YouTube 정상 metadata/comment/transcript: 통과
- 댓글 비활성 `partial_success`: 통과
- 공개 자막 없음 `partial_success`: 통과
- Anthropic + Upstage dual RAG 실행: 통과
- HTML/XLSX, 관리자 API, secret scan: 통과
- prompt `category-rag-v0.2.0` 및 retriever threshold `0.40` report 추적: 통과
- 합성 smoke 3회 안정성: 통과(운영 품질 지표로 사용 금지)

## 실제 배포 승인 시 별도 확인

다음은 배포 직전 구현 완료와 구분되는 운영 승인 작업이다.

1. limit 없는 전체 K-HATERS corpus 적재와 collection count/retrieval 확인
2. 익명화한 실제 댓글·스크립트 gold set의 2인 독립 라벨링과 불일치 조정
3. 실제 gold에서 네 variant 비교 및 dual RAG 비열화 확인
4. 운영 secret manager, TLS ingress, PostgreSQL backup/restore, volume snapshot 확인
5. YouTube quota와 Anthropic/Upstage 비용·rate limit 경보 확인

이 항목은 사람·운영 인프라가 필요한 배포 승인 조건이며 코드 구현 미완료로 간주하지 않는다.
