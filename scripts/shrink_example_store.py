"""Build a smaller vector store by sampling the example collection, reusing stored vectors.

The example index (172k x 4096 dims, about 2.8GB) does not fit in the e2-micro VM's memory.
This copies the taxonomy and authoritative collections as they are and keeps a stratified
sample of the examples, grouped by mapped_categories. Each group gets its proportional
share of --size, but groups below --floor keep min(count, floor) so rare categories stay
retrievable. No embedding calls are made; the Upstage embedding config is recorded so the runtime can
open the collections with its own embedding function.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path

import chromadb

from app.analysis.embeddings import create_embedding_function
from app.analysis.collections import (
    AUTHORITATIVE_COLLECTION_NAME,
    EXAMPLE_COLLECTION_NAME,
    TAXONOMY_COLLECTION_NAME,
)

PAGE_SIZE = 5000
ADD_BATCH = 1000
SEED = 20261111


def allocate(groups: dict[str, int], size: int, floor: int) -> dict[str, int]:
    """Per-group sample counts: a floor for small groups, the rest split proportionally."""
    fixed = {key: min(count, floor) for key, count in groups.items() if count <= floor}
    rest = {key: count for key, count in groups.items() if key not in fixed}
    budget = max(0, size - sum(fixed.values()))
    total = sum(rest.values())
    shares = {key: max(min(count, floor), round(budget * count / total)) for key, count in rest.items()}
    return {**fixed, **{key: min(count, shares[key]) for key, count in rest.items()}}


def _create_like(client, collection):
    # Keep the persisted embedding function config so the runtime's get_collection(ef=...) matches.
    embedding = create_embedding_function(
        provider="upstage", model="embedding", api_key=os.environ.get("UPSTAGE_API_KEY", "unused")
    )
    return client.create_collection(collection.name, metadata=collection.metadata, embedding_function=embedding)


def _copy(source, target, ids: list[str]) -> None:
    for start in range(0, len(ids), ADD_BATCH):
        batch = source.get(ids=ids[start : start + ADD_BATCH], include=["embeddings", "documents", "metadatas"])
        target.add(
            ids=batch["ids"],
            embeddings=batch["embeddings"],
            documents=batch["documents"],
            metadatas=batch["metadatas"],
        )


def shrink(source_dir: str, target_dir: str, size: int, floor: int) -> dict:
    if Path(target_dir).exists():
        raise SystemExit(f"{target_dir} already exists")
    source = chromadb.PersistentClient(path=source_dir)
    target = chromadb.PersistentClient(path=target_dir)

    for name in (TAXONOMY_COLLECTION_NAME, AUTHORITATIVE_COLLECTION_NAME):
        collection = source.get_collection(name)
        _copy(collection, _create_like(target, collection), collection.get()["ids"])

    examples = source.get_collection(EXAMPLE_COLLECTION_NAME)
    by_group: dict[str, list[str]] = defaultdict(list)
    offset = 0
    while True:
        page = examples.get(include=["metadatas"], limit=PAGE_SIZE, offset=offset)
        if not page["ids"]:
            break
        for doc_id, metadata in zip(page["ids"], page["metadatas"], strict=True):
            by_group[metadata["mapped_categories"]].append(doc_id)
        offset += len(page["ids"])

    counts = allocate({key: len(ids) for key, ids in by_group.items()}, size, floor)
    rng = random.Random(SEED)
    chosen = sorted(doc_id for key, ids in by_group.items() for doc_id in rng.sample(sorted(ids), counts[key]))
    _copy(examples, _create_like(target, examples), chosen)

    return {
        "source": source_dir,
        "target": target_dir,
        "examples": len(chosen),
        "groups": {key: f"{counts[key]}/{len(ids)}" for key, ids in sorted(by_group.items(), key=lambda kv: -len(kv[1]))},
        "counts": {name: target.get_collection(name).count() for name in (
            TAXONOMY_COLLECTION_NAME, AUTHORITATIVE_COLLECTION_NAME, EXAMPLE_COLLECTION_NAME)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--size", type=int, default=30000)
    parser.add_argument("--floor", type=int, default=0, help="Minimum kept per category group.")
    args = parser.parse_args()
    print(json.dumps(shrink(args.source, args.target, args.size, args.floor), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
