"""Social network metrics for the author reply graph.

Each reply comment is one directed edge (replier -> parent author), so the raw
edge list is a multigraph. The metrics below separate the two views SNA users
expect, and both exclude self-replies (an author replying to their own comment):

* degree family — the simple directed graph of unique (source, target) pairs.
  in_degree / out_degree count distinct partners; degree = in + out.
* strength family — reply counts (weighted degree). in/out_strength count replies.

Density uses the same simple directed graph as degree, so
average_degree == 2 * (n - 1) * density holds.

The frontend mirrors these formulas in buildNetworkMetrics/computeNodeMetrics
(frontend/src/CommentNetworkGraph.tsx); keep them in sync.
"""

from __future__ import annotations

from collections.abc import Iterable

NODE_METRIC_KEYS = ("in_degree", "out_degree", "degree", "in_strength", "out_strength", "strength", "self_replies")


def node_metrics(node_keys: Iterable[str], edges: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    metrics = {key: dict.fromkeys(NODE_METRIC_KEYS, 0) for key in node_keys}
    pairs: set[tuple[str, str]] = set()
    for source, target in edges:
        for key in (source, target):
            metrics.setdefault(key, dict.fromkeys(NODE_METRIC_KEYS, 0))
        if source == target:
            metrics[source]["self_replies"] += 1
            continue
        metrics[source]["out_strength"] += 1
        metrics[target]["in_strength"] += 1
        pairs.add((source, target))
    for source, target in pairs:
        metrics[source]["out_degree"] += 1
        metrics[target]["in_degree"] += 1
    for values in metrics.values():
        values["degree"] = values["in_degree"] + values["out_degree"]
        values["strength"] = values["in_strength"] + values["out_strength"]
    return metrics


def network_overview(node_keys: Iterable[str], edges: Iterable[tuple[str, str, bool]]) -> dict[str, float | int]:
    keys = list(node_keys)
    edge_list = list(edges)
    replies = [(source, target) for source, target, _hate in edge_list if source != target]
    pairs = set(replies)
    connected = {key for pair in pairs for key in pair}
    n = len(keys)
    return {
        "node_count": n,
        "reply_count": len(replies),
        "edge_count": len(pairs),
        "self_reply_count": len(edge_list) - len(replies),
        "connected_nodes": len(connected),
        "isolated_nodes": max(0, n - len(connected)),
        "hate_edges": sum(1 for _source, _target, hate in edge_list if hate),
        "average_degree": 2 * len(pairs) / n if n else 0.0,
        "average_strength": 2 * len(replies) / n if n else 0.0,
        "density": len(pairs) / (n * (n - 1)) * 100 if n > 1 else 0.0,
    }

