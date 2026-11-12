"""Disk-backed index for the similar-case examples.

Chroma loads a collection's whole HNSW index into memory as soon as it is touched. For the
examples (172k x 4096-dim Upstage vectors, about 2.9GB in memory) that does not fit the e2-micro VM.
This keeps the same vectors in a usearch HNSW index of 1-bit codes (the sign of each
dimension, Hamming distance), about 110MB, small enough to stay in the VM's page cache.
The binary search returns CANDIDATES neighbours, which are re-ranked with exact cosine
similarity against float16 copies of the vectors, read from disk row by row in parallel. Documents and metadata live in a small SQLite file next to it.

An earlier int8 index (0.7GB) did not fit in the page cache, so every search walked the
graph on disk; on the VM's pd-standard disk a comment took about 24s (docs/51).

On 300 dev queries, recall@6 against exact search was 0.963 for this index, 0.939 for the
int8 index and 0.858 for the Chroma HNSW index.

`ExampleIndex.query` returns the same shape as `chromadb.Collection.query`, so the retriever
and `parse_example_query_result` work unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from usearch.index import Index

from app.analysis.collections import EXAMPLE_COLLECTION_NAME

INDEX_DIRNAME = "example_index"
INDEX_FILE = "examples.b1.usearch"
LEGACY_INDEX_FILE = "examples.usearch"  # int8 index, superseded
META_FILE = "examples.sqlite"
VECTOR_FILE = "examples.f16.npy"
DTYPE = "b1"
METRIC = "hamming"
CONNECTIVITY = 16
EXPANSION_ADD = 128
EXPANSION_SEARCH = 512
CANDIDATES = 100
READ_THREADS = 32
PAGE_SIZE = 5000


def index_directory(persist_directory: Path | str) -> Path:
    return Path(persist_directory) / INDEX_DIRNAME


def has_example_index(persist_directory: Path | str) -> bool:
    """True when the index is built. A partial directory is an error, not a fallback:
    falling back would silently search the (empty) Chroma example collection."""
    directory = index_directory(persist_directory)
    if not directory.exists():
        return False
    missing = [name for name in (INDEX_FILE, META_FILE, VECTOR_FILE) if not (directory / name).exists()]
    if missing:
        hint = (
            f" Build it with: python -m app.analysis.example_index --from-vectors {directory}"
            if INDEX_FILE in missing and (directory / VECTOR_FILE).exists()
            else ""
        )
        raise RuntimeError(f"example index at {directory} is missing {', '.join(missing)}.{hint}")
    return True


def binary_codes(vectors: np.ndarray) -> np.ndarray:
    """1 bit per dimension (sign), packed into bytes."""
    return np.packbits(np.asarray(vectors) > 0, axis=-1)


class VectorRows:
    """Reads rows of a float16 .npy file with parallel pread calls.

    Re-ranking needs ~100 random rows per query, and the 1.4GB file does not fit in the
    VM's page cache. Page faults on a memory map read those rows one at a time; on a
    network disk (about 1ms per read) that alone took 100ms+. Issuing the reads together
    lets the disk serve them in parallel. FADV_RANDOM stops the kernel reading ahead.
    """

    def __init__(self, path: Path, threads: int = READ_THREADS) -> None:
        with open(path, "rb") as handle:
            version = np.lib.format.read_magic(handle)
            read_header = (
                np.lib.format.read_array_header_1_0
                if version == (1, 0)
                else np.lib.format.read_array_header_2_0
            )
            self.shape, fortran_order, self.dtype = read_header(handle)
            self._offset = handle.tell()
        if fortran_order or len(self.shape) != 2:
            raise ValueError(f"{path} must be a C-ordered 2-D array")
        self._row_bytes = self.shape[1] * self.dtype.itemsize
        self._fd = os.open(path, os.O_RDONLY)
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(self._fd, 0, 0, os.POSIX_FADV_RANDOM)
        self._pool = ThreadPoolExecutor(max_workers=threads, thread_name_prefix="example-rows")

    def _read(self, row: int) -> bytes:
        data = os.pread(self._fd, self._row_bytes, self._offset + row * self._row_bytes)
        if len(data) != self._row_bytes:
            raise RuntimeError(f"short read for example row {row}")
        return data

    def __getitem__(self, rows: np.ndarray) -> np.ndarray:
        chunks = list(self._pool.map(self._read, (int(row) for row in rows)))
        return np.frombuffer(b"".join(chunks), dtype=self.dtype).reshape(len(chunks), self.shape[1])

    def __len__(self) -> int:
        return self.shape[0]


class ExampleIndex:
    """Read-only example search with a Chroma-compatible query result."""

    def __init__(
        self,
        directory: Path | str,
        expansion_search: int = EXPANSION_SEARCH,
        candidates: int = CANDIDATES,
    ) -> None:
        directory = Path(directory)
        # Loaded into memory (about 110MB) so graph search never waits on the disk.
        index = Index.restore(str(directory / INDEX_FILE), view=False)
        if index is None:
            raise RuntimeError(f"cannot read {directory / INDEX_FILE}: corrupt or truncated file")
        self.index = index
        self.index.expansion_search = expansion_search
        self.candidates = candidates
        self.vectors = VectorRows(directory / VECTOR_FILE)
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
            matches = self.index.search(binary_codes(query), max(n_results, self.candidates))
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
    del vectors
    return build_binary_index(target)


def build_binary_index(directory: Path | str) -> dict[str, Any]:
    """Build the 1-bit index from the float16 vectors already in `directory`.

    Reads the vectors in pages, so it runs on the VM (peak memory is about the index size).
    """
    directory = Path(directory)
    vectors = np.load(directory / VECTOR_FILE, mmap_mode="r")
    total, dimensions = vectors.shape
    index = Index(
        ndim=dimensions,
        metric=METRIC,
        dtype=DTYPE,
        connectivity=CONNECTIVITY,
        expansion_add=EXPANSION_ADD,
    )
    for start in range(0, total, PAGE_SIZE):
        stop = min(start + PAGE_SIZE, total)
        index.add(np.arange(start, stop, dtype=np.uint64), binary_codes(vectors[start:stop]))
    temporary = directory / f"{INDEX_FILE}.tmp"
    index.save(str(temporary))
    temporary.replace(directory / INDEX_FILE)
    return {
        "target": str(directory),
        "examples": len(index),
        "dtype": DTYPE,
        "index_bytes": (directory / INDEX_FILE).stat().st_size,
    }


def benchmark(directory: Path | str, queries: int, candidates: int, cold: bool) -> dict[str, Any]:
    """Time search + re-rank on this machine, using perturbed stored vectors as queries.

    No API calls; run it where the index will serve (the VM) to see real disk latency.
    """
    directory = Path(directory)
    if cold and hasattr(os, "posix_fadvise"):
        descriptor = os.open(directory / VECTOR_FILE, os.O_RDONLY)
        os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
        os.close(descriptor)
    started = time.perf_counter()
    index = ExampleIndex(directory, candidates=candidates)
    load_seconds = time.perf_counter() - started
    rng = np.random.default_rng(0)
    rows = rng.choice(len(index.vectors), queries, replace=False)
    probes = index.vectors[np.sort(rows)].astype(np.float32)
    probes += rng.normal(scale=0.01, size=probes.shape).astype(np.float32)
    timings = []
    for probe in probes:
        started = time.perf_counter()
        index.query(query_embeddings=[probe.tolist()], n_results=6)
        timings.append((time.perf_counter() - started) * 1000)
    values = np.asarray(timings)
    return {
        "examples": index.count(),
        "candidates": candidates,
        "load_seconds": round(load_seconds, 1),
        "mean_ms": round(float(values.mean()), 1),
        "p50_ms": round(float(np.percentile(values, 50)), 1),
        "p95_ms": round(float(np.percentile(values, 95)), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the disk-backed example index from a Chroma store."
    )
    parser.add_argument(
        "--source",
        help="Chroma persist directory holding the example collection.",
    )
    parser.add_argument(
        "--target",
        help="Output directory, normally <store>/example_index.",
    )
    parser.add_argument(
        "--from-vectors",
        metavar="DIRECTORY",
        help="Rebuild only the 1-bit index from the float16 vectors in an existing example_index directory.",
    )
    parser.add_argument(
        "--benchmark",
        metavar="DIRECTORY",
        help="Time search + re-rank on an existing example_index directory (no API calls).",
    )
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument("--candidates", type=int, default=CANDIDATES)
    parser.add_argument("--warm", action="store_true", help="Keep the page cache instead of dropping the vector file from it.")
    args = parser.parse_args()
    if args.benchmark:
        summary = benchmark(args.benchmark, args.queries, args.candidates, cold=not args.warm)
    elif args.from_vectors:
        summary = build_binary_index(args.from_vectors)
    elif args.source and args.target:
        summary = build_example_index(args.source, args.target)
    else:
        parser.error("give --source and --target, or --from-vectors")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
