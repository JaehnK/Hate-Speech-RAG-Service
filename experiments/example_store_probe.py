"""Compare example stores by what their nearest examples say about benchmark comments (no LLM).

For each dev item, takes the 6 nearest examples (same query text as the retriever) and scores
- vote F1: majority of neighbours' is_hate_speech against the gold hate label;
- category hit: for gold-hate items, any neighbour shares a gold category;
- hate share: mean fraction of hateful neighbours, for gold-hate and gold-non-hate items.
Query vectors are cached so several stores are compared on identical queries.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
from pathlib import Path

import chromadb

from app.analysis.collections import EXAMPLE_COLLECTION_NAME
from app.analysis.embeddings import create_embedding_function
from app.analysis.retry import RetryPolicy
from experiments.io import read_jsonl
from experiments.normative_retrieval_probe import _gold_categories

K = 6


def _query_vectors(items: list[dict], cache_path: Path) -> dict[str, list[float]]:
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    missing = [item for item in items if item["item_id"] not in cache]
    if missing:
        live = create_embedding_function(
            provider="upstage", model="embedding", api_key=os.environ["UPSTAGE_API_KEY"],
            retry_policy=RetryPolicy(max_attempts=8, max_delay_seconds=60),
        )
        for item in missing:
            cache[item["item_id"]] = list(live.embed_query([f"{item['text']}\nsource_type=comment"])[0])
        cache_path.write_text(json.dumps(cache))
    return cache


def probe(store: str, items: list[dict], gold: dict, vectors: dict) -> dict:
    collection = chromadb.PersistentClient(path=store).get_collection(EXAMPLE_COLLECTION_NAME)
    tp = fp = fn = category_hits = hate_items = 0
    share_hate: list[float] = []
    share_clean: list[float] = []
    for item in items:
        row = gold[item["item_id"]]
        result = collection.query(query_embeddings=[vectors[item["item_id"]]], n_results=K, include=["metadatas"])
        neighbours = result["metadatas"][0]
        hateful = sum(bool(m["is_hate_speech"]) for m in neighbours)
        predicted = hateful * 2 > len(neighbours)
        actual = row["is_hate_speech"]
        tp += predicted and actual
        fp += predicted and not actual
        fn += actual and not predicted
        (share_hate if actual else share_clean).append(hateful / len(neighbours))
        if actual:
            hate_items += 1
            wanted = _gold_categories(row)
            found = {c for m in neighbours for c in json.loads(m["mapped_categories"])}
            category_hits += bool(wanted & found) if wanted else True
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "store": store,
        "examples": collection.count(),
        "vote_precision": round(precision, 3),
        "vote_recall": round(recall, 3),
        "vote_f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "category_hit": round(category_hits / hate_items, 3),
        "hate_share_on_hate": round(sum(share_hate) / len(share_hate), 3),
        "hate_share_on_clean": round(sum(share_clean) / len(share_clean), 3),
        "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", required=True)
    parser.add_argument("--inputs", default="experiments/outputs/benchmark/dev.inputs.jsonl")
    parser.add_argument("--gold", default="experiments/outputs/benchmark/dev.gold.jsonl")
    parser.add_argument("--cache", default="experiments/outputs/benchmark/dev.query_vectors.json")
    args = parser.parse_args()
    gold = {row["item_id"]: row for row in read_jsonl(args.gold)}
    items = list(read_jsonl(args.inputs))
    vectors = _query_vectors(items, Path(args.cache))
    print(json.dumps(probe(args.store, items, gold, vectors), ensure_ascii=False))


if __name__ == "__main__":
    main()
