from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import DefinitionDocument, DefinitionSearchResult
from app.analysis.models import ExampleDocument, ExampleSearchResult


DEFINITION_COLLECTION_NAME = "hate_speech_definitions"
EXAMPLE_COLLECTION_NAME = "hate_speech_examples"


def ingest_definition_documents(
    persist_directory: Path | str,
    documents: list[DefinitionDocument],
    collection_name: str = DEFINITION_COLLECTION_NAME,
    reset: bool = False,
    embedding_function: Any | None = None,
) -> int:
    collection = _get_collection(
        persist_directory,
        collection_name,
        reset=reset,
        embedding_function=embedding_function,
    )
    if not documents:
        return collection.count()
    collection.upsert(
        ids=[document.doc_id for document in documents],
        documents=[document.chunk_text for document in documents],
        metadatas=[_definition_metadata(document) for document in documents],
    )
    return collection.count()


def query_definition_documents(
    persist_directory: Path | str,
    query_text: str,
    collection_name: str = DEFINITION_COLLECTION_NAME,
    n_results: int = 5,
    embedding_function: Any | None = None,
) -> list[DefinitionSearchResult]:
    if n_results <= 0:
        return []

    collection = _get_collection(
        persist_directory,
        collection_name,
        embedding_function=embedding_function,
    )
    result = collection.query(query_texts=[query_text], n_results=n_results)
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    search_results = []
    for index, doc_id in enumerate(ids):
        metadata = metadatas[index]
        search_results.append(
            DefinitionSearchResult(
                doc_id=doc_id,
                chunk_text=documents[index],
                source_id=str(metadata["source_id"]),
                source_title=str(metadata["source_title"]),
                retrieval_tags=tuple(json.loads(str(metadata["retrieval_tags"]))),
                related_categories=tuple(json.loads(str(metadata["related_categories"]))),
                distance=distances[index] if distances else None,
            )
        )
    return search_results


def ingest_example_documents(
    persist_directory: Path | str,
    documents: list[ExampleDocument],
    collection_name: str = EXAMPLE_COLLECTION_NAME,
    reset: bool = False,
    embedding_function: Any | None = None,
) -> int:
    collection = _get_collection(
        persist_directory,
        collection_name,
        reset=reset,
        embedding_function=embedding_function,
    )
    if not documents:
        return collection.count()

    collection.upsert(
        ids=[document.doc_id for document in documents],
        documents=[document.text for document in documents],
        metadatas=[_example_metadata(document) for document in documents],
    )
    return collection.count()


def query_example_documents(
    persist_directory: Path | str,
    query_text: str,
    collection_name: str = EXAMPLE_COLLECTION_NAME,
    n_results: int = 5,
    embedding_function: Any | None = None,
) -> list[ExampleSearchResult]:
    if n_results <= 0:
        return []

    collection = _get_collection(
        persist_directory,
        collection_name,
        embedding_function=embedding_function,
    )
    result = collection.query(query_texts=[query_text], n_results=n_results)
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    search_results = []
    for index, doc_id in enumerate(ids):
        metadata = metadatas[index]
        search_results.append(
            ExampleSearchResult(
                doc_id=doc_id,
                text=documents[index],
                source_dataset=str(metadata["source_dataset"]),
                source_split=str(metadata["source_split"]),
                license_tier=str(metadata["license_tier"]),
                mapped_categories=tuple(json.loads(str(metadata["mapped_categories"]))),
                is_hate_speech=_metadata_bool(metadata["is_hate_speech"]),
                distance=distances[index] if distances else None,
            )
        )
    return search_results


def _get_collection(
    persist_directory: Path | str,
    collection_name: str,
    reset: bool = False,
    embedding_function: Any | None = None,
) -> Any:
    client = chromadb.PersistentClient(path=str(persist_directory))
    if reset and collection_name in _collection_names(client):
        client.delete_collection(collection_name)

    return client.get_or_create_collection(
        collection_name,
        embedding_function=embedding_function or HashEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def _collection_names(client: Any) -> set[str]:
    return {str(getattr(collection, "name", collection)) for collection in client.list_collections()}


def _definition_metadata(document: DefinitionDocument) -> dict[str, str]:
    return {
        "doc_id": document.doc_id,
        "source_id": document.source_id,
        "source_title": document.source_title,
        "source_url": document.source_url or "",
        "publisher": document.publisher,
        "document_type": document.document_type,
        "language": document.language,
        "normalized_language": document.normalized_language,
        "license_tier": document.license_tier,
        "retrieval_tags": json.dumps(document.retrieval_tags, ensure_ascii=False),
        "related_categories": json.dumps(document.related_categories, ensure_ascii=False),
        "chunk_hash": document.chunk_hash,
        "corpus_version": document.corpus_version,
    }


def _example_metadata(document: ExampleDocument) -> dict[str, str | bool]:
    return {
        "doc_id": document.doc_id,
        "source_dataset": document.source_dataset,
        "source_split": document.source_split,
        "source_revision": document.source_revision or "",
        "license_tier": document.license_tier,
        "raw_labels": json.dumps(document.raw_labels, ensure_ascii=False),
        "mapped_categories": json.dumps(document.mapped_categories, ensure_ascii=False),
        "is_hate_speech": document.is_hate_speech,
        "target_labels": json.dumps(document.target_labels, ensure_ascii=False),
        "hate_type_labels": json.dumps(document.hate_type_labels, ensure_ascii=False),
        "text_hash": document.text_hash,
    }


def _metadata_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"
