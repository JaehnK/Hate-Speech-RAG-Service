from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.analysis.embeddings import DEFAULT_UPSTAGE_EMBEDDING_BASE_URL
from app.analysis.embeddings import DEFAULT_UPSTAGE_EMBEDDING_MODEL
from app.analysis.embeddings import create_embedding_function
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION, build_internal_taxonomy_documents
from app.analysis.vector_store import TAXONOMY_COLLECTION_NAME, ingest_definition_documents


def ingest_internal_taxonomy(
    persist_directory: Path | str,
    collection_name: str = TAXONOMY_COLLECTION_NAME,
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
    reset: bool = False,
    embedding_function=None,
) -> int:
    documents = build_internal_taxonomy_documents(corpus_version=corpus_version)
    return ingest_definition_documents(
        persist_directory=persist_directory,
        documents=documents,
        collection_name=collection_name,
        reset=reset,
        embedding_function=embedding_function,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest internal taxonomy cards into Chroma.")
    parser.add_argument("--persist-directory", default=".chroma", help="Chroma persistent directory.")
    parser.add_argument("--collection-name", default=TAXONOMY_COLLECTION_NAME)
    parser.add_argument("--corpus-version", default=DEFAULT_DEFINITION_CORPUS_VERSION)
    parser.add_argument("--embedding-provider", default=os.getenv("EMBEDDING_PROVIDER", "hash"))
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", DEFAULT_UPSTAGE_EMBEDDING_MODEL))
    parser.add_argument(
        "--embedding-base-url",
        default=os.getenv("UPSTAGE_EMBEDDING_BASE_URL", DEFAULT_UPSTAGE_EMBEDDING_BASE_URL),
    )
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    embedding_function = create_embedding_function(
        provider=args.embedding_provider,
        model=args.embedding_model,
        api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("UPSTAGE_API_KEY"),
        base_url=args.embedding_base_url,
    )
    count = ingest_internal_taxonomy(
        persist_directory=Path(args.persist_directory),
        collection_name=args.collection_name,
        corpus_version=args.corpus_version,
        reset=args.reset,
        embedding_function=embedding_function,
    )
    print(
        json.dumps(
            {
                "collection_name": args.collection_name,
                "persist_directory": args.persist_directory,
                "document_count": count,
                "corpus_version": args.corpus_version,
                "embedding_provider": args.embedding_provider,
                "embedding_model": args.embedding_model,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
