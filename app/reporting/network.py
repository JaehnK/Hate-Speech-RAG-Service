from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, CommentAnalysisResult, CommentNetwork, CommentNetworkEdge, CommentNetworkNode, CommentSnapshot


class CommentNetworkBuilder:
    def build(self, session: Session, run: AnalysisRun) -> CommentNetwork:
        rows = session.execute(
            select(CommentSnapshot, CommentAnalysisResult)
            .outerjoin(
                CommentAnalysisResult,
                (CommentAnalysisResult.comment_snapshot_id == CommentSnapshot.id)
                & (CommentAnalysisResult.analysis_run_id == run.id),
            )
            .where(CommentSnapshot.job_id == run.job_id)
        ).all()
        comments = {comment.youtube_comment_id: (comment, result) for comment, result in rows}
        node_stats = defaultdict(lambda: {"comment_count": 0, "hate_count": 0, "in": 0, "out": 0, "label": None, "channel": None})
        edge_values = []

        for comment, result in rows:
            key = _node_key(comment)
            stats = node_stats[key]
            stats["comment_count"] += 1
            stats["hate_count"] += bool(result and result.is_hate_speech)
            stats["label"] = stats["label"] or comment.author_display_name
            stats["channel"] = stats["channel"] or comment.author_channel_id
            if not comment.parent_youtube_comment_id or comment.parent_youtube_comment_id not in comments:
                continue
            parent, _parent_result = comments[comment.parent_youtube_comment_id]
            target = _node_key(parent)
            node_stats[key]["out"] += 1
            node_stats[target]["in"] += 1
            edge_values.append((comment, key, target, bool(result and result.is_hate_speech)))

        network = CommentNetwork(
            analysis_run_id=run.id,
            status="succeeded",
            summary={"node_count": len(node_stats), "edge_count": len(edge_values), "self_edge_count": sum(s == t for _c, s, t, _h in edge_values)},
        )
        session.add(network)
        session.flush()
        for key, stats in node_stats.items():
            count = int(stats["comment_count"])
            hate_count = int(stats["hate_count"])
            session.add(
                CommentNetworkNode(
                    network_id=network.id,
                    node_key=key,
                    label=stats["label"],
                    author_channel_id=stats["channel"],
                    comment_count=count,
                    hate_speech_count=hate_count,
                    hate_speech_ratio=Decimal(hate_count) / Decimal(count) if count else Decimal(0),
                    metrics={"in_degree": stats["in"], "out_degree": stats["out"], "degree": stats["in"] + stats["out"]},
                    attributes={},
                )
            )
        for comment, source, target, is_hate in edge_values:
            parent = comments[comment.parent_youtube_comment_id][0]
            session.add(
                CommentNetworkEdge(
                    network_id=network.id,
                    source_node_key=source,
                    target_node_key=target,
                    comment_snapshot_id=comment.id,
                    parent_comment_snapshot_id=parent.id,
                    is_hate_speech=is_hate,
                    attributes={},
                )
            )
        session.flush()
        return network


def _node_key(comment: CommentSnapshot) -> str:
    return comment.author_channel_id or f"anonymous:{comment.id}"
