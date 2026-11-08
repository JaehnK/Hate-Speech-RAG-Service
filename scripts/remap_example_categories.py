"""Recompute mapped_categories for indexed K-HATERS examples without re-embedding.

The categories are derived from the label and target labels already stored in each
example's metadata, using the current loader mapping. Stop the worker before running
against a live store, and keep a copy of the store as a backup.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import chromadb

from app.analysis.example_loaders import _k_haters_categories
from app.analysis.vector_store import EXAMPLE_COLLECTION_NAME

PAGE_SIZE = 5000


def remap(persist_directory: str, apply: bool) -> dict:
    collection = chromadb.PersistentClient(path=persist_directory).get_collection(EXAMPLE_COLLECTION_NAME)
    changes: Counter[tuple[str, str]] = Counter()
    scanned = updated = 0
    offset = 0
    while True:
        page = collection.get(
            where={"source_dataset": "k-haters"},
            include=["metadatas"],
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not page["ids"]:
            break
        ids, metadatas = [], []
        for doc_id, metadata in zip(page["ids"], page["metadatas"], strict=True):
            scanned += 1
            label = str(json.loads(metadata["raw_labels"])["label"]).strip().lower()
            targets = tuple(json.loads(metadata["target_labels"]))
            new = json.dumps(_k_haters_categories(label, targets), ensure_ascii=False)
            if new != metadata["mapped_categories"]:
                changes[(metadata["mapped_categories"], new)] += 1
                ids.append(doc_id)
                metadatas.append({**metadata, "mapped_categories": new})
        if apply and ids:
            collection.update(ids=ids, metadatas=metadatas)
            updated += len(ids)
        offset += len(page["ids"])

    return {
        "persist_directory": persist_directory,
        "applied": apply,
        "scanned": scanned,
        "changed": sum(changes.values()),
        "updated": updated,
        "transitions": {f"{old} -> {new}": count for (old, new), count in changes.most_common()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--persist-directory", required=True)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is a dry run.")
    args = parser.parse_args()
    print(json.dumps(remap(args.persist_directory, args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
