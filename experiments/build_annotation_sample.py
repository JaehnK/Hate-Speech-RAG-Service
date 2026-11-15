"""Build a blind labeling page for a second annotator.

Draws a stratified sample from the YouTube gold sets, writes the sample (with the
existing labels, for later agreement scoring) and a self-contained HTML labeling
page that shows only the comment and the video title. Comment text stays local:
both outputs go under experiments/outputs/, which is gitignored.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold_labels"
YT = ROOT / "outputs" / "youtube"
TEMPLATE = ROOT / "annotation" / "label_tool.html"

# (name, inputs, gold labels, items to draw)
SOURCES = (
    ("heldout200", YT / "heldout200.inputs.jsonl", GOLD / "youtube_heldout200.labels.jsonl", 90),
    ("eval300", YT / "eval300.titled.inputs.jsonl", GOLD / "youtube_eval300_v08.labels.jsonl", 60),
    ("celeb200", YT / "celeb200.inputs.jsonl", GOLD / "youtube_celeb200.labels.jsonl", 50),
)
# Share of each scope in the drawn sample; fewer clear non-hate items than the raw data.
SCOPE_SHARE = {"group": 0.35, "individual": 0.30, "none": 0.35}


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def draw(seed: int) -> list[dict]:
    rng = random.Random(seed)
    sample: list[dict] = []
    for name, inputs_path, gold_path, size in SOURCES:
        inputs = {row["item_id"]: row for row in _read(inputs_path)}
        gold = [row for row in _read(gold_path) if row["item_id"] in inputs]
        by_scope: dict[str, list[dict]] = {}
        for row in gold:
            by_scope.setdefault(row["target_scope"], []).append(row)
        picked: list[dict] = []
        for scope, share in SCOPE_SHARE.items():
            pool = by_scope.get(scope, [])
            picked += rng.sample(pool, min(len(pool), round(size * share)))
        picked = picked[:size]
        rest = [row for row in gold if row not in picked]
        picked += rng.sample(rest, max(0, size - len(picked)))
        for row in picked:
            item = inputs[row["item_id"]]
            sample.append(
                {
                    "item_id": row["item_id"],
                    "source": name,
                    "text": item["text"],
                    "video_title": item.get("video_title") or "",
                    "reference": {k: row[k] for k in ("is_hate_speech", "target_scope", "categories")},
                }
            )
    rng.shuffle(sample)
    return sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261115)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "annotation")
    args = parser.parse_args()

    sample = draw(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = args.output_dir / f"sample_{args.seed}.jsonl"
    sample_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sample), encoding="utf-8")

    # The page gets no reference labels: the annotator labels blind.
    blind = [{"item_id": r["item_id"], "text": r["text"], "video_title": r["video_title"]} for r in sample]
    payload = json.dumps({"sample_id": f"yt-{args.seed}", "items": blind}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    page_path = args.output_dir / f"label_{args.seed}.html"
    page_path.write_text(html, encoding="utf-8")

    scopes: dict[str, int] = {}
    for row in sample:
        scopes[row["reference"]["target_scope"]] = scopes.get(row["reference"]["target_scope"], 0) + 1
    print(json.dumps({"items": len(sample), "reference_scopes": scopes, "sample": str(sample_path), "page": str(page_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
