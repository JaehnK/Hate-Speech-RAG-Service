"""Disk-backed index for the similar-case examples.

Chroma loads a collection's whole HNSW index into memory as soon as it is touched. For the
examples (172k x 4096-dim Upstage vectors, about 2.9GB in memory) that does not fit the e2-micro VM.
This keeps the same vectors in a usearch HNSW index stored as int8 and opened with
`view=True` (memory-mapped), so only the pages a search visits are read. The int8 search
returns CANDIDATES neighbours, which are re-ranked with exact cosine similarity against
float16 copies of the vectors (also memory-mapped). Documents and metadata live in a small
SQLite file next to it.

On 300 dev queries, recall@6 against exact search was 0.936 for this index and 0.858 for
the Chroma HNSW index it replaces.

`ExampleIndex.query` returns the same shape as `chromadb.Collection.query`, so the retriever
and `parse_example_query_result` work unchanged.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import numpy as np
from usearch.index import Index

from app.analysis.collections import EXAMPLE_COLLECTION_NAME

INDEX_DIRNAME = "example_index"
INDEX_FILE = "examples.usearch"
META_FILE = "examples.sqlite"
VECTOR_FILE = "examples.f16.npy"
DTYPE = "i8"
CONNECTIVITY = 16
EXPANSION_ADD = 128
EXPANSION_SEARCH = 256
CANDIDATES = 48
PAGE_SIZE = 5000


def index_directory(persist_directory: Path | str) -> Path:
    return Path(persist_directory) / INDEX_DIRNAME


def has_example_index(persist_directory: Path | str) -> bool:
    directory = index_directory(persist_directory)
    return all(
        (directory / name).exists() for name in (INDEX_FILE, META_FILE, VECTOR_FILE)
    )


class ExampleIndex:
    """Read-only, memory-mapped example search with a Chroma-compatible query result."""

    def __init__(
        self, directory: Path | str, expansion_search: int = EXPANSION_SEARCH
    ) -> None:
        directory = Path(directory)
        self.index = Index.restore(str(directory / INDEX_FILE), view=True)
        self.index.expansion_search = expansion_search
        self.vectors = np.load(directory / VECTOR_FILE, mmap_mode="r")
        self._meta_path = directory / META_FILE
        self._local = threading.local()

    def _db(self) -> sqlite3.Connection:
        # One read-only connection per thread: the worker queries from several threads.
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(
                f"file:{self._meta_path}?mode=ro", uri=True, check_same_thread=False
            )
            self._local.db = db
        return db

    def count(self) -> int:
        return len(self.index)

    def query(
        self, query_embeddings: list[list[float]], n_results: int, **_: Any
    ) -> dict[str, list[list[Any]]]:
        ids, documents, metadatas, distances = [], [], [], []
        for vector in query_embeddings:
            query = np.asarray(vector, dtype=np.float32)
            query /= np.linalg.norm(query) or 1.0
            matches = self.index.search(query, max(n_results, CANDIDATES))
            candidates = np.sort(np.asarray(matches.keys, dtype=np.int64))
            similarity = self.vectors[candidates].astype(np.float32) @ query
            order = np.argsort(-similarity)[:n_results]
            keys = [int(candidates[i]) for i in order]
            # Same convention as Chroma's cosine space: distance = 1 - cosine similarity.
            exact = {int(candidates[i]): float(1.0 - similarity[i]) for i in order}
            rows = (
                {
                    key: (doc_id, document, metadata)
                    for key, doc_id, document, metadata in self._db().execute(
                        f"select key, doc_id, document, metadata from examples where key in ({','.join('?' * len(keys))})",
                        keys,
                    )
                }
                if keys
                else {}
            )
            ordered = [(key, exact[key]) for key in keys if key in rows]
            ids.append([rows[key][0] for key, _ in ordered])
            documents.append([rows[key][1] for key, _ in ordered])
            metadatas.append([json.loads(rows[key][2]) for key, _ in ordered])
            distances.append([distance for _, distance in ordered])
        return {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
        }


def build_example_index(source_directory: str, target_directory: str) -> dict[str, Any]:
    """Export the Chroma example collection (vectors, documents, metadata) into an ExampleIndex."""
    import chromadb

    target = Path(target_directory)
    target.mkdir(parents=True, exist_ok=False)
    collection = chromadb.PersistentClient(path=source_directory).get_collection(
        EXAMPLE_COLLECTION_NAME
    )
    total = collection.count()
    if total == 0:
        raise SystemExit("example collection is empty")
    dimensions = len(collection.get(include=["embeddings"], limit=1)["embeddings"][0])
    index = Index(
        ndim=dimensions,
        metric="cos",
        dtype=DTYPE,
        connectivity=CONNECTIVITY,
        expansion_add=EXPANSION_ADD,
    )
    db = sqlite3.connect(target / META_FILE)
    db.execute(
        "create table examples (key integer primary key, doc_id text unique, document text, metadata text)"
    )

    vectors = np.lib.format.open_memmap(
        target / VECTOR_FILE, mode="w+", dtype=np.float16, shape=(total, dimensions)
    )
    key = offset = 0
    while True:
        page = collection.get(
            include=["embeddings", "documents", "metadatas"],
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not page["ids"]:
            break
        keys = np.arange(key, key + len(page["ids"]), dtype=np.uint64)
        embeddings = np.asarray(page["embeddings"], dtype=np.float32)
        embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
        index.add(keys, embeddings)
        vectors[key : key + len(page["ids"])] = embeddings.astype(np.float16)
        db.executemany(
            "insert into examples values (?, ?, ?, ?)",
            [
                (int(k), doc_id, document, json.dumps(metadata, ensure_ascii=False))
                for k, doc_id, document, metadata in zip(
                    keys, page["ids"], page["documents"], page["metadatas"], strict=True
                )
            ],
        )
        key += len(page["ids"])
        offset += len(page["ids"])
    if key != total:
        raise RuntimeError(f"collection changed while exporting: {key} != {total}")
    vectors.flush()
    db.commit()
    db.close()
    index.save(str(target / INDEX_FILE))
    return {
        "target": str(target),
        "examples": key,
        "dtype": DTYPE,
        "index_bytes": (target / INDEX_FILE).stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the disk-backed example index from a Chroma store."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Chroma persist directory holding the example collection.",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Output directory, normally <store>/example_index.",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build_example_index(args.source, args.target), ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
