from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from app.analysis.embeddings import HashEmbeddingFunction
from app.analysis.models import DefinitionDocument, DefinitionSearchResult


DEFINITION_COLLECTION_NAME = "hate_speech_definitions"


def ingest_definition_documents(
    persist_directory: Path | str,
    documents: list[DefinitionDocument],
    collection_name: str = DEFINITION_COLLECTION_NAME,
    reset: bool = False,
) -> int:
    collection = _get_collection(persist_directory, collection_name, reset=reset)
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
) -> list[DefinitionSearchResult]:
    collection = _get_collection(persist_directory, collection_name)
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


def _get_collection(
    persist_directory: Path | str,
    collection_name: str,
    reset: bool = False,
) -> Any:
    client = chromadb.PersistentClient(path=str(persist_directory))
    if reset and collection_name in _collection_names(client):
        client.delete_collection(collection_name)

    return client.get_or_create_collection(
        collection_name,
        embedding_function=HashEmbeddingFunction(),
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
