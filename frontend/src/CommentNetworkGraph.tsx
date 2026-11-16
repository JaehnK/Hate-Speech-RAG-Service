import cytoscape, { type Core, type EdgeSingular, type ElementDefinition, type NodeSingular, type StylesheetJson } from "cytoscape";
import { Maximize2, Minus, Plus, RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { CommentNetwork, CommentNetworkNode } from "./types";

interface EdgeDetailsData {
  sourceLabel: string;
  targetLabel: string;
  frequency: number;
  hateCount: number;
  hateRatio: number;
  lineWidth: number;
}

const GRAPH_STYLE: StylesheetJson = [
  {
    selector: "node",
    style: {
      width: "data(size)",
      height: "data(size)",
      "background-color": "#17233f",
      "border-color": "#ffffff",
      "border-width": 3,
      "font-family": "Inter, sans-serif",
      "font-size": 10,
      color: "#17233f",
      label: "",
      "text-background-color": "#ffffff",
      "text-background-opacity": 0.9,
      "text-background-padding": "3px",
      "text-margin-y": 8,
      "text-valign": "bottom",
      "text-wrap": "ellipsis",
      "text-max-width": "100px",
    },
  },
  { selector: "node.risk", style: { "background-color": "#c8102e" } },
  { selector: "node.hub", style: { label: "data(label)" } },
  {
    selector: "node:selected",
    style: {
      label: "data(label)",
      "border-color": "#f5b800",
      "border-width": 5,
      "overlay-color": "#f5b800",
      "overlay-opacity": 0.12,
    },
  },
  {
    selector: "edge",
    style: {
      width: "data(lineWidth)",
      "curve-style": "bezier",
      "line-color": "#9aa8bd",
      "target-arrow-color": "#9aa8bd",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.75,
      opacity: 0.62,
    },
  },
  {
    selector: "edge.risk",
    style: {
      "line-color": "#c8102e",
      "target-arrow-color": "#c8102e",
      opacity: 0.85,
    },
  },
  { selector: "edge:selected", style: { width: 4, opacity: 1 } },
];

export function CommentNetworkGraph({ network }: { network: CommentNetwork }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Core | null>(null);
  const [showAllNodes, setShowAllNodes] = useState(false);
  const [selectedNode, setSelectedNode] = useState<CommentNetworkNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<EdgeDetailsData | null>(null);
  const elements = useMemo(() => buildNetworkElements(network, showAllNodes), [network, showAllNodes]);
  const connectedNodeCount = connectedNodeKeys(network).size;

  useEffect(() => {
    if (!containerRef.current || network.nodes.length === 0) return;
    setSelectedNode(null);
    setSelectedEdge(null);
    const graph = cytoscape({
      container: containerRef.current,
      elements,
      style: GRAPH_STYLE,
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 46,
        nodeRepulsion: () => 7000,
        idealEdgeLength: () => 90,
        edgeElasticity: () => 100,
        gravity: 0.35,
        numIter: 700,
      },
      minZoom: 0.18,
      maxZoom: 3.5,
      wheelSensitivity: 0.18,
      boxSelectionEnabled: false,
      autoungrabify: false,
    });
    graphRef.current = graph;
    graph.on("tap", "node", (event) => {
      setSelectedEdge(null);
      setSelectedNode((event.target as NodeSingular).data("networkNode"));
    });
    graph.on("tap", "edge", (event) => {
      setSelectedNode(null);
      setSelectedEdge((event.target as EdgeSingular).data("edgeDetails"));
    });
    graph.on("tap", (event) => { if (event.target === graph) { setSelectedNode(null); setSelectedEdge(null); } });
    const resize = () => graph.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      graph.destroy();
      graphRef.current = null;
    };
  }, [elements, network.nodes.length]);

  if (network.nodes.length === 0) {
    return <div className="network-state"><strong>표시할 관계가 없습니다.</strong><p>수집된 댓글 작성자 데이터가 없습니다.</p></div>;
  }

  const fit = () => graphRef.current?.fit(graphRef.current.elements(), 46);
  const zoom = (factor: number) => {
    const graph = graphRef.current;
    const container = containerRef.current;
    if (!graph || !container) return;
    graph.zoom({
      level: Math.min(graph.maxZoom(), Math.max(graph.minZoom(), graph.zoom() * factor)),
      renderedPosition: { x: container.clientWidth / 2, y: container.clientHeight / 2 },
    });
  };
  const relayout = () => graphRef.current?.layout({ name: "cose", animate: true, animationDuration: 350, fit: true, padding: 46 }).run();
  const metrics = buildNetworkMetrics(network);
  const nodeValues = computeNodeMetrics(network);
  const clearSelection = () => { graphRef.current?.elements().unselect(); setSelectedNode(null); setSelectedEdge(null); };

  return (
    <div className="network-workspace">
      <div className="network-toolbar">
        <div className="network-counts">
          <strong>{formatCount(network.nodes.length)}명</strong><span>작성자</span>
          <strong>{formatCount(metrics.edgeCount)}개</strong><span>답글 관계</span>
        </div>
        {network.edges.length > 0 && connectedNodeCount < network.nodes.length && (
          <div className="network-scope" role="group" aria-label="네트워크 표시 범위">
            <button className={!showAllNodes ? "active" : ""} aria-pressed={!showAllNodes} onClick={() => setShowAllNodes(false)}>연결 중심</button>
            <button className={showAllNodes ? "active" : ""} aria-pressed={showAllNodes} onClick={() => setShowAllNodes(true)}>전체 노드</button>
          </div>
        )}
        <div className="network-legend" aria-label="그래프 범례"><span><i className="normal" />일반</span><span><i className="risk" />혐오표현 포함</span><span><i className="edge" />답글 방향</span></div>
      </div>
      <div className="network-content">
        <NetworkOverview metrics={metrics} />
        <div className="network-stage">
          <div
            ref={containerRef}
            className="network-canvas"
            role="img"
            aria-label={`작성자 노드 ${network.nodes.length}개와 답글 관계 ${metrics.edgeCount}개의 상호작용 네트워크`}
          />
          <div className="network-controls" aria-label="그래프 화면 제어">
            <button aria-label="확대" title="확대" onClick={() => zoom(1.25)}><Plus size={16} /></button>
            <button aria-label="축소" title="축소" onClick={() => zoom(0.8)}><Minus size={16} /></button>
            <button aria-label="화면에 맞춤" title="화면에 맞춤" onClick={fit}><Maximize2 size={16} /></button>
            <button aria-label="배치 다시 계산" title="배치 다시 계산" onClick={relayout}><RefreshCw size={16} /></button>
          </div>
          {selectedNode && <NodeDetails node={selectedNode} values={nodeValues.get(selectedNode.node_key)!} onClose={clearSelection} />}
          {selectedEdge && <EdgeDetails edge={selectedEdge} onClose={clearSelection} />}
        </div>
      </div>
      <p className="network-help">노드를 드래그해 위치를 바꾸고 빈 공간을 드래그해 이동하세요. 노드 또는 연결선을 선택하면 상세 지표가 열립니다.</p>
    </div>
  );
}

function NetworkOverview({ metrics }: { metrics: ReturnType<typeof buildNetworkMetrics> }) {
  const rows: [string, string, string][] = [
    ["전체 작성자", "Nodes", formatCount(metrics.nodeCount)],
    ["답글 관계", "Edges", formatCount(metrics.edgeCount)],
    ["답글 수", "Replies", formatCount(metrics.replyCount)],
    ["답글을 주고받은 작성자", "", formatCount(metrics.connectedNodes)],
    ["답글이 없는 작성자", "Isolates", formatCount(metrics.isolatedNodes)],
    ["혐오표현을 쓴 작성자", "", formatCount(metrics.hateNodes)],
    ["혐오표현이 담긴 답글", "", formatCount(metrics.hateEdges)],
    ["평균 연결 수", "Avg. degree", metrics.averageDegree.toFixed(2)],
    ["평균 답글 수", "Avg. strength", metrics.averageStrength.toFixed(2)],
    ["연결 밀도", "Density", `${metrics.density.toFixed(2)}%`],
  ];
  return <aside className="network-overview"><h3>답글 관계 요약</h3><dl>
    {rows.map(([label, term, value]) => <div key={label}><dt>{label}{term && <span className="sna-term"> ({term})</span>}</dt><dd>{value}</dd></div>)}
  </dl><p>답글 관계는 답글이 오간 작성자 쌍(방향 구분), 답글 수는 중복을 포함한 전체 답글입니다. 연결 밀도는 가능한 모든 쌍 중 실제로 답글이 오간 비율입니다.{metrics.selfReplyCount > 0 && ` 자기 댓글에 단 답글 ${formatCount(metrics.selfReplyCount)}개는 제외했습니다.`}</p></aside>;
}

function NodeDetails({ node, values, onClose }: { node: CommentNetworkNode; values: NodeMetrics; onClose: () => void }) {
  return (
    <aside className="network-details" aria-label="선택한 작성자 상세 정보">
      <button aria-label="상세 정보 닫기" onClick={onClose}><X size={16} /></button>
      <small>선택한 작성자</small>
      <strong>{node.label || "이름 없는 작성자"}</strong>
      <dl>
        <div><dt>댓글</dt><dd>{formatCount(node.comment_count)}</dd></div>
        <div><dt>혐오표현</dt><dd>{formatCount(node.hate_speech_count)}</dd></div>
        <div><dt>비율</dt><dd>{Math.round(node.hate_speech_ratio * 100)}%</dd></div>
        <div><dt>답글 보낸 사람 <span className="sna-term">(In-degree)</span></dt><dd>{formatCount(values.inDegree)}</dd></div>
        <div><dt>답글 받은 사람 <span className="sna-term">(Out-degree)</span></dt><dd>{formatCount(values.outDegree)}</dd></div>
        <div><dt>받은 답글 <span className="sna-term">(In-strength)</span></dt><dd>{formatCount(values.inStrength)}</dd></div>
        <div><dt>단 답글 <span className="sna-term">(Out-strength)</span></dt><dd>{formatCount(values.outStrength)}</dd></div>
      </dl>
    </aside>
  );
}

function EdgeDetails({ edge, onClose }: { edge: EdgeDetailsData; onClose: () => void }) {
  return <aside className="network-details" aria-label="선택한 답글 관계 상세 정보">
    <button aria-label="상세 정보 닫기" onClick={onClose}><X size={16} /></button>
    <small>선택한 답글 관계</small><strong>{edge.sourceLabel} → {edge.targetLabel}</strong>
    <dl>
      <div><dt>답글 수 <span className="sna-term">(Weight)</span></dt><dd>{formatCount(edge.frequency)}</dd></div>
      <div><dt>혐오표현 답글</dt><dd>{formatCount(edge.hateCount)}</dd></div>
      <div><dt>혐오 비율</dt><dd>{Math.round(edge.hateRatio * 100)}%</dd></div>
      <div><dt>선 굵기</dt><dd>{edge.lineWidth.toFixed(1)}</dd></div>
    </dl>
  </aside>;
}

export function buildNetworkElements(network: CommentNetwork, showAllNodes: boolean): ElementDefinition[] {
  const knownNodeKeys = new Set(network.nodes.map((node) => node.node_key));
  const labels = new Map(network.nodes.map((node) => [node.node_key, node.label || "이름 없는 작성자"]));
  const grouped = new Map<string, { source: string; target: string; frequency: number; hateCount: number }>();
  for (const edge of network.edges) {
    if (!knownNodeKeys.has(edge.source_node_key) || !knownNodeKeys.has(edge.target_node_key)) continue;
    const key = `${edge.source_node_key}\u0000${edge.target_node_key}`;
    const value = grouped.get(key) ?? { source: edge.source_node_key, target: edge.target_node_key, frequency: 0, hateCount: 0 };
    value.frequency += Math.max(1, edge.weight);
    value.hateCount += edge.is_hate_speech ? 1 : 0;
    grouped.set(key, value);
  }
  const edges = [...grouped.values()];
  const connected = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const nodes = showAllNodes || edges.length === 0 ? network.nodes : network.nodes.filter((node) => connected.has(node.node_key));
  const nodeValues = computeNodeMetrics(network);
  const degreeOf = (key: string) => nodeValues.get(key)?.degree ?? 0;
  const maxMetric = Math.max(1, ...nodes.map((node) => node.comment_count + degreeOf(node.node_key)));
  return [
    ...nodes.map((node) => {
      const degree = degreeOf(node.node_key);
      const sizeMetric = node.comment_count + degree;
      const size = 22 + (sizeMetric / maxMetric) * 26;
      return {
        group: "nodes" as const,
        data: {
          id: node.node_key,
          label: node.label || "이름 없는 작성자",
          size,
          networkNode: node,
        },
        classes: [node.hate_speech_count > 0 ? "risk" : "", degree >= 2 ? "hub" : ""].filter(Boolean).join(" "),
      };
    }),
    ...edges.map((edge, index) => {
      const lineWidth = Math.min(7, 1.2 + Math.log2(edge.frequency + 1) * 1.5);
      const edgeDetails: EdgeDetailsData = { sourceLabel: labels.get(edge.source)!, targetLabel: labels.get(edge.target)!, frequency: edge.frequency, hateCount: edge.hateCount, hateRatio: edge.hateCount / edge.frequency, lineWidth };
      return {
        group: "edges" as const,
        data: { id: `reply-${index}`, source: edge.source, target: edge.target, lineWidth, edgeDetails },
        classes: edge.hateCount > 0 ? "risk" : "",
      };
    }),
  ];
}

export interface NodeMetrics {
  inDegree: number;
  outDegree: number;
  degree: number;
  inStrength: number;
  outStrength: number;
  strength: number;
}

// Mirrors app/reporting/network_metrics.py. Degree counts distinct partners on the
// simple directed graph; strength counts replies. Self-replies are excluded from both.
export function computeNodeMetrics(network: CommentNetwork): Map<string, NodeMetrics> {
  const values = new Map<string, NodeMetrics>(network.nodes.map((node) => [node.node_key, { inDegree: 0, outDegree: 0, degree: 0, inStrength: 0, outStrength: 0, strength: 0 }]));
  const ensure = (key: string) => {
    if (!values.has(key)) values.set(key, { inDegree: 0, outDegree: 0, degree: 0, inStrength: 0, outStrength: 0, strength: 0 });
    return values.get(key)!;
  };
  const pairs = new Set<string>();
  for (const edge of network.edges) {
    if (edge.source_node_key === edge.target_node_key) continue;
    const source = ensure(edge.source_node_key);
    const target = ensure(edge.target_node_key);
    source.outStrength += 1;
    target.inStrength += 1;
    const pair = `${edge.source_node_key}\u0000${edge.target_node_key}`;
    if (pairs.has(pair)) continue;
    pairs.add(pair);
    source.outDegree += 1;
    target.inDegree += 1;
  }
  for (const value of values.values()) {
    value.degree = value.inDegree + value.outDegree;
    value.strength = value.inStrength + value.outStrength;
  }
  return values;
}

export function buildNetworkMetrics(network: CommentNetwork) {
  const replies = network.edges.filter((edge) => edge.source_node_key !== edge.target_node_key);
  const uniqueEdges = new Set(replies.map((edge) => `${edge.source_node_key}\u0000${edge.target_node_key}`));
  const connected = new Set(replies.flatMap((edge) => [edge.source_node_key, edge.target_node_key]));
  const nodeCount = network.nodes.length;
  return {
    nodeCount,
    edgeCount: uniqueEdges.size,
    replyCount: replies.length,
    selfReplyCount: network.edges.length - replies.length,
    connectedNodes: connected.size,
    isolatedNodes: Math.max(0, nodeCount - connected.size),
    hateNodes: network.nodes.filter((node) => node.hate_speech_count > 0).length,
    hateEdges: network.edges.filter((edge) => edge.is_hate_speech).length,
    averageDegree: nodeCount ? (2 * uniqueEdges.size) / nodeCount : 0,
    averageStrength: nodeCount ? (2 * replies.length) / nodeCount : 0,
    density: nodeCount > 1 ? uniqueEdges.size / (nodeCount * (nodeCount - 1)) * 100 : 0,
  };
}

function connectedNodeKeys(network: CommentNetwork): Set<string> {
  return new Set(network.edges.filter((edge) => edge.source_node_key !== edge.target_node_key).flatMap((edge) => [edge.source_node_key, edge.target_node_key]));
}

function formatCount(value: number): string {
  return value.toLocaleString("ko-KR");
}
