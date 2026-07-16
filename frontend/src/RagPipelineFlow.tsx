const FIGMA_FLOW_URL = "https://www.figma.com/board/sGQ5uzigH8gTdLRYVGDM6X";

type FlowNode = {
  id: string;
  type: "start" | "process" | "input" | "pool" | "store" | "decision" | "merge" | "success" | "failure";
  x: number;
  y: number;
  width: number;
  height: number;
  title: string;
  detail: string;
};

const NODES: FlowNode[] = [
  { id: "request", type: "start", x: 40, y: 74, width: 140, height: 56, title: "분석 요청", detail: "YouTube URL" },
  { id: "accept", type: "process", x: 230, y: 74, width: 140, height: 56, title: "API 202 접수", detail: "pending job" },
  { id: "collect", type: "process", x: 420, y: 74, width: 140, height: 56, title: "공개 데이터 수집", detail: "댓글 · 자막" },
  { id: "items", type: "input", x: 610, y: 70, width: 150, height: 64, title: "분석 Item 구성", detail: "comment · reply · segment" },
  { id: "pool", type: "pool", x: 810, y: 68, width: 160, height: 68, title: "병렬 Worker Pool", detail: "bounded concurrency" },
  { id: "embed", type: "process", x: 50, y: 320, width: 150, height: 62, title: "검색 Query 임베딩", detail: "Upstage query vector" },
  { id: "examples", type: "store", x: 240, y: 235, width: 160, height: 68, title: "사례 Store", detail: "example k=6" },
  { id: "definitions", type: "store", x: 240, y: 410, width: 160, height: 68, title: "정의 Store", detail: "taxonomy 4 + definition 4" },
  { id: "similarity", type: "decision", x: 430, y: 225, width: 150, height: 96, title: "유사도 0.40 이상?", detail: "score gate" },
  { id: "evidence", type: "merge", x: 610, y: 310, width: 90, height: 90, title: "근거", detail: "결합" },
  { id: "prompt", type: "process", x: 735, y: 326, width: 140, height: 60, title: "Prompt 조립", detail: "rules + 3 contexts" },
  { id: "classify", type: "process", x: 910, y: 326, width: 130, height: 60, title: "Claude 분류", detail: "valid JSON" },
  { id: "validate", type: "decision", x: 1050, y: 306, width: 130, height: 100, title: "JSON 계약 통과?", detail: "schema + category" },
  { id: "retry", type: "decision", x: 610, y: 490, width: 140, height: 96, title: "재시도 남음?", detail: "최대 2회" },
  { id: "correct", type: "process", x: 800, y: 508, width: 140, height: 60, title: "교정 Prompt", detail: "validation errors" },
  { id: "persist", type: "success", x: 1020, y: 490, width: 150, height: 62, title: "분류 결과 저장", detail: "판정 + RAG 근거" },
  { id: "fail", type: "failure", x: 610, y: 600, width: 140, height: 48, title: "Item 실패 기록", detail: "LLM_ERROR" },
  { id: "aggregate", type: "process", x: 250, y: 735, width: 150, height: 60, title: "판정 결과 집계", detail: "성공 · 실패 포함" },
  { id: "network", type: "process", x: 480, y: 735, width: 150, height: 60, title: "댓글 Network", detail: "node · edge" },
  { id: "report", type: "success", x: 710, y: 735, width: 150, height: 60, title: "분석 보고서", detail: "HTML · XLSX" },
  { id: "complete", type: "start", x: 960, y: 735, width: 170, height: 60, title: "Job 완료", detail: "partial_success 포함" },
];

const EDGES = [
  ["M180 102 H230"], ["M370 102 H420"], ["M560 102 H610"], ["M760 102 H810"],
  ["M970 102 H1000 V180 H125 V320", "critical"],
  ["M200 340 H220 V269 H240"], ["M200 362 H220 V444 H240"],
  ["M400 269 H430"], ["M400 444 H565 V370 H610"],
  ["M580 273 H600 V335 H610"], ["M545 300 H590 V380 H610", "optional"],
  ["M700 355 H735"], ["M875 356 H910"], ["M1040 356 H1050"],
  ["M1115 406 V490", "success"], ["M1115 406 V458 H680 V490", "optional"],
  ["M750 538 H800", "optional"], ["M940 538 H975 V386", "optional"],
  ["M680 586 V600", "failure"],
  ["M1095 552 V680 H325 V735", "success"], ["M680 648 V695 H325 V735", "optional"],
  ["M400 765 H480"], ["M630 765 H710"], ["M860 765 H960"],
] as const;

export function RagPipelineFlow() {
  return (
    <div className="rag-flow-wrap">
      <div className="rag-flow-scroll" tabIndex={0} aria-label="RAG 호출 흐름도, 좁은 화면에서는 좌우로 이동할 수 있습니다">
        <svg className="rag-flowchart" viewBox="0 0 1200 835" role="img" aria-labelledby="rag-flow-title rag-flow-desc">
          <title id="rag-flow-title">YouTube 혐오표현 Dual-Vector RAG 호출 흐름</title>
          <desc id="rag-flow-desc">비동기 분석 작업 접수부터 병렬 item 처리, 정의와 사례 검색, 유사도 분기, JSON 검증과 교정 재시도, 결과 집계와 보고서 생성까지의 흐름</desc>
          <defs>
            <marker id="rag-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
          </defs>

          <Phase x={20} y={20} width={1160} height={140} title="01 · 비동기 Job" className="job" />
          <Phase x={20} y={185} width={1160} height={470} title="02 · Item별 Dual-Vector RAG" className="rag" />
          <Phase x={20} y={680} width={1160} height={140} title="03 · 집계와 보고서" className="report" />

          <g className="flow-edges">
            {EDGES.map(([path, kind = ""], index) => <path className={`flow-edge ${kind}`} d={path} key={index} markerEnd="url(#rag-arrow)" />)}
          </g>
          <EdgeLabel x={588} y={258}>사용</EdgeLabel>
          <EdgeLabel x={563} y={316}>제외</EdgeLabel>
          <EdgeLabel x={1088} y={450}>통과</EdgeLabel>
          <EdgeLabel x={900} y={448}>실패</EdgeLabel>
          <EdgeLabel x={775} y={528}>있음</EdgeLabel>
          <EdgeLabel x={692} y={606}>없음</EdgeLabel>
          <EdgeLabel x={635} y={688}>부분 성공</EdgeLabel>

          {NODES.map((node) => <Node {...node} key={node.id} />)}
        </svg>
      </div>
      <div className="rag-flow-footer">
        <span className="rag-flow-mobile-hint">흐름도를 좌우로 이동해 전체 분기를 확인하세요.</span>
        <div className="rag-flow-legend"><span><i className="solid" />순차 흐름</span><span><i className="thick" />병렬 진입</span><span><i className="dotted" />조건·재시도</span></div>
        <a href={FIGMA_FLOW_URL} target="_blank" rel="noreferrer">FigJam 설계 원본 열기 ↗</a>
      </div>
    </div>
  );
}

function Phase({ x, y, width, height, title, className }: { x: number; y: number; width: number; height: number; title: string; className: string }) {
  return <g className={`flow-phase ${className}`}><rect x={x} y={y} width={width} height={height} rx="12" /><text x={x + 20} y={y + 28}>{title}</text></g>;
}

function EdgeLabel({ x, y, children }: { x: number; y: number; children: string }) {
  return <text className="flow-edge-label" x={x} y={y}>{children}</text>;
}

function Node(node: FlowNode) {
  const { x, y, width, height, title, detail, type } = node;
  const centerX = x + width / 2;
  const centerY = y + height / 2;
  let shape = <rect className="flow-node-shape" x={x} y={y} width={width} height={height} rx={type === "start" ? height / 2 : 7} />;
  if (type === "input") shape = <polygon className="flow-node-shape" points={`${x + 14},${y} ${x + width},${y} ${x + width - 14},${y + height} ${x},${y + height}`} />;
  if (type === "pool") shape = <polygon className="flow-node-shape" points={`${x + 18},${y} ${x + width - 18},${y} ${x + width},${centerY} ${x + width - 18},${y + height} ${x + 18},${y + height} ${x},${centerY}`} />;
  if (type === "decision") shape = <polygon className="flow-node-shape" points={`${centerX},${y} ${x + width},${centerY} ${centerX},${y + height} ${x},${centerY}`} />;
  if (type === "merge") shape = <ellipse className="flow-node-shape" cx={centerX} cy={centerY} rx={width / 2} ry={height / 2} />;
  if (type === "store") shape = <><rect className="flow-node-shape" x={x} y={y + 8} width={width} height={height - 16} /><ellipse className="flow-node-shape store-top" cx={centerX} cy={y + 8} rx={width / 2} ry="8" /><path className="store-bottom" d={`M${x} ${y + height - 8} A${width / 2} 8 0 0 0 ${x + width} ${y + height - 8}`} /></>;
  return (
    <g className={`flow-node ${type}`} data-node={node.id}>
      {shape}
      <text className="flow-node-title" x={centerX} y={centerY - 3}>{title}</text>
      <text className="flow-node-detail" x={centerX} y={centerY + 15}>{detail}</text>
    </g>
  );
}
