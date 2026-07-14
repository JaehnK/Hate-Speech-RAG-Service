# 배포 전 실행 절차

## 1. Secret 준비

- `ADMIN_TOKEN`: 충분히 긴 무작위 값
- `POSTGRES_PASSWORD`: 운영 전용 값
- `YOUTUBE_API_KEY`: YouTube Data API v3 활성화 키
- `ANTHROPIC_API_KEY`: 분류 모델 호출 키
- `UPSTAGE_API_KEY`: embedding 호출 키

키 원문은 DB, Git, 보고서, command history에 기록하지 않는다. 배포 플랫폼의 secret manager 또는 보호된 환경변수로 주입한다.

## 2. Corpus 생성

라이선스가 허용된 production corpus는 다음 one-shot 서비스로 named volume에 생성한다. 실제 전체 적재는 limit 없이 실행하며, 외부 API 연결 smoke에만 `--limit-per-dataset`을 사용한다.

```bash
docker compose --profile tools run --rm corpus
```

1. dataset source revision과 license tier를 확인한다.
2. internal taxonomy를 `hate_speech_definitions`에 ingest한다.
3. 허용된 외부 definition 문서를 같은 collection에 추가한다.
4. 허용된 example dataset만 `hate_speech_examples`에 ingest한다.
5. 두 collection의 document count와 retrieval smoke test를 확인한다.

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
```

운영 DB에서는 downgrade를 실행하지 않고 staging의 빈 DB에서만 왕복 검증한다.

`PYSEC-2026-311` 예외의 도달 불가능 조건과 제거 기준은 `SECURITY.md`에 고정한다. Chroma HTTP server mode는 upstream 수정 전 금지한다.

## 4. 실제 API E2E

1. 댓글과 공개 자막이 있는 공개 영상으로 job을 생성한다.
2. 모든 step이 끝날 때까지 status API를 polling한다.
3. metadata, 전체 댓글/대댓글, transcript segment 수를 원천 응답과 대조한다.
4. comment/script 결과 수가 각 snapshot/segment 수와 일치하는지 확인한다.
5. report page, JSON 상세 API, network, HTML/XLSX export를 확인한다.
6. 댓글 비활성 영상과 자막 없는 영상으로 `partial_success` 경로를 각각 확인한다.
7. 로그, 관리자 API, report/export 파일에서 secret 문자열이 검색되지 않는지 확인한다.

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
- `haiku_only`, `definitions_only`, `examples_only`, `dual_rag` 동일 입력 비교
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
