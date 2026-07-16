# 상호작용 댓글 네트워크 구현 기록

## 문제 진단

- 보고서 화면은 `network_summary`의 node/edge 수만 읽고 네 개의 고정 점을 표시했다.
- 백엔드는 이미 `CommentNetworkBuilder`에서 작성자별 node, 답글 관계 edge, degree와 혐오표현 비율을 계산해 저장한다.
- `/api/reports/{report_id}/network`도 실제 node/edge 전체를 반환하지만 프론트가 호출하지 않았다.

## 구현 결정

- 브랜치: `feat/interactive-comment-network`
- NetworkX를 추가하지 않았다. 현재 서버 계산과 API 계약이 필요한 관계 지표를 이미 제공하며 NetworkX 자체는 브라우저 렌더러가 아니기 때문이다.
- 브라우저 렌더링에는 Cytoscape.js `3.34.0`의 CoSE force-directed layout을 사용했다.
- 그래프 엔진은 보고서 화면에서만 dynamic import해 분석 요청과 작업 화면의 초기 bundle에 포함하지 않았다.

## 표시 규칙

- node는 댓글 작성자이며 크기는 댓글 수와 연결 차수에 비례한다.
- 혐오표현이 하나라도 포함된 작성자는 crimson, 나머지는 navy로 표시한다.
- edge는 답글 작성자에서 원댓글 작성자로 향하며 혐오표현 답글은 crimson으로 표시한다.
- degree 2 이상 작성자는 기본 label을 표시하고 나머지는 선택 시 label과 상세 지표를 표시한다.
- 답글 관계보다 고립 작성자가 많은 보고서는 `연결 중심`을 기본으로 사용하고 `전체 노드` 전환을 제공한다.

## 상호작용

- node drag
- 배경 drag pan
- mouse wheel/trackpad/pinch zoom
- 확대, 축소, 화면 맞춤과 layout 재계산 버튼
- node 선택 시 댓글 수, 혐오표현 수·비율, 전체/in/out degree 상세 panel
- desktop/mobile 반응형 toolbar와 빈 network 상태

## 검증

- 실제 report `0825e981-27b1-49a2-851b-0ca53ed6a759`의 218 nodes/38 edges API 응답과 브라우저 렌더링을 비교했다.
- 연결 중심 화면에서 실제 방향 edge, 위험 node/edge 색상, hub label과 controller가 렌더링되는 것을 확인했다.
- 500px mobile viewport와 node 0/edge 0 보고서의 명시적 empty state를 확인했다.
- node/edge 변환, 고립 작성자 filter와 empty state frontend 회귀 테스트를 추가했다.
- frontend test/build, backend reporting API 회귀, Ruff, Compose config와 production frontend image build를 merge gate로 사용한다.
