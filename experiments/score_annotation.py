"""Agreement between the human labels, the reference (Claude) labels and model results.

Usage:
  uv run python -m experiments.score_annotation \
    --sample experiments/outputs/annotation/sample_20261115.jsonl \
    --human experiments/outputs/annotation/yt-20261115.human.labels.jsonl \
    --results v071b=experiments/outputs/youtube/{set}.claude-haiku-5-5.v071b.results.jsonl \
    --results v080=experiments/outputs/youtube/{set}.claude-haiku-5-5.v080.results.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.analysis.taxonomy import TAXONOMY_CATEGORY_CODES, V07_CATEGORY_MAP

SCOPES = ("group", "individual", "none")
CATS = tuple(c for c in TAXONOMY_CATEGORY_CODES if c != "unclassified")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _cats(categories: list[str]) -> frozenset[str]:
    return frozenset(V07_CATEGORY_MAP.get(c, c) for c in categories) - {"unclassified"}


def _label(row: dict) -> dict:
    scope = row.get("target_scope") or ("none" if not row.get("is_hate_speech") else "individual")
    return {"scope": scope, "cats": _cats(row.get("categories") or []) if scope != "none" else frozenset()}


def kappa(a: list, b: list) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def compare(name: str, ref: dict[str, dict], other: dict[str, dict]) -> dict:
    ids = [i for i in ref if i in other]
    a = [ref[i]["scope"] for i in ids]
    b = [other[i]["scope"] for i in ids]
    out = {
        "name": name,
        "n": len(ids),
        "scope_accuracy": round(sum(x == y for x, y in zip(a, b)) / len(ids), 3),
        "scope_kappa": round(kappa(a, b), 3),
        "hate_kappa": round(kappa([x != "none" for x in a], [x != "none" for x in b]), 3),
        "confusion": {f"{x}->{y}": c for (x, y), c in sorted(Counter(zip(a, b)).items()) if x != y},
    }
    both_hate = [i for i in ids if ref[i]["scope"] != "none" and other[i]["scope"] != "none"]
    out["category_kappa_on_shared_hate"] = {
        c: round(kappa([c in ref[i]["cats"] for i in both_hate], [c in other[i]["cats"] for i in both_hate]), 3)
        for c in CATS
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--results", action="append", default=[], help="name=path with {set} placeholder")
    args = parser.parse_args()

    sample = _read(args.sample)
    human = {r["item_id"]: _label(r) for r in _read(args.human)}
    reference = {r["item_id"]: _label(r["reference"]) for r in sample}
    source = {r["item_id"]: r["source"] for r in sample}

    report = {
        "human_scopes": dict(Counter(v["scope"] for v in human.values())),
        "reference_scopes": dict(Counter(v["scope"] for v in reference.values())),
        "human_vs_reference": compare("human_vs_reference", human, reference),
        "models": [],
    }
    for spec in args.results:
        name, pattern = spec.split("=", 1)
        preds: dict[str, dict] = {}
        for s in sorted(set(source.values())):
            path = Path(pattern.format(set=s))
            if not path.exists():
                continue
            for row in _read(path):
                if row["item_id"] in source and source[row["item_id"]] == s and row.get("payload"):
                    preds[row["item_id"]] = _label(row["payload"])
        report["models"].append(
            {"model": name, "vs_human": compare(name, human, preds), "vs_reference": compare(name, reference, preds)}
        )
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
