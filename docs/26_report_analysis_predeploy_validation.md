# 보고서·RAG 방법론 개선 배포 전 검증

## 1. 범위와 완료 기준

기준일은 2026-07-16이다. 외부 환경 배포와 트래픽 전환은 수행하지 않고, 로컬 배포 구성을 새 이미지로 재생성해 배포 직전 상태까지 검증했다.

| 요구사항 | 구현 결과 | 검증 |
| --- | --- | --- |
| category/전체 혐오 댓글 panel 높이 | 두 panel을 650px로 맞추고 내부 목록만 scroll | production build와 실제 보고서 화면 |
| category 가독성 | label/count 글자 확대, 7개 이하는 scroll 없음, 8개 이상 category 영역 scroll | 7/8개 경계 로직과 실제 화면 |
| network 좌측 1/3 지표 | 작성자·관계·평균 차수·방향 밀도 제공 | component test와 실제 보고서 화면 |
| edge 선택 상세 | 중복 edge 집계, 빈도 기반 굵기, 혐오 수·비율·방향 표시 | component test 11건 묶음에 포함 |
| History thumbnail | 완료 job의 report를 추가 조회해 실제 thumbnail/title 표시 | 브라우저 localStorage 기반 실환경 DOM 확인 |
| 한국어 분석 사유 | prompt v0.3.0에서 한국어 사유를 요구하고 validator가 한글 없는 사유를 거부 | 실제 Upstage+Anthropic 1건과 backend test |
| Excel 한국어 표시 | 댓글·자막 sheet의 사유 열 제목을 `분석 사유`로 표시 | 실제 XLSX 생성·재개방 |
| 사회과학적 함의 | 분석 단위, 조작화, 해석 범위, 타당도·편향·윤리·인과 경계를 화면과 문서에 추가 | frontend test, desktop/mobile 화면, 재현 문서 test |

## 2. 브랜치와 병합 순서

브랜치는 병합 후 삭제하지 않았다.

1. `feat/report-layout-history-thumbnails`
   - feature commit: `0a4a94c`
   - merge commit: `546e3ae`
2. `feat/network-metrics-edge-details`
   - feature commit: `402a989`
   - merge commit: `2cfda81`
3. `feat/korean-reasoning-excel`
   - feature commit: `95a2301`
   - merge commit: `8059db1`
4. `feat/rag-social-science-implications`
   - feature commit: `af2fe3b`
   - merge commit: `0a1384a`
5. `chore/report-analysis-predeploy-validation`
   - 통합 검증과 이 문서를 기록한 후 `main`에 병합한다.

## 3. 정적·자동 검증

```bash
uv run ruff check .
uv run python -m compileall -q app scripts experiments tests
uv run pytest -q
```

결과: Ruff와 compileall 성공, backend `96 passed, 1 skipped`.

```bash
cd frontend
npm test -- --run
npm run build
```

결과: frontend `11 passed`, TypeScript와 Vite production build 성공. Cytoscape graph는 별도 dynamic chunk로 유지됐다.

```bash
docker compose --env-file /dev/null -f compose.yaml -f compose.dev.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.test.yaml config --quiet
docker compose --env-file /dev/null -f compose.yaml -f compose.prod.yaml config --quiet
```

결과: dev/test/prod 세 구성이 모두 유효하다.

## 4. 실행 환경 검증

다음 명령으로 개발 frontend/web/worker 이미지를 새 코드로 재생성했다. PostgreSQL, Chroma, report named volume은 보존했다.

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build frontend web worker
```

확인 결과:

- frontend: healthy, host port 3000
- web: healthy, host port 8000
- worker: running
- `GET /health`: `{"status":"ok"}`

### 4.1 실제 RAG provider smoke

중립 댓글 1건을 실행 중인 worker container에서 실제 Upstage embedding과 Anthropic 분류로 호출했다. 원문과 모델 사유는 증적에 저장하지 않고 계약 상태만 확인했다.

```json
{
  "prompt_version": "category-rag-v0.3.0",
  "valid": true,
  "reasoning_has_hangul": true,
  "attempts": 1,
  "rag_context_status": "definition_only",
  "model": "claude-haiku-4-5-20251001",
  "usage": {"input_tokens": 2104, "output_tokens": 277}
}
```

`definition_only`는 중립 입력에서 similarity 0.40을 넘는 example이 없었던 정상적인 부분 context 상태다.

### 4.2 실제 Excel export

report `0825e981-27b1-49a2-851b-0ca53ed6a759`에서 XLSX export를 새로 생성하고 openpyxl로 다시 열었다.

- sheet: `summary`, `comment_analysis`, `script_analysis`, `network_nodes`, `network_edges`
- `comment_analysis!G1`: `분석 사유`
- `script_analysis!H1`: `분석 사유`

기존 분석 row의 사유는 원문 보존을 위해 소급 번역하지 않는다. prompt v0.3.0 적용 이후 새 분석부터 한국어 사유 계약을 따른다.

### 4.3 History thumbnail

브라우저 origin의 `sentinel-yt:jobs`에 완료 job을 넣고 `/history`를 열어 비동기 report 조회가 끝난 뒤 DOM을 확인했다.

- image: 실제 `i.ytimg.com` thumbnail URL
- title: 실제 video title
- video ID fallback element: 없음

## 5. 배포 경계

애플리케이션 코드, migration 정합성, production frontend build, 세 Compose 변형, 실제 외부 provider와 실행 container까지 확인했다. 남은 작업은 대상 서버에서 production secret과 domain/TLS를 적용해 이미지를 올리고 트래픽을 전환하는 운영 배포뿐이다.
