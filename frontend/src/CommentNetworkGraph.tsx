import { Button } from "@astryxdesign/core/Button";
import { CheckboxInput } from "@astryxdesign/core/CheckboxInput";
import { Heading } from "@astryxdesign/core/Heading";
import { IconButton } from "@astryxdesign/core/IconButton";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Table } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
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

type GraphPalette = { node: string; hate: string; edge: string; selected: string; label: string; surface: string };

const FALLBACK_PALETTE: GraphPalette = { node: "#5c5c5c", hate: "#c9303a", edge: "#c4c4c4", selected: "#1b1b1b", label: "#1b1b1b", surface: "#ffffff" };

/**
 * Cytoscape draws on canvas and cannot read CSS variables, and a custom property's
 * computed value stays as the raw `light-dark(...)` text. Resolve each token through
 * a probe element so the graph follows the active light/dark scheme.
 */
function readPalette(host: HTMLElement | null): GraphPalette {
  if (!host || typeof getComputedStyle === "undefined") return FALLBACK_PALETTE;
  const probe = document.createElement("span");
  probe.style.display = "none";
  host.appendChild(probe);
  const resolve = (token: string, fallback: string) => {
    probe.style.color = "";
    probe.style.color = `var(${token}, ${fallback})`;
    return getComputedStyle(probe).color || fallback;
  };
  const palette = {
    node: resolve("--hs-graph-node", FALLBACK_PALETTE.node),
    hate: resolve("--hs-data-hate", FALLBACK_PALETTE.hate),
    edge: resolve("--hs-graph-edge", FALLBACK_PALETTE.edge),
    selected: resolve("--color-text-primary", FALLBACK_PALETTE.selected),
    label: resolve("--color-text-primary", FALLBACK_PALETTE.label),
    surface: resolve("--color-background-muted", FALLBACK_PALETTE.surface),
  };
  probe.remove();
  return palette;
}

/** Re-renders when the OS switches between light and dark. */
function useColorScheme(): "light" | "dark" {
  const darkQuery = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null);
  const [scheme, setScheme] = useState<"light" | "dark">(() => (darkQuery()?.matches ? "dark" : "light"));
  useEffect(() => {
    const query = darkQuery();
    if (!query) return;
    const onChange = (event: MediaQueryListEvent) => setScheme(event.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return scheme;
}

function graphStyle(highlightHate: boolean, palette: GraphPalette): StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        width: "data(size)",
        height: "data(size)",
        "background-color": palette.node,
        "border-color": palette.surface,
        "border-width": 2,
        "font-family": "Figtree, 'IBM Plex Sans KR', sans-serif",
        "font-size": 11,
        color: palette.label,
        label: "",
        "text-background-color": palette.surface,
        "text-background-opacity": 0.9,
        "text-background-padding": "3px",
        "text-margin-y": 6,
        "text-valign": "bottom",
        "text-wrap": "ellipsis",
        "text-max-width": "110px",
      },
    },
    { selector: "node.risk", style: { "background-color": palette.hate } },
    { selector: "node.hub", style: { label: "data(label)" } },
    { selector: "node:selected", style: { label: "data(label)", "border-color": palette.selected, "border-width": 4 } },
    {
      selector: "edge",
      style: {
        width: "data(lineWidth)",
        "curve-style": "bezier",
        "line-color": palette.edge,
        "target-arrow-color": palette.edge,
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.75,
        opacity: 0.8,
      },
    },
    ...(highlightHate ? [{ selector: "edge.risk", style: { "line-color": palette.hate, "target-arrow-color": palette.hate, opacity: 0.9 } }] : []),
    { selector: "edge:selected", style: { "line-color": palette.selected, "target-arrow-color": palette.selected, opacity: 1 } },
  ];
}

interface AuthorRow extends Record<string, unknown> {
  key: string;
  label: string;
  comments: number;
  hate: number;
  degree: number;
  inStrength: number;
  outStrength: number;
}

export function CommentNetworkGraph({ network, onShowAuthor }: { network: CommentNetwork; onShowAuthor?: (authorKey: string, label: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Core | null>(null);
  const [scope, setScope] = useState("connected");
  const [highlightHate, setHighlightHate] = useState(true);
  const [selectedNode, setSelectedNode] = useState<CommentNetworkNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<EdgeDetailsData | null>(null);
  const showAllNodes = scope === "all";
  const elements = useMemo(() => buildNetworkElements(network, showAllNodes), [network, showAllNodes]);
  const metrics = useMemo(() => buildNetworkMetrics(network), [network]);
  const nodeValues = useMemo(() => computeNodeMetrics(network), [network]);
  const scheme = useColorScheme();
  const hasIsolates = metrics.edgeCount > 0 && metrics.connectedNodes < network.nodes.length;

  useEffect(() => {
    if (!containerRef.current || network.nodes.length === 0) return;
    setSelectedNode(null);
    setSelectedEdge(null);
    const graph = cytoscape({
      container: containerRef.current,
      elements,
      style: graphStyle(true, readPalette(containerRef.current)),
      layout: { name: "cose", animate: false, fit: true, padding: 40, nodeRepulsion: () => 7000, idealEdgeLength: () => 90, edgeElasticity: () => 100, gravity: 0.35, numIter: 700 },
      minZoom: 0.18,
      maxZoom: 3.5,
      wheelSensitivity: 0.18,
      boxSelectionEnabled: false,
    });
    graphRef.current = graph;
    graph.on("tap", "node", (event) => { setSelectedEdge(null); setSelectedNode((event.target as NodeSingular).data("networkNode")); });
    graph.on("tap", "edge", (event) => { setSelectedNode(null); setSelectedEdge((event.target as EdgeSingular).data("edgeDetails")); });
    graph.on("tap", (event) => { if (event.target === graph) { setSelectedNode(null); setSelectedEdge(null); } });
    const resize = () => graph.resize();
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); graph.destroy(); graphRef.current = null; };
  }, [elements, network.nodes.length]);

  useEffect(() => { graphRef.current?.style(graphStyle(highlightHate, readPalette(containerRef.current))); }, [highlightHate, scheme, elements]);

  if (network.nodes.length === 0) {
    return <Text type="supporting" as="p">모은 댓글 작성자 데이터가 없어 답글 관계를 그릴 수 없습니다.</Text>;
  }

  const fit = () => graphRef.current?.fit(graphRef.current.elements(), 40);
  const zoom = (factor: number) => {
    const graph = graphRef.current;
    const container = containerRef.current;
    if (!graph || !container) return;
    graph.zoom({ level: Math.min(graph.maxZoom(), Math.max(graph.minZoom(), graph.zoom() * factor)), renderedPosition: { x: container.clientWidth / 2, y: container.clientHeight / 2 } });
  };
  const relayout = () => graphRef.current?.layout({ name: "cose", animate: true, animationDuration: 350, fit: true, padding: 40 }).run();
  const clearSelection = () => { graphRef.current?.elements().unselect(); setSelectedNode(null); setSelectedEdge(null); };

  const authors: AuthorRow[] = network.nodes
    .map((node) => {
      const values = nodeValues.get(node.node_key);
      return { key: node.node_key, label: node.label || "이름 없는 작성자", comments: node.comment_count, hate: node.hate_speech_count, degree: values?.degree ?? 0, inStrength: values?.inStrength ?? 0, outStrength: values?.outStrength ?? 0 };
    })
    .filter((row) => row.degree > 0)
    .sort((a, b) => b.degree - a.degree || b.inStrength + b.outStrength - (a.inStrength + a.outStrength))
    .slice(0, 10);

  return (
    <div className="hs-stack">
      <div className="hs-toolbar">
        {hasIsolates && (
          <SegmentedControl label="표시할 작성자" value={scope} onChange={setScope} size="lg">
            <SegmentedControlItem value="connected" label="답글이 오간 작성자만" />
            <SegmentedControlItem value="all" label="전체 작성자" />
          </SegmentedControl>
        )}
        <CheckboxInput label="혐오표현 답글 강조" value={highlightHate} onChange={setHighlightHate} />
        <div className="hs-legend" aria-label="그래프 범례">
          <span><i className="hs-dot" />일반 작성자</span>
          <span><i className="hs-dot is-hate" />혐오표현을 쓴 작성자</span>
          <span>화살표는 답글 방향, 굵기는 답글 수 <span className="hs-term">(Edge weight)</span></span>
        </div>
      </div>

      <div className="hs-network">
        <div className="hs-network-stage">
          <div ref={containerRef} className="hs-network-canvas" role="img" aria-label={`작성자 ${network.nodes.length}명, 답글 관계 ${metrics.edgeCount}개의 답글 네트워크. 같은 내용을 아래 표로 볼 수 있습니다.`} />
          <div className="hs-network-controls" aria-label="그래프 보기 조절">
            <IconButton size="sm" variant="ghost" label="확대" tooltip="확대" icon={<Plus size={16} />} onClick={() => zoom(1.25)} />
            <IconButton size="sm" variant="ghost" label="축소" tooltip="축소" icon={<Minus size={16} />} onClick={() => zoom(0.8)} />
            <IconButton size="sm" variant="ghost" label="화면에 맞춤" tooltip="화면에 맞춤" icon={<Maximize2 size={16} />} onClick={fit} />
            <IconButton size="sm" variant="ghost" label="배치 다시 계산" tooltip="배치 다시 계산" icon={<RefreshCw size={16} />} onClick={relayout} />
          </div>
          <span className="hs-network-hint">드래그로 이동하고, 작성자나 선을 누르면 자세히 봅니다</span>
        </div>

        <aside className="hs-network-aside">
          {selectedNode && <NodeDetails node={selectedNode} values={nodeValues.get(selectedNode.node_key)!} onClose={clearSelection} onShowAuthor={onShowAuthor} />}
          {selectedEdge && <EdgeDetails edge={selectedEdge} onClose={clearSelection} />}
          <NetworkOverview metrics={metrics} />
        </aside>
      </div>

      {authors.length > 0 && (
        <div className="hs-stack">
          <div className="hs-section-header">
            <Heading level={3}>대화가 몰린 작성자</Heading>
            <Text type="supporting">그래프와 같은 내용을 연결 수(Degree)가 많은 순으로 정리한 표</Text>
          </div>
          <div className="hs-table-scroll">
            <Table<AuthorRow>
              data={authors}
              idKey="key"
              density="compact"
              columns={[
                { key: "label", header: "작성자" },
                { key: "comments", header: "댓글", align: "end" },
                { key: "hate", header: "혐오표현", align: "end" },
                { key: "degree", header: <>연결 수 <span className="hs-term">(Degree)</span></>, align: "end" },
                { key: "inStrength", header: <>받은 답글 <span className="hs-term">(In-strength)</span></>, align: "end" },
                { key: "outStrength", header: <>단 답글 <span className="hs-term">(Out-strength)</span></>, align: "end" },
                ...(onShowAuthor ? [{
                  key: "action",
                  header: <span className="hs-visually-hidden">동작</span>,
                  align: "end" as const,
                  renderCell: (row: AuthorRow) => row.key.startsWith("anonymous:") ? null : <Button size="sm" variant="ghost" label="댓글 보기" onClick={() => onShowAuthor(row.key, row.label)} />,
                }] : []),
              ]}
            />
          </div>
        </div>
      )}
      <p className="hs-note">답글 관계는 대화가 어디에 몰렸는지만 보여줍니다. 동조나 설득, 혐오가 퍼졌다는 증거는 아니며, 작성자 수치는 댓글 판정을 합친 값일 뿐 그 사람의 성향을 판단하지 않습니다.</p>
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
  return (
    <div className="hs-stack">
      <Heading level={3}>답글 관계 요약</Heading>
      <dl className="hs-kv">
        {rows.map(([label, term, value]) => <div key={label}><dt>{label}{term && <span className="hs-term"> ({term})</span>}</dt><dd>{value}</dd></div>)}
      </dl>
      <p className="hs-note">답글 관계는 답글이 오간 작성자 쌍(방향 구분), 답글 수는 중복을 포함한 전체 답글입니다. 연결 밀도는 가능한 모든 쌍 중 실제로 답글이 오간 비율입니다.{metrics.selfReplyCount > 0 && ` 자기 댓글에 단 답글 ${formatCount(metrics.selfReplyCount)}개는 제외했습니다.`}</p>
    </div>
  );
}

function NodeDetails({ node, values, onClose, onShowAuthor }: { node: CommentNetworkNode; values: NodeMetrics; onClose: () => void; onShowAuthor?: (authorKey: string, label: string) => void }) {
  const label = node.label || "이름 없는 작성자";
  return (
    <div className="hs-stack hs-network-detail" aria-label="선택한 작성자">
      <div className="hs-section-header">
        <Text type="supporting" weight="medium">선택한 작성자</Text>
        <IconButton size="sm" variant="ghost" label="선택 해제" icon={<X size={16} />} onClick={onClose} />
      </div>
      <Heading level={3} maxLines={1} wordBreak="break-word">{label}</Heading>
      <dl className="hs-kv">
        <div><dt>댓글</dt><dd>{formatCount(node.comment_count)}</dd></div>
        <div><dt>혐오표현</dt><dd>{formatCount(node.hate_speech_count)}</dd></div>
        <div><dt>혐오표현 비율</dt><dd>{Math.round(node.hate_speech_ratio * 100)}%</dd></div>
        <div><dt>답글 보낸 사람 <span className="hs-term">(In-degree)</span></dt><dd>{formatCount(values.inDegree)}명</dd></div>
        <div><dt>답글 받은 사람 <span className="hs-term">(Out-degree)</span></dt><dd>{formatCount(values.outDegree)}명</dd></div>
        <div><dt>받은 답글 <span className="hs-term">(In-strength)</span></dt><dd>{formatCount(values.inStrength)}</dd></div>
        <div><dt>단 답글 <span className="hs-term">(Out-strength)</span></dt><dd>{formatCount(values.outStrength)}</dd></div>
      </dl>
      {onShowAuthor && !node.node_key.startsWith("anonymous:") && node.hate_speech_count > 0 && (
        <Button size="sm" label="이 작성자의 혐오표현 댓글 보기" onClick={() => onShowAuthor(node.node_key, label)} />
      )}
    </div>
  );
}

function EdgeDetails({ edge, onClose }: { edge: EdgeDetailsData; onClose: () => void }) {
  return (
    <div className="hs-stack hs-network-detail" aria-label="선택한 답글 관계">
      <div className="hs-section-header">
        <Text type="supporting" weight="medium">선택한 답글 관계</Text>
        <IconButton size="sm" variant="ghost" label="선택 해제" icon={<X size={16} />} onClick={onClose} />
      </div>
      <Heading level={3} maxLines={2} wordBreak="break-word">{edge.sourceLabel} → {edge.targetLabel}</Heading>
      <dl className="hs-kv">
        <div><dt>답글 수 <span className="hs-term">(Weight)</span></dt><dd>{formatCount(edge.frequency)}</dd></div>
        <div><dt>혐오표현 답글</dt><dd>{formatCount(edge.hateCount)}</dd></div>
        <div><dt>혐오표현 비율</dt><dd>{Math.round(edge.hateRatio * 100)}%</dd></div>
      </dl>
    </div>
  );
}

export function buildNetworkElements(network: CommentNetwork, showAllNodes: boolean): ElementDefinition[] {
  const knownNodeKeys = new Set(network.nodes.map((node) => node.node_key));
  const labels = new Map(network.nodes.map((node) => [node.node_key, node.label || "이름 없는 작성자"]));
  const grouped = new Map<string, { source: string; target: string; frequency: number; hateCount: number }>();
  for (const edge of network.edges) {
    if (!knownNodeKeys.has(edge.source_node_key) || !knownNodeKeys.has(edge.target_node_key)) continue;
    if (edge.source_node_key === edge.target_node_key) continue;
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

function formatCount(value: number): string {
  return value.toLocaleString("ko-KR");
}
