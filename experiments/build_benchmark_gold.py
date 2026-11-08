"""Build experiment inputs and gold labels from held-out public benchmark splits.

The example collection is built from training splits only, so held-out splits can be
scored without retrieval leakage. Items whose text also appears in the training split
are dropped as an extra guard against duplicated rows across splits.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.analysis.example_loaders import load_dataset_split, stratified_sample
from app.analysis.models import ExampleDocument
from experiments.io import append_jsonl

DEFAULT_MANIFEST = "data/external/manifests/dataset_sources.yaml"


def build_benchmark(
    dataset_id: str,
    split: str,
    sample_size: int | None,
    min_per_category: int = 0,
    manifest_path: Path | str = DEFAULT_MANIFEST,
    project_root: Path | str | None = None,
    exclude_train_overlap: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    documents = load_dataset_split(manifest_path, dataset_id, split, project_root)
    loaded = len(documents)
    overlap = 0
    if exclude_train_overlap and split != "train":
        train_hashes = {
            document.text_hash for document in load_dataset_split(manifest_path, dataset_id, "train", project_root)
        }
        kept = [document for document in documents if document.text_hash not in train_hashes]
        overlap = loaded - len(kept)
        documents = kept
    if sample_size is not None:
        documents = _sample_with_floor(documents, sample_size, min_per_category)
    documents = sorted(documents, key=lambda document: document.doc_id)

    inputs = [{"item_id": document.doc_id, "source_type": "comment", "text": document.text} for document in documents]
    gold = [_gold_row(document) for document in documents]
    summary = {
        "dataset": dataset_id,
        "split": split,
        "loaded": loaded,
        "dropped_train_overlap": overlap,
        "sample_size": sample_size,
        "min_per_category": min_per_category,
        "items": len(gold),
        "hate_items": sum(row["is_hate_speech"] for row in gold),
        "categories": dict(sorted(Counter(c for row in gold for c in row["categories"]).items())),
    }
    return inputs, gold, summary


def _sample_with_floor(documents: list[ExampleDocument], sample_size: int, floor: int) -> list[ExampleDocument]:
    """Stratified sample that still keeps at least `floor` items of every primary category."""
    if sample_size >= len(documents):
        return documents
    groups: dict[str, list[ExampleDocument]] = {}
    for document in documents:
        groups.setdefault(_primary_category(document), []).append(document)
    reserved: list[ExampleDocument] = []
    for group in groups.values():
        reserved.extend(stratified_sample(group, min(floor, len(group))) if floor else [])
    reserved_ids = {document.doc_id for document in reserved}
    rest = [document for document in documents if document.doc_id not in reserved_ids]
    return reserved + stratified_sample(rest, max(sample_size - len(reserved), 0))


def _primary_category(document: ExampleDocument) -> str:
    return _gold_categories(document)[0] if _gold_categories(document) else "unclassified"


def _gold_categories(document: ExampleDocument) -> list[str]:
    """Corpus mapping, plus a coarse "political" label the evaluator can score.

    The corpus leaves political targets uncategorised because the six state/non-state
    categories cannot be recovered from the dataset; for scoring, any of them counts.
    """
    categories = list(document.mapped_categories)
    if document.is_hate_speech and "political" in document.target_labels:
        categories.append("political")
    return categories


def _gold_row(document: ExampleDocument) -> dict:
    return {
        "item_id": document.doc_id,
        "is_hate_speech": document.is_hate_speech,
        "categories": _gold_categories(document),
        "raw_labels": document.raw_labels,
        "source_dataset": document.source_dataset,
        "source_split": document.source_split,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gold JSONL from a held-out public benchmark split.")
    parser.add_argument("--dataset", required=True, choices=["k-haters", "beep", "kodoli"])
    parser.add_argument("--split", default="test")
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--min-per-category", type=int, default=0)
    parser.add_argument("--manifest-path", default=DEFAULT_MANIFEST)
    parser.add_argument("--input-output-path", required=True)
    parser.add_argument("--gold-output-path", required=True)
    args = parser.parse_args()

    inputs, gold, summary = build_benchmark(
        args.dataset, args.split, args.sample_size, args.min_per_category, args.manifest_path
    )
    for path in (args.input_output_path, args.gold_output_path):
        Path(path).unlink(missing_ok=True)
    append_jsonl(args.input_output_path, inputs)
    append_jsonl(args.gold_output_path, gold)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
