from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from experiments.io import read_jsonl


def evaluate(rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gold = {str(row["item_id"]): row for row in gold_rows}
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["variant"])].append(row)

    summaries = []
    for variant, items in sorted(grouped.items()):
        matched = [(item, gold.get(str(item["item_id"]))) for item in items]
        matched = [(item, label) for item, label in matched if label is not None and item.get("status") == "succeeded"]
        binary_correct = 0
        tp = fp = fn = 0
        predictions: dict[str, list[tuple[bool, tuple[str, ...]]]] = defaultdict(list)
        for item, label in matched:
            payload = item["payload"]
            predicted_hate = bool(payload["is_hate_speech"])
            expected_hate = bool(label["is_hate_speech"])
            binary_correct += predicted_hate == expected_hate
            predicted_categories = set(payload.get("categories", [])) - {"unclassified"}
            expected_categories = set(label.get("categories", [])) - {"unclassified"}
            tp += len(predicted_categories & expected_categories)
            fp += len(predicted_categories - expected_categories)
            fn += len(expected_categories - predicted_categories)
            predictions[str(item["item_id"])].append((predicted_hate, tuple(sorted(predicted_categories))))
        precision = _rate(tp, tp + fp)
        recall = _rate(tp, tp + fn)
        repeated = [values for values in predictions.values() if len(values) > 1]
        stability = None if not repeated else _rate(sum(len(set(values)) == 1 for values in repeated), len(repeated))
        summaries.append(
            {
                "variant": variant,
                "gold_total": len(gold),
                "evaluated_predictions": len(matched),
                "evaluated_items": len(predictions),
                "coverage": _rate(len(predictions), len(gold)),
                "binary_accuracy": _rate(binary_correct, len(matched)),
                "category_micro_precision": precision,
                "category_micro_recall": recall,
                "category_micro_f1": _rate(2 * precision * recall, precision + recall),
                "repeat_stability": stability,
                "repeat_item_count": len(repeated),
            }
        )
    return summaries


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG experiment results against gold labels.")
    parser.add_argument("--results-path", required=True)
    parser.add_argument("--gold-path", required=True)
    args = parser.parse_args()
    for summary in evaluate(read_jsonl(Path(args.results_path)), read_jsonl(Path(args.gold_path))):
        stability = summary["repeat_stability"]
        stability_text = "n/a" if stability is None else f"{stability:.3f}"
        print(
            "\t".join(
                [
                    summary["variant"],
                    f"coverage={summary['coverage']:.3f}",
                    f"binary_accuracy={summary['binary_accuracy']:.3f}",
                    f"category_micro_f1={summary['category_micro_f1']:.3f}",
                    f"repeat_stability={stability_text}",
                ]
            )
        )


if __name__ == "__main__":
    main()
