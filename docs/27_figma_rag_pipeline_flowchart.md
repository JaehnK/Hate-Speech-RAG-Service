# Figma 기반 RAG 호출 흐름도

## 1. 목적

RAG 방법론 화면의 기존 8개 step card는 순서만 보여주고 이중 검색의 fan-out/fan-in, validation retry, item 실패와 부분 성공의 합류를 설명하지 못했다. 실제 실행 구조를 이해할 수 있도록 Figma FigJam에서 먼저 흐름도를 설계한 뒤 같은 정보 구조를 웹 SVG로 구현했다.

- 브랜치: `feat/figma-rag-pipeline-flowchart`
- FigJam: [YouTube 혐오표현 Dual-Vector RAG 호출 흐름](https://www.figma.com/board/sGQ5uzigH8gTdLRYVGDM6X)
- Figma file key: `sGQ5uzigH8gTdLRYVGDM6X`
- 웹 경로: `/rag-methodology` (공개 화면에서는 provider, 임계값, 오류 코드와 설계 원본 링크를 제외)

## 2. 설계 순서

1. `app/worker_main.py`, `app/analysis/executor.py`, `app/analysis/rag_classifier.py`, `app/analysis/retriever.py`를 기준으로 실제 실행 경계를 확인했다.
2. Figma `figma-generate-diagram` 지침과 flowchart reference를 읽고 Mermaid flowchart를 작성했다.
3. FigJam에 비동기 Job, item별 Dual-Vector RAG, 집계와 보고서의 세 phase를 생성했다.
4. FigJam 결과의 도형 의미와 연결 관계를 유지하면서 웹 폭에 맞는 세로 phase lane SVG로 옮겼다.
5. 데스크톱과 모바일 실제 화면에서 화살표, 분기 label, 글자 크기와 overflow를 확인했다.

## 3. 표현 계약

| 표현 | 의미 |
| --- | --- |
| 둥근 사각형 | 시작과 종료 |
| 평행사변형 | 분석 item 입력 구성 |
| 육각형 | bounded 병렬 worker pool |
| 원통 | definition/example vector store |
| 마름모 | similarity, validation, retry decision |
| 원 | definition/example 근거의 fan-in |
| 굵은 실선 | worker pool에서 item 병렬 처리로 진입 |
| 점선 | threshold 제외, validation 실패, retry와 부분 성공 |
| 녹색 | 저장·보고서 성공 경로 |
| 붉은색 | item 실패 기록 |

## 4. 실제 실행과의 대응

- API는 분석 요청을 HTTP 202로 접수하고 pending job을 저장한다.
- worker는 공개 metadata, 댓글·답글, 자막을 수집하고 분석 item을 구성한다.
- 현재 실행값은 bounded pool을 통한 item 병렬 처리다.
- 한 item은 query embedding 후 definition/example collection을 조회한다.
- example은 `score >= 0.40`만 근거에 포함하고 definition 결과와 합친다.
- prompt 조립과 Claude JSON 분류 후 output contract를 검증한다.
- 실패하면 validation error를 넣은 교정 prompt로 한 번 재시도한다.
- item 실패도 기록하며 성공 결과와 함께 집계되어 job이 `partial_success`가 될 수 있다.
- 집계 이후 댓글 network와 report snapshot을 생성한다.

## 5. 구현과 검증

- `frontend/src/RagPipelineFlow.tsx`: 접근 가능한 SVG title/description, node/edge data와 Figma 원본 link
- `frontend/src/styles.css`: phase 색상, 도형·edge 상태, mobile horizontal pan과 안내
- `frontend/src/RagMethodologyPage.test.tsx`: 핵심 decision과 Figma URL 계약

검증 명령:

```bash
cd frontend
npm test -- --run
npm run build
```

브라우저 검증 해상도:

- desktop: 1440 × 1500
- mobile: 390 × 1600

모바일에서는 SVG의 최소 폭을 유지하고 flow container만 가로 이동하도록 해 글자를 축소하지 않는다.

마지막으로 `docker compose -f compose.yaml -f compose.dev.yaml up -d --build frontend`를 실행해 개발 frontend image를 재생성했으며, `/rag-methodology` 응답과 container health가 정상임을 확인했다.

## 6. 사용자 수정 FigJam 동기화

사용자가 FigJam을 직접 다듬은 뒤 같은 file key의 root node를 다시 읽어 웹 구현과 비교했다.

- 동기화 브랜치: `feat/sync-refined-figjam-rag-flow`
- 세 phase를 위에서 아래로 읽는 구조는 기존 웹 구현과 일치해 유지했다.
- 수정본처럼 사례 Store를 위에 놓고 `사례 → 유사도 판단 → 근거 결합`을 우선 흐름으로 표시했다.
- 정의 Store는 별도 검색 결과로 근거 결합에 직접 합류하도록 이동했다.
- validation 실패 이후 `재시도 판단 → 교정 Prompt → Claude 재호출` 순서가 왼쪽에서 오른쪽으로 읽히도록 재배치했다.
- FigJam의 매우 넓은 RAG section을 그대로 축소하지 않고, 웹에서는 phase 폭과 글자 크기를 유지하면서 connector 교차를 최소화했다.

동기화 후 frontend test 11건, production build와 1440 × 1500 실제 화면을 다시 확인했다.
