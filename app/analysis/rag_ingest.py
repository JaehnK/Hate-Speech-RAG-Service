from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION, build_internal_taxonomy_documents
from app.analysis.vector_store import DEFINITION_COLLECTION_NAME, ingest_definition_documents


def ingest_internal_taxonomy(
    persist_directory: Path | str,
    collection_name: str = DEFINITION_COLLECTION_NAME,
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
    reset: bool = False,
) -> int:
    documents = build_internal_taxonomy_documents(corpus_version=corpus_version)
    return ingest_definition_documents(
        persist_directory=persist_directory,
        documents=documents,
        collection_name=collection_name,
        reset=reset,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest internal taxonomy cards into Chroma.")
    parser.add_argument("--persist-directory", default=".chroma", help="Chroma persistent directory.")
    parser.add_argument("--collection-name", default=DEFINITION_COLLECTION_NAME)
    parser.add_argument("--corpus-version", default=DEFAULT_DEFINITION_CORPUS_VERSION)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    count = ingest_internal_taxonomy(
        persist_directory=Path(args.persist_directory),
        collection_name=args.collection_name,
        corpus_version=args.corpus_version,
        reset=args.reset,
    )
    print(
        json.dumps(
            {
                "collection_name": args.collection_name,
                "persist_directory": args.persist_directory,
                "document_count": count,
                "corpus_version": args.corpus_version,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
