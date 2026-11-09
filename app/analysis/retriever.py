from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import RetrievalBundle
from app.analysis.normative_guidance import category_filter, guided_categories
from app.analysis.vector_store import (
    AUTHORITATIVE_COLLECTION_NAME,
    EXAMPLE_COLLECTION_NAME,
    TAXONOMY_COLLECTION_NAME,
    _get_collection,
    parse_definition_query_result,
    parse_example_query_result,
)


class DualVectorRetriever:
    def __init__(
        self,
        persist_directory: Path | str,
        embedding_function: Any | None = None,
        client: Any | None = None,
    ) -> None:
        self.embedding_function = embedding_function or HashEmbeddingFunction()
        self.client = client or chromadb.PersistentClient(path=str(persist_directory))
        self.taxonomy_collection = _get_collection(
            persist_directory,
            TAXONOMY_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            client=self.client,
        )
        self.authoritative_collection = _get_collection(
            persist_directory,
            AUTHORITATIVE_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            client=self.client,
        )
        self.example_collection = _get_collection(
            persist_directory,
            EXAMPLE_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            client=self.client,
        )

    def retrieve(
        self,
        query_text: str,
        *,
        taxonomy_n: int,
        authoritative_n: int,
        example_n: int,
        pinned_taxonomy_ids: tuple[str, ...] = (),
        authoritative_slots: tuple[tuple, ...] = (),
    ) -> RetrievalBundle:
        if max(taxonomy_n, authoritative_n, example_n) <= 0:
            # LLM-only baseline: nothing to retrieve, so skip the embedding call too.
            return RetrievalBundle(taxonomy=(), authoritative=(), examples=(), failures=())
        vector = self.embedding_function.embed_query([query_text])[0]
        failures: list[str] = []

        def query(name: str, collection, n: int, parse) -> list:
            if n <= 0:
                return []
            try:
                return parse(collection.query(query_embeddings=[vector], n_results=n))
            except Exception:
                failures.append(name)
                return []

        pinned = self._pinned_taxonomy(pinned_taxonomy_ids) if taxonomy_n > 0 else []
        pinned_ids = {result.doc_id for result in pinned}
        # Fetch extra so pinned cards that also rank highly do not shrink the searched slots.
        searched = query(
            "taxonomy", self.taxonomy_collection, taxonomy_n + len(pinned), parse_definition_query_result
        )
        taxonomy = pinned + [result for result in searched if result.doc_id not in pinned_ids][:taxonomy_n]
        # Similar cases first: their labels can steer the normative-document search.
        examples = query("examples", self.example_collection, example_n, parse_example_query_result)
        if authoritative_slots and authoritative_n > 0:
            guide = category_filter(guided_categories(examples))
            authoritative = self._slotted_authoritative(vector, authoritative_slots, failures, guide)
        else:
            authoritative = query(
                "authoritative", self.authoritative_collection, authoritative_n, parse_definition_query_result
            )

        return RetrievalBundle(
            taxonomy=tuple(taxonomy),
            authoritative=tuple(authoritative),
            examples=tuple(examples),
            failures=tuple(failures),
        )

    def _slotted_authoritative(
        self, vector, slots: tuple[tuple, ...], failures: list[str], guide: dict | None = None
    ) -> list:
        """Fixed number of results per document_type, so one source type cannot crowd out the rest.

        A slot given as (document_type, n, True) is filtered by `guide` (categories from the
        similar cases) when there is one, and topped up without the filter if it comes back short.
        """
        results: list = []
        seen: set[str] = set()
        failed = 0
        for slot in slots:
            document_type, n = slot[0], slot[1]
            guided = len(slot) > 2 and slot[2] and guide is not None
            if n <= 0:
                continue
            wheres = [{"document_type": document_type}]
            if guided:
                wheres.insert(0, {"$and": [{"document_type": document_type}, guide]})
            picked: list = []
            try:
                for where in wheres:
                    raw = self.authoritative_collection.query(
                        query_embeddings=[vector], n_results=n + len(picked), where=where
                    )
                    for result in parse_definition_query_result(raw):
                        if result.doc_id not in seen and len(picked) < n:
                            picked.append(result)
                            seen.add(result.doc_id)
                    if len(picked) >= n:
                        break
            except Exception:
                failed += 1
                continue
            results.extend(picked)
        if failed and failed == sum(slot[1] > 0 for slot in slots):
            failures.append("authoritative")
        return results

    def _pinned_taxonomy(self, doc_ids: tuple[str, ...]) -> list:
        """Rule cards that every prompt needs regardless of similarity (cached per id set)."""
        if not doc_ids:
            return []
        cache = self.__dict__.setdefault("_pinned_cache", {})
        if doc_ids not in cache:
            try:
                got = self.taxonomy_collection.get(ids=list(doc_ids), include=["documents", "metadatas"])
            except Exception:
                return []
            by_id = {
                doc_id: (document, metadata)
                for doc_id, document, metadata in zip(got["ids"], got["documents"], got["metadatas"], strict=True)
            }
            ordered = [doc_id for doc_id in doc_ids if doc_id in by_id]
            cache[doc_ids] = parse_definition_query_result(
                {
                    "ids": [ordered],
                    "documents": [[by_id[doc_id][0] for doc_id in ordered]],
                    "metadatas": [[by_id[doc_id][1] for doc_id in ordered]],
                    "distances": [[]],
                }
            )
        return list(cache[doc_ids])

    def close(self) -> None:
        close = getattr(self.embedding_function, "close", None)
        if close is not None:
            close()
