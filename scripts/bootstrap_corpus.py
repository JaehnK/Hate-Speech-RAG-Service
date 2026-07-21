from __future__ import annotations

import argparse
import json

from app.analysis.definition_ingest import ingest_manifest_definitions
from app.analysis.embeddings import create_embedding_function
from app.analysis.example_ingest import ingest_manifest_examples
from app.analysis.rag_ingest import ingest_internal_taxonomy
from app.core.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Build licensed definition and example retrieval collections.")
    parser.add_argument("--manifest-path", default="data/external/manifests/dataset_sources.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--persist-directory", default=None)
    parser.add_argument("--limit-per-dataset", type=int, default=None)
    parser.add_argument(
        "--stratified-sample-size",
        type=int,
        default=None,
        help="Downsample examples to this many documents, preserving each primary category's share.",
    )
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    persist_directory = args.persist_directory or settings.chroma_persist_directory
    embedding = create_embedding_function(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.upstage_embedding_base_url,
    )
    taxonomy_count = ingest_internal_taxonomy(
        persist_directory,
        reset=args.reset,
        embedding_function=embedding,
    )
    external_loaded, definition_count = ingest_manifest_definitions(
        args.manifest_path,
        persist_directory,
        project_root=args.project_root,
        reset=args.reset,
        embedding_function=embedding,
    )
    examples_loaded, example_count = ingest_manifest_examples(
        args.manifest_path,
        persist_directory,
        project_root=args.project_root,
        limit_per_dataset=args.limit_per_dataset,
        stratified_sample_size=args.stratified_sample_size,
        reset=args.reset,
        embedding_function=embedding,
    )
    print(
        json.dumps(
            {
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "taxonomy_collection_count": taxonomy_count,
                "external_authoritative_loaded": external_loaded,
                "authoritative_collection_count": definition_count,
                "examples_loaded": examples_loaded,
                "example_collection_count": example_count,
                "limited": args.limit_per_dataset is not None,
                "stratified_sample_size": args.stratified_sample_size,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
