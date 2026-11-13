from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any

from app.analysis.taxonomy import MERGED_CATEGORIES, POLITICAL_CATEGORIES
from experiments.io import read_jsonl

# Benchmarks such as K-HATERS or BEEP only label gender/age/identity/profanity/other,
# plus a coarse "political" target in K-HATERS. Political predictions are folded into
# "political" when the gold has it; finer categories the gold lacks fold into "other",
# so the model is not penalised for being more specific than the gold label space.
# political_actor / political_camp are the taxonomy v0.7.0 political codes (prompt v0.8.0).
POLITICAL_CODES = frozenset({*POLITICAL_CATEGORIES, "political_actor", "political_camp"})
FOLDABLE_INTO_OTHER = frozenset({*POLITICAL_CODES, "no_target"})
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 20261108


def evaluate(
    rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    reference_variant: str = "three_vector_rag",
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    merge_categories: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if merge_categories:
        # Score under a merged category scheme (e.g. taxonomy v0.5.0 folds `other` into
        # `profanity`): rewrite gold and predictions the same way before scoring.
        gold_rows = [{**row, "categories": _merge(row.get("categories", []), merge_categories)} for row in gold_rows]
        rows = [
            {**row, "payload": {**row["payload"], "categories": _merge(row["payload"].get("categories", []), merge_categories)}}
            if row.get("status") == "succeeded"
            else row
            for row in rows
        ]
    gold = {str(row["item_id"]): row for row in gold_rows}
    label_space = sorted({c for row in gold_rows for c in row.get("categories", [])} - {"unclassified"})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["variant"])].append(row)

    primaries: dict[str, dict[str, tuple[bool, frozenset[str]]]] = {}
    summaries = []
    for variant, items in sorted(grouped.items()):
        attempted = {str(item["item_id"]) for item in items if str(item["item_id"]) in gold}
        succeeded = [item for item in items if str(item["item_id"]) in gold and item.get("status") == "succeeded"]
        predictions: dict[str, list[tuple[int, bool, frozenset[str]]]] = defaultdict(list)
        for item in succeeded:
            payload = item["payload"]
            predictions[str(item["item_id"])].append(
                (
                    int(item.get("repeat_index", 0)),
                    bool(payload["is_hate_speech"]),
                    _categories(payload.get("categories", []), label_space),
                )
            )
        primary = {
            item_id: (hate, categories)
            for item_id, values in predictions.items()
            for _, hate, categories in [min(values, key=lambda value: value[0])]
        }
        primaries[variant] = primary
        item_ids = sorted(primary)
        repeated = [values for values in predictions.values() if len(values) > 1]

        summary = {
            "variant": variant,
            "gold_total": len(gold),
            "evaluated_predictions": len(succeeded),
            "evaluated_items": len(primary),
            "coverage": _rate(len(primary), len(gold)),
            "failure_rate": _rate(len(attempted - set(primary)), len(attempted)),
            **_metrics(item_ids, primary, gold, label_space),
            "repeat_stability": None
            if not repeated
            else _rate(sum(len({value[1:] for value in values}) == 1 for values in repeated), len(repeated)),
            "repeat_item_count": len(repeated),
            "mean_input_tokens": _mean_usage(succeeded, "input_tokens"),
            "mean_output_tokens": _mean_usage(succeeded, "output_tokens"),
        }
        if bootstrap_samples and item_ids:
            summary["ci95"] = _bootstrap(item_ids, primary, gold, label_space, bootstrap_samples)
        summaries.append(summary)

    reference = primaries.get(reference_variant)
    for summary in summaries:
        if reference is not None and summary["variant"] != reference_variant:
            summary["mcnemar_vs_reference"] = _mcnemar(reference, primaries[summary["variant"]], gold)
    return summaries


def _merge(categories: list[str], mapping: dict[str, str]) -> list[str]:
    return list(dict.fromkeys(mapping.get(category, category) for category in categories))


def _categories(raw: list[str], label_space: list[str]) -> frozenset[str]:
    categories = set(raw) - {"unclassified"}
    if "political" in label_space:
        categories = {"political" if c in POLITICAL_CODES else c for c in categories}
    if "other" in label_space:
        categories = {"other" if c in FOLDABLE_INTO_OTHER and c not in label_space else c for c in categories}
    return frozenset(categories)


def _expected(label: dict[str, Any]) -> frozenset[str]:
    return frozenset(set(label.get("categories", [])) - {"unclassified"})


def _metrics(
    item_ids: list[str],
    primary: dict[str, tuple[bool, frozenset[str]]],
    gold: dict[str, dict[str, Any]],
    label_space: list[str],
) -> dict[str, Any]:
    btp = bfp = bfn = correct = 0
    per_category = {category: [0, 0, 0] for category in label_space}
    for item_id in item_ids:
        predicted_hate, predicted = primary[item_id]
        expected_hate = bool(gold[item_id]["is_hate_speech"])
        expected = _expected(gold[item_id])
        correct += predicted_hate == expected_hate
        btp += predicted_hate and expected_hate
        bfp += predicted_hate and not expected_hate
        bfn += expected_hate and not predicted_hate
        for category in per_category:
            per_category[category][0] += category in predicted and category in expected
            per_category[category][1] += category in predicted and category not in expected
            per_category[category][2] += category in expected and category not in predicted

    tp, fp, fn = (sum(counts[i] for counts in per_category.values()) for i in range(3))
    category_stats = {
        category: {**_prf(*counts), "support": counts[0] + counts[2]} for category, counts in per_category.items()
    }
    supported = [stats["f1"] for stats in category_stats.values() if stats["support"]]
    micro = _prf(tp, fp, fn)
    binary = _prf(btp, bfp, bfn)
    return {
        "binary_accuracy": _rate(correct, len(item_ids)),
        "binary_precision": binary["precision"],
        "binary_recall": binary["recall"],
        "binary_f1": binary["f1"],
        "category_micro_precision": micro["precision"],
        "category_micro_recall": micro["recall"],
        "category_micro_f1": micro["f1"],
        "category_macro_f1": _rate(sum(supported), len(supported)),
        "per_category": category_stats,
    }


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    return {"precision": precision, "recall": recall, "f1": _rate(2 * precision * recall, precision + recall)}


def _bootstrap(
    item_ids: list[str],
    primary: dict[str, tuple[bool, frozenset[str]]],
    gold: dict[str, dict[str, Any]],
    label_space: list[str],
    samples: int,
) -> dict[str, list[float]]:
    rng = random.Random(BOOTSTRAP_SEED)
    keys = ("binary_accuracy", "binary_f1", "category_micro_f1", "category_macro_f1")
    draws: dict[str, list[float]] = {key: [] for key in keys}
    for _ in range(samples):
        resampled = [rng.choice(item_ids) for _ in item_ids]
        metrics = _metrics_for_multiset(resampled, primary, gold, label_space)
        for key in keys:
            draws[key].append(metrics[key])
    return {key: [_percentile(values, 0.025), _percentile(values, 0.975)] for key, values in draws.items()}


def _metrics_for_multiset(item_ids, primary, gold, label_space):
    # Bootstrap resamples repeat item ids; give each draw its own key so duplicates count.
    keyed_primary = {f"{index}:{item_id}": primary[item_id] for index, item_id in enumerate(item_ids)}
    keyed_gold = {f"{index}:{item_id}": gold[item_id] for index, item_id in enumerate(item_ids)}
    return _metrics(list(keyed_primary), keyed_primary, keyed_gold, label_space)


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)]


def _mcnemar(
    reference: dict[str, tuple[bool, frozenset[str]]],
    other: dict[str, tuple[bool, frozenset[str]]],
    gold: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Exact two-sided McNemar test on binary correctness over items both variants scored."""
    shared = sorted(set(reference) & set(other))
    reference_only = other_only = 0
    for item_id in shared:
        expected = bool(gold[item_id]["is_hate_speech"])
        reference_right = reference[item_id][0] == expected
        other_right = other[item_id][0] == expected
        reference_only += reference_right and not other_right
        other_only += other_right and not reference_right
    discordant = reference_only + other_only
    tail = sum(comb(discordant, k) for k in range(min(reference_only, other_only) + 1)) / 2**discordant
    return {
        "shared_items": len(shared),
        "reference_only_correct": reference_only,
        "variant_only_correct": other_only,
        "p_value": min(1.0, 2 * tail) if discordant else 1.0,
    }


def _mean_usage(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row["usage"][key] for row in rows if isinstance(row.get("usage"), dict) and key in row["usage"]]
    return None if not values else sum(values) / len(values)


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG experiment results against gold labels.")
    parser.add_argument("--results-path", required=True)
    parser.add_argument("--gold-path", required=True)
    parser.add_argument("--reference-variant", default="three_vector_rag")
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    parser.add_argument("--json-output-path", default=None)
    parser.add_argument(
        "--merge-other", action="store_true", help="Score `other` as `profanity` (taxonomy v0.5.0 scheme)."
    )
    args = parser.parse_args()
    summaries = evaluate(
        read_jsonl(Path(args.results_path)),
        read_jsonl(Path(args.gold_path)),
        reference_variant=args.reference_variant,
        bootstrap_samples=args.bootstrap_samples,
        merge_categories=MERGED_CATEGORIES if args.merge_other else None,
    )
    if args.json_output_path:
        Path(args.json_output_path).write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    for summary in summaries:
        stability = summary["repeat_stability"]
        ci = summary.get("ci95", {})
        p_value = summary.get("mcnemar_vs_reference", {}).get("p_value")
        print(
            "\t".join(
                [
                    summary["variant"],
                    f"coverage={summary['coverage']:.3f}",
                    f"binary_acc={summary['binary_accuracy']:.3f}{_ci(ci.get('binary_accuracy'))}",
                    f"binary_f1={summary['binary_f1']:.3f}{_ci(ci.get('binary_f1'))}",
                    f"cat_micro_f1={summary['category_micro_f1']:.3f}",
                    f"cat_macro_f1={summary['category_macro_f1']:.3f}{_ci(ci.get('category_macro_f1'))}",
                    "stability=n/a" if stability is None else f"stability={stability:.3f}",
                    "" if p_value is None else f"mcnemar_p={p_value:.4f}",
                ]
            ).rstrip()
        )


def _ci(bounds: list[float] | None) -> str:
    return "" if not bounds else f"[{bounds[0]:.3f},{bounds[1]:.3f}]"


if __name__ == "__main__":
    main()
