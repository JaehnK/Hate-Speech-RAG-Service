"""Simulate a Jev -> three-vector RAG cascade from stored results, without new LLM calls.

Items Jev scores below the threshold are predicted non-hate and skip the LLM; every
other item keeps its stored three-vector RAG prediction. The threshold is chosen on
tuning splits (`--tuning`) by a rule fixed before looking at test results: the largest
threshold on a 0.01 grid whose gold-hate leakage (hate items filtered / hate items) is
at most `--max-leakage`. Leakage bounds the cascade's recall loss from above, because
the cascade only loses the filtered hate items that RAG would have caught.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from experiments.evaluate_results import BOOTSTRAP_SEED, _categories, _metrics_for_multiset, evaluate
from experiments.io import read_jsonl

REFERENCE_VARIANT = "three_vector_rag"
DIFF_KEYS = ("binary_accuracy", "binary_precision", "binary_recall", "binary_f1", "category_macro_f1")


def choose_threshold(scores: dict[str, float], gold: dict[str, dict], max_leakage: float) -> dict[str, float]:
    hate_scores = [scores[item_id] for item_id, row in gold.items() if row["is_hate_speech"] and item_id in scores]
    best = {"threshold": 0.0, "leakage": 0.0, "filtered_rate": 0.0}
    for step in range(1, 100):
        threshold = round(step / 100, 2)
        leakage = sum(score < threshold for score in hate_scores) / len(hate_scores)
        if leakage > max_leakage:
            break
        filtered = sum(scores[item_id] < threshold for item_id in gold if item_id in scores)
        best = {"threshold": threshold, "leakage": leakage, "filtered_rate": filtered / len(gold)}
    return best


def cascade_rows(rows: list[dict[str, Any]], scores: dict[str, float], threshold: float) -> list[dict[str, Any]]:
    variant = f"jev_cascade_{threshold:.2f}"
    cascaded = []
    for row in rows:
        if row["variant"] != REFERENCE_VARIANT:
            continue
        score = scores.get(str(row["item_id"]))
        if score is not None and score < threshold:
            row = {
                **row,
                "status": "succeeded",
                "payload": {"is_hate_speech": False, "categories": ["unclassified"]},
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "jev_filtered": True,
            }
        cascaded.append({**row, "variant": variant})
    return cascaded


def paired_differences(
    reference_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    gold: dict[str, dict[str, Any]],
    samples: int = 1000,
) -> dict[str, dict[str, float]]:
    label_space = sorted({c for row in gold.values() for c in row.get("categories", [])} - {"unclassified"})

    def primary(rows):
        return {
            str(row["item_id"]): (
                bool(row["payload"]["is_hate_speech"]),
                _categories(row["payload"].get("categories", []), label_space),
            )
            for row in rows
            if row.get("status") == "succeeded" and str(row["item_id"]) in gold
        }

    reference, candidate = primary(reference_rows), primary(candidate_rows)
    item_ids = sorted(set(reference) & set(candidate))

    def diff(ids):
        a = _metrics_for_multiset(ids, candidate, gold, label_space)
        b = _metrics_for_multiset(ids, reference, gold, label_space)
        return {key: a[key] - b[key] for key in DIFF_KEYS}

    point = diff(item_ids)
    rng = random.Random(BOOTSTRAP_SEED)
    draws = [diff([rng.choice(item_ids) for _ in item_ids]) for _ in range(samples)]
    result = {}
    for key in DIFF_KEYS:
        values = sorted(draw[key] for draw in draws)
        result[key] = {
            "diff": point[key],
            "ci95_low": values[int(0.025 * samples)],
            "ci95_high": values[min(int(0.975 * samples), samples - 1)],
        }
    return result


def _load_scores(paths: list[str]) -> dict[str, float]:
    return {
        row["item_id"]: float(row["p_hate"])
        for path in paths
        for row in read_jsonl(path)
        if row.get("status") == "succeeded"
    }


def _load_gold(paths: list[str]) -> dict[str, dict[str, Any]]:
    return {str(row["item_id"]): row for path in paths for row in read_jsonl(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tuning", nargs=2, action="append", metavar=("JEV", "GOLD"), required=True)
    parser.add_argument("--test", nargs=3, action="append", metavar=("JEV", "GOLD", "RESULTS"), required=True)
    parser.add_argument("--max-leakage", type=float, default=0.02)
    parser.add_argument("--threshold", type=float, default=None, help="Override the tuned threshold.")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--json-output-path")
    args = parser.parse_args()

    tuning_gold = _load_gold([gold for _, gold in args.tuning])
    tuned = choose_threshold(_load_scores([jev for jev, _ in args.tuning]), tuning_gold, args.max_leakage)
    threshold = args.threshold if args.threshold is not None else tuned["threshold"]

    scores = _load_scores([jev for jev, _, _ in args.test])
    gold = _load_gold([g for _, g, _ in args.test])
    reference = [row for _, _, path in args.test for row in read_jsonl(path) if row["variant"] == REFERENCE_VARIANT]
    candidate = cascade_rows(reference, scores, threshold)

    summaries = evaluate(reference + candidate, list(gold.values()), REFERENCE_VARIANT, args.bootstrap_samples)
    filtered = [row for row in candidate if row.get("jev_filtered")]
    hate_filtered = sum(gold[str(row["item_id"])]["is_hate_speech"] for row in filtered)
    hate_total = sum(row["is_hate_speech"] for row in gold.values())
    report = {
        "tuning": {**tuned, "max_leakage": args.max_leakage, "items": len(tuning_gold)},
        "threshold": threshold,
        "test_items": len(gold),
        "jev_filtered": len(filtered),
        "jev_filtered_rate": len(filtered) / len(gold),
        "test_leakage": hate_filtered / hate_total,
        "rag_true_positives_lost": sum(
            gold[str(row["item_id"])]["is_hate_speech"] and ref["payload"]["is_hate_speech"]
            for row in filtered
            for ref in [next(r for r in reference if r["item_id"] == row["item_id"])]
        ),
        "rag_false_positives_removed": sum(
            not gold[str(row["item_id"])]["is_hate_speech"] and ref["payload"]["is_hate_speech"]
            for row in filtered
            for ref in [next(r for r in reference if r["item_id"] == row["item_id"])]
        ),
        "differences_vs_reference": paired_differences(reference, candidate, gold, args.bootstrap_samples),
        "summaries": summaries,
    }
    if args.json_output_path:
        Path(args.json_output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {k: v for k, v in report.items() if k != "summaries"}
    brief["metrics"] = {
        s["variant"]: {k: round(s[k], 4) for k in DIFF_KEYS} | {"mcnemar": s.get("mcnemar_vs_reference")}
        for s in summaries
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
