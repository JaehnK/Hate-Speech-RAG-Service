from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import RetrievalBundle
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

        taxonomy = query("taxonomy", self.taxonomy_collection, taxonomy_n, parse_definition_query_result)
        authoritative = query(
            "authoritative", self.authoritative_collection, authoritative_n, parse_definition_query_result
        )
        examples = query("examples", self.example_collection, example_n, parse_example_query_result)

        return RetrievalBundle(
            taxonomy=tuple(taxonomy),
            authoritative=tuple(authoritative),
            examples=tuple(examples),
            failures=tuple(failures),
        )

    def close(self) -> None:
        close = getattr(self.embedding_function, "close", None)
        if close is not None:
            close()
