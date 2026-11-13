"""Score classifier results against the YouTube gold labels (experiments/gold_labels/youtube_*).

The gold separates two questions the report needs:
  - is_hate_speech: the service's broad threshold (group hate or an insult aimed at someone);
  - target_scope:   "group" (protected attribute or political camp/institution),
                    "individual" (a person, a commenter, the people in the video) or "none".

Results written before prompt v0.7 have no target_scope; it is derived from the categories
(any target category other than profanity/no_target counts as group).

    uv run python -m experiments.evaluate_youtube --results R.jsonl --gold experiments/gold_labels/youtube_eval300.labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from app.analysis.taxonomy import V07_CATEGORY_MAP
from experiments.io import read_jsonl

INSULT_ONLY = {"profanity", "no_target", "unclassified", "other"}
# Scored when the gold uses taxonomy v0.7.0 codes; older predictions are mapped onto them.
POLITICAL_V07 = ("political_actor", "political_camp")


def v07_categories(categories) -> set[str]:
    return {V07_CATEGORY_MAP.get(c, c) for c in categories or ()}


def predicted_scope(payload: dict) -> str:
    if not payload.get("is_hate_speech"):
        return "none"
    scope = payload.get("target_scope")
    if scope in {"group", "individual"}:
        return scope
    categories = set(payload.get("categories") or [])
    return "group" if categories - INSULT_ONLY else "individual"


def prf(pairs: list[tuple[bool, bool]]) -> dict[str, float]:
    tp = sum(g and p for g, p in pairs)
    fp = sum(p and not g for g, p in pairs)
    fn = sum(g and not p for g, p in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def bootstrap_f1(pairs: list[tuple[bool, bool]], rounds: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    scores = sorted(prf([rng.choice(pairs) for _ in pairs])["f1"] for _ in range(rounds))
    return scores[int(0.025 * rounds)], scores[int(0.975 * rounds) - 1]


def evaluate(results: list[dict], gold: list[dict]) -> dict:
    gold_by_id = {row["item_id"]: row for row in gold}
    by_item: dict[str, list[dict]] = defaultdict(list)
    failed = 0
    for row in results:
        if row["item_id"] not in gold_by_id:
            continue
        if row.get("status") != "succeeded" or not row.get("payload"):
            failed += 1
            continue
        by_item[row["item_id"]].append(row)
    for rows in by_item.values():
        rows.sort(key=lambda row: row.get("repeat_index", 0))

    first = {item_id: rows[0]["payload"] for item_id, rows in by_item.items()}
    scored = [item_id for item_id in gold_by_id if item_id in first]
    attack = [(gold_by_id[i]["is_hate_speech"], bool(first[i].get("is_hate_speech"))) for i in scored]
    group = [(gold_by_id[i]["target_scope"] == "group", predicted_scope(first[i]) == "group") for i in scored]
    scope_hits = sum(gold_by_id[i]["target_scope"] == predicted_scope(first[i]) for i in scored)

    report: dict = {
        "items": len(scored),
        "missing": len(gold_by_id) - len(scored),
        "failed_rows": failed,
        "attack": {**prf(attack), "f1_ci": bootstrap_f1(attack), "accuracy": sum(g == p for g, p in attack) / len(attack)},
        "group_hate": {**prf(group), "f1_ci": bootstrap_f1(group)},
        "scope_accuracy": scope_hits / len(scored),
        "predicted_scope": dict(Counter(predicted_scope(first[i]) for i in scored)),
        "gold_scope": dict(Counter(gold_by_id[i]["target_scope"] for i in scored)),
    }

    if any(set(POLITICAL_V07) & set(gold_by_id[i].get("categories") or ()) for i in scored):
        report["political_categories"] = {
            code: prf([(code in gold_by_id[i]["categories"], code in v07_categories(first[i].get("categories"))) for i in scored])
            for code in POLITICAL_V07
        }

    repeated = {i: rows for i, rows in by_item.items() if len(rows) > 1}
    if repeated:
        report["repeat"] = {
            "items": len(repeated),
            "attack_stable": sum(len({bool(r["payload"].get("is_hate_speech")) for r in rows}) == 1 for rows in repeated.values()) / len(repeated),
            "scope_stable": sum(len({predicted_scope(r["payload"]) for r in rows}) == 1 for rows in repeated.values()) / len(repeated),
        }

    groups: dict[str, list[str]] = defaultdict(list)
    for item_id in scored:
        if gold_by_id[item_id].get("group"):
            groups[gold_by_id[item_id]["group"]].append(item_id)
    if groups:
        per_group = {}
        agree_total = 0
        for name, ids in sorted(groups.items()):
            predictions = [predicted_scope(r["payload"]) for i in ids for r in by_item[i]]
            majority = Counter(predictions).most_common(1)[0][1]
            agree_total += majority
            per_group[name] = {
                "gold": gold_by_id[ids[0]]["target_scope"],
                "predicted": dict(Counter(predictions)),
                "agreement": round(majority / len(predictions), 3),
            }
        total = sum(len(ids) * len(by_item[ids[0]]) for ids in groups.values())
        report["consistency"] = {"within_group_agreement": agree_total / total, "groups": per_group}
    return report


def _rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(read_jsonl(args.results), read_jsonl(args.gold))
    text = json.dumps(_rounded(report), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
