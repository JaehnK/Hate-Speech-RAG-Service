import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildNetworkElements, CommentNetworkGraph } from "./CommentNetworkGraph";
import type { CommentNetwork } from "./types";

const network: CommentNetwork = {
  network_id: "network-1",
  status: "succeeded",
  graph_type: "comment_reply_author_network",
  directed: true,
  summary: { node_count: 3, edge_count: 1 },
  nodes: [
    { node_key: "author-a", node_type: "author", label: "작성자 A", comment_count: 2, hate_speech_count: 1, hate_speech_ratio: 0.5, metrics: { degree: 2, in_degree: 1, out_degree: 1 } },
    { node_key: "author-b", node_type: "author", label: "작성자 B", comment_count: 1, hate_speech_count: 0, hate_speech_ratio: 0, metrics: { degree: 1, in_degree: 1, out_degree: 0 } },
    { node_key: "isolated", node_type: "author", label: "고립 작성자", comment_count: 1, hate_speech_count: 0, hate_speech_ratio: 0, metrics: { degree: 0, in_degree: 0, out_degree: 0 } },
  ],
  edges: [
    { source_node_key: "author-a", target_node_key: "author-b", edge_type: "reply_to", weight: 1, is_hate_speech: true },
  ],
};

describe("comment network graph", () => {
  it("shows connected nodes first and preserves directed risk edges", () => {
    const elements = buildNetworkElements(network, false);
    const nodes = elements.filter((element) => element.group === "nodes");
    const edges = elements.filter((element) => element.group === "edges");

    expect(nodes).toHaveLength(2);
    expect(nodes.find((element) => element.data.id === "author-a")?.classes).toContain("risk");
    expect(edges).toHaveLength(1);
    expect(edges[0].data).toMatchObject({ source: "author-a", target: "author-b" });
    expect(edges[0].classes).toBe("risk");
  });

  it("can include isolated authors", () => {
    const nodes = buildNetworkElements(network, true).filter((element) => element.group === "nodes");
    expect(nodes).toHaveLength(3);
  });

  it("renders an explicit empty state without a browser canvas", () => {
    const html = renderToStaticMarkup(<CommentNetworkGraph network={{ ...network, nodes: [], edges: [] }} />);
    expect(html).toContain("표시할 관계가 없습니다");
  });
});
