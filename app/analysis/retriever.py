from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import RetrievalBundle
from app.analysis.vector_store import (
    DEFINITION_COLLECTION_NAME,
    EXAMPLE_COLLECTION_NAME,
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
        self.definition_collection = _get_collection(
            persist_directory,
            DEFINITION_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            client=self.client,
        )
        self.example_collection = _get_collection(
            persist_directory,
            EXAMPLE_COLLECTION_NAME,
            embedding_function=self.embedding_function,
            client=self.client,
        )

    def retrieve(self, query_text: str, *, definition_n: int, example_n: int) -> RetrievalBundle:
        vector = self.embedding_function.embed_query([query_text])[0]
        definitions = []
        examples = []
        failures = []

        try:
            result = self.definition_collection.query(query_embeddings=[vector], n_results=definition_n)
            definitions = parse_definition_query_result(result)
        except Exception:
            failures.append("definitions")

        try:
            result = self.example_collection.query(query_embeddings=[vector], n_results=example_n)
            examples = parse_example_query_result(result)
        except Exception:
            failures.append("examples")

        return RetrievalBundle(
            definitions=tuple(definitions),
            examples=tuple(examples),
            failures=tuple(failures),
        )

    def close(self) -> None:
        close = getattr(self.embedding_function, "close", None)
        if close is not None:
            close()
