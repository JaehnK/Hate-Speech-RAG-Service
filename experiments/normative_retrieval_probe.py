"""Measure how well the normative corpus is retrieved for benchmark comments (no LLM).

Runs the real retriever (same slots as a prompt version) over gold-hate items and checks
whether the retrieved normative chunks point the same way as the gold label:
- category match: a chunk's related_categories overlap the gold categories;
- level match: offensive-labelled items retrieve `offensive` chunks, hate-labelled
  items retrieve `group_hate`/`incitement` chunks;
- coverage: how many distinct chunks are ever retrieved (low = a few generic chunks
  dominate).
Dataset-label chunks are excluded from the scores. Query embeddings are cached on disk
so prompt versions and corpus changes can be compared cheaply.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import Counter
from pathlib import Path

from app.analysis.embeddings import create_embedding_function
from app.analysis.prompt_template import AUTHORITATIVE_SLOTS
from app.analysis.retriever import DualVectorRetriever
from app.analysis.retry import RetryPolicy
from app.analysis.taxonomy import POLITICAL_CATEGORIES
from experiments.io import read_jsonl

SCORED_TYPES = {"official_standard", "official_guideline", "international_summary", "platform_summary"}


class CachedQueryEmbedding:
    """Wraps the real embedding function; query vectors come from a disk cache when present."""

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self.cache: dict[str, list[float]] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        self._live = create_embedding_function(
            provider="upstage",
            model="embedding",
            api_key=os.environ["UPSTAGE_API_KEY"],
            retry_policy=RetryPolicy(max_attempts=8, max_delay_seconds=60),
        )

    def embed_query(self, input: list[str]) -> list[list[float]]:
        for text in input:
            if text not in self.cache:
                self.cache[text] = list(self._live.embed_query([text])[0])
        return [self.cache[text] for text in input]

    def __call__(self, input):
        return self._live(input)

    def __getattr__(self, name: str):
        return getattr(self._live, name)

    def save(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache))


def _gold_level(gold: dict) -> str:
    raw = gold["raw_labels"]
    return "offensive" if (raw.get("label") or raw.get("hate")) == "offensive" else "hate"


def _gold_categories(gold: dict) -> set[str]:
    categories = set(gold["categories"]) - {"unclassified"}
    if "political" in categories:
        categories = (categories - {"political"}) | set(POLITICAL_CATEGORIES)
    return categories


def probe(persist_directory: str, prompt_version: str, inputs_path: str, gold_path: str, sample: int, cache: Path) -> dict:
    gold = {row["item_id"]: row for row in read_jsonl(gold_path)}
    items = [row for row in read_jsonl(inputs_path) if gold[row["item_id"]]["is_hate_speech"]]
    random.Random(20261109).shuffle(items)
    items = items[:sample]

    embedding = CachedQueryEmbedding(cache)
    retriever = DualVectorRetriever(persist_directory, embedding)
    slots = AUTHORITATIVE_SLOTS[prompt_version]
    category_hits = level_hits = total = 0
    seen: Counter[str] = Counter()
    for item in items:
        row = gold[item["item_id"]]
        categories, level = _gold_categories(row), _gold_level(row)
        bundle = retriever.retrieve(
            f"{item['text']}\nsource_type=comment",
            taxonomy_n=0,
            authoritative_n=sum(slot[1] for slot in slots),
            example_n=6,
            authoritative_slots=slots,
        )
        for result in bundle.authoritative:
            if result.retrieval_tags[0] not in SCORED_TYPES:
                continue
            total += 1
            seen[result.doc_id] += 1
            category_hits += bool(set(result.related_categories) & categories)
            chunk_level = result.retrieval_tags[1]
            level_hits += (level == "offensive" and chunk_level == "offensive") or (
                level == "hate" and chunk_level in {"group_hate", "incitement"}
            )
    embedding.save()
    top = seen.most_common(3)
    return {
        "prompt_version": prompt_version,
        "items": len(items),
        "scored_chunks": total,
        "category_match": round(category_hits / total, 3),
        "level_match": round(level_hits / total, 3),
        "distinct_chunks": len(seen),
        "top3_share": round(sum(count for _, count in top) / total, 3),
        "top3": [doc_id for doc_id, _ in top],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--persist-directory", default=".chroma-dev")
    parser.add_argument("--prompt-version", action="append", required=True, choices=list(AUTHORITATIVE_SLOTS))
    parser.add_argument("--inputs", default="experiments/outputs/benchmark/dev.inputs.jsonl")
    parser.add_argument("--gold", default="experiments/outputs/benchmark/dev.gold.jsonl")
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--cache", default="experiments/outputs/benchmark/dev.query_vectors.json")
    args = parser.parse_args()
    for version in args.prompt_version:
        result = probe(args.persist_directory, version, args.inputs, args.gold, args.sample, Path(args.cache))
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
