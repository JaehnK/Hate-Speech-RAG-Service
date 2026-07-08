from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.analysis.example_loaders import load_example_documents
from app.analysis.license_policy import DEFAULT_EXAMPLE_LICENSE_TIERS
from app.analysis.vector_store import EXAMPLE_COLLECTION_NAME, ingest_example_documents


def ingest_manifest_examples(
    manifest_path: Path | str,
    persist_directory: Path | str,
    project_root: Path | str | None = None,
    collection_name: str = EXAMPLE_COLLECTION_NAME,
    split: str = "train",
    allowed_license_tiers: tuple[str, ...] = DEFAULT_EXAMPLE_LICENSE_TIERS,
    limit_per_dataset: int | None = None,
    reset: bool = False,
) -> tuple[int, int]:
    documents = load_example_documents(
        manifest_path=manifest_path,
        split=split,
        allowed_license_tiers=allowed_license_tiers,
        project_root=project_root,
        limit_per_dataset=limit_per_dataset,
    )
    count = ingest_example_documents(
        persist_directory=persist_directory,
        documents=documents,
        collection_name=collection_name,
        reset=reset,
    )
    return len(documents), count


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest allowed example rows into Chroma.")
    parser.add_argument(
        "--manifest-path",
        default="data/external/manifests/dataset_sources.yaml",
        help="Dataset source manifest.",
    )
    parser.add_argument("--persist-directory", default=".chroma", help="Chroma persistent directory.")
    parser.add_argument("--project-root", default=".", help="Root used for relative manifest paths.")
    parser.add_argument("--collection-name", default=EXAMPLE_COLLECTION_NAME)
    parser.add_argument("--split", default="train")
    parser.add_argument(
        "--allowed-license-tier",
        action="append",
        default=[],
        help="Allowed license tier. Repeat to allow multiple tiers.",
    )
    parser.add_argument("--limit-per-dataset", type=int, default=None)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    allowed_tiers = tuple(args.allowed_license_tier) or DEFAULT_EXAMPLE_LICENSE_TIERS
    loaded_count, collection_count = ingest_manifest_examples(
        manifest_path=Path(args.manifest_path),
        persist_directory=Path(args.persist_directory),
        project_root=Path(args.project_root),
        collection_name=args.collection_name,
        split=args.split,
        allowed_license_tiers=allowed_tiers,
        limit_per_dataset=args.limit_per_dataset,
        reset=args.reset,
    )
    print(
        json.dumps(
            {
                "collection_name": args.collection_name,
                "persist_directory": args.persist_directory,
                "split": args.split,
                "allowed_license_tiers": allowed_tiers,
                "loaded_document_count": loaded_count,
                "collection_document_count": collection_count,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
