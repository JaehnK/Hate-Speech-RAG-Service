from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

import yaml

from app.analysis.license_policy import DEFAULT_DEFINITION_LICENSE_TIERS, definitions_allowed, normalize_license_tier
from app.analysis.models import DefinitionDocument
from app.analysis.taxonomy import DEFAULT_DEFINITION_CORPUS_VERSION
from app.analysis.vector_store import ingest_definition_documents


DEFINITION_FILE_PATTERNS = ("README.md", "guideline/*.md")


def load_manifest_definition_documents(
    manifest_path: Path | str,
    project_root: Path | str = ".",
    allowed_license_tiers: tuple[str, ...] = DEFAULT_DEFINITION_LICENSE_TIERS,
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
) -> list[DefinitionDocument]:
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8")) or {}
    root = Path(project_root)
    documents = []
    for source in manifest.get("datasets", []):
        if not definitions_allowed(source, allowed_license_tiers):
            continue
        source_root = root / source["local_path"]
        for pattern in DEFINITION_FILE_PATTERNS:
            for path in sorted(source_root.glob(pattern)):
                documents.extend(_markdown_documents(source, path, corpus_version))
    return documents


def ingest_manifest_definitions(
    manifest_path: Path | str,
    persist_directory: Path | str,
    project_root: Path | str = ".",
    allowed_license_tiers: tuple[str, ...] = DEFAULT_DEFINITION_LICENSE_TIERS,
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
    embedding_function=None,
) -> tuple[int, int]:
    documents = load_manifest_definition_documents(
        manifest_path,
        project_root,
        allowed_license_tiers,
        corpus_version,
    )
    count = ingest_definition_documents(persist_directory, documents, embedding_function=embedding_function)
    return len(documents), count


def _markdown_documents(source: dict, path: Path, corpus_version: str) -> list[DefinitionDocument]:
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)(?=^#{1,4}\s+)", text)
    result = []
    for index, section in enumerate(_bounded_sections(sections)):
        normalized = section.strip()
        if len(normalized) < 40:
            continue
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        source_id = str(source["id"])
        result.append(
            DefinitionDocument(
                doc_id=f"dataset:{source_id}:{path.stem}:{index}:{digest[:12]}",
                source_id=source_id,
                source_title=str(source.get("name", source_id)),
                source_url=source.get("source_url"),
                publisher=source_id,
                document_type="dataset_guideline",
                language="ko",
                normalized_language="ko",
                license_tier=normalize_license_tier(source.get("license_status")),
                retrieval_tags=("definition", "dataset_guideline", source_id),
                related_categories=(),
                chunk_text=normalized,
                chunk_hash=digest,
                corpus_version=corpus_version,
            )
        )
    return result


def _bounded_sections(sections: list[str], max_chars: int = 3000):
    for section in sections:
        paragraphs = [part.strip() for part in section.split("\n\n") if part.strip()]
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 2 > max_chars:
                yield current
                current = ""
            current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            yield current


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest licensed dataset definition documents into Chroma.")
    parser.add_argument("--manifest-path", default="data/external/manifests/dataset_sources.yaml")
    parser.add_argument("--persist-directory", default=".chroma")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    loaded, collection = ingest_manifest_definitions(args.manifest_path, args.persist_directory, args.project_root)
    print({"loaded_document_count": loaded, "collection_document_count": collection})


if __name__ == "__main__":
    main()
