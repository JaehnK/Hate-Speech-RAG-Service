"""Load the curated normative corpus (data/normative/*.md) into the authoritative store.

Each markdown file is one source: YAML front matter for source metadata, then one
chunk per `## ` section. A chunk's first lines `tags:`, `categories:` and `level:` are
metadata, not text. See data/normative/README.md for the format and field values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.analysis.embeddings import create_embedding_function
from app.analysis.license_policy import COMMERCIAL_OK, NONCOMMERCIAL_RESEARCH
from app.analysis.models import DefinitionDocument
from app.analysis.taxonomy import CATEGORY_CODES, DEFAULT_DEFINITION_CORPUS_VERSION
from app.analysis.vector_store import AUTHORITATIVE_COLLECTION_NAME, ingest_definition_documents

DEFAULT_CORPUS_DIR = "data/normative"

SOURCE_TYPES = (
    "official_standard",
    "official_guideline",
    "international_summary",
    "platform_summary",
    "dataset_guideline",
)
LEVELS = ("incitement", "group_hate", "offensive", "context_rule", "label_scheme")
# license_basis -> retrieval license tier. Statutes, own summaries and CC BY text are
# usable anywhere; excerpts of public works and quotations are kept to non-commercial
# research use (this project), so a commercial deployment can filter them out.
LICENSE_TIERS = {
    "public_domain_statute": COMMERCIAL_OK,
    "own_summary": COMMERCIAL_OK,
    "cc_by_4.0": COMMERCIAL_OK,
    "public_work": NONCOMMERCIAL_RESEARCH,
    "excerpt_quotation": NONCOMMERCIAL_RESEARCH,
}
REQUIRED_FIELDS = ("source_id", "title", "publisher", "source_url", "source_type", "license_basis")


class NormativeCorpusError(ValueError):
    pass


@dataclass(frozen=True)
class NormativeChunk:
    heading: str
    cues: str
    tags: tuple[str, ...]
    categories: tuple[str, ...]
    level: str
    body: str


def load_normative_documents(
    corpus_dir: Path | str = DEFAULT_CORPUS_DIR,
    allowed_license_tiers: tuple[str, ...] = (COMMERCIAL_OK, NONCOMMERCIAL_RESEARCH),
    corpus_version: str = DEFAULT_DEFINITION_CORPUS_VERSION,
) -> list[DefinitionDocument]:
    documents: list[DefinitionDocument] = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        if path.name == "README.md":
            continue
        meta, chunks = parse_normative_file(path)
        tier = LICENSE_TIERS[meta["license_basis"]]
        if tier not in allowed_license_tiers:
            continue
        for index, chunk in enumerate(chunks):
            text = f"[{meta['title']}] {chunk.heading}\n{chunk.body}"
            if chunk.cues:
                # Service-written comment-style examples; they bridge the vocabulary gap
                # between formal standards and comments for retrieval, and are labelled.
                text += f"\n적용 예(서비스 작성, 원문 아님): {chunk.cues}"
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            documents.append(
                DefinitionDocument(
                    doc_id=f"normative:{meta['source_id']}:{index}:{digest[:12]}",
                    source_id=meta["source_id"],
                    source_title=meta["title"],
                    source_url=meta["source_url"],
                    publisher=meta["publisher"],
                    document_type=meta["source_type"],
                    language=meta.get("language", "ko"),
                    normalized_language="ko",
                    license_tier=tier,
                    retrieval_tags=(meta["source_type"], chunk.level, *chunk.tags),
                    related_categories=chunk.categories,
                    chunk_text=text,
                    chunk_hash=digest,
                    corpus_version=corpus_version,
                )
            )
    return documents


def parse_normative_file(path: Path) -> tuple[dict, list[NormativeChunk]]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.S)
    if not match:
        raise NormativeCorpusError(f"{path}: missing front matter")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise NormativeCorpusError(f"{path}: invalid front matter ({exc})") from exc
    missing = [field for field in REQUIRED_FIELDS if not meta.get(field)]
    if missing:
        raise NormativeCorpusError(f"{path}: missing front matter fields {missing}")
    if meta["source_type"] not in SOURCE_TYPES:
        raise NormativeCorpusError(f"{path}: unknown source_type {meta['source_type']!r}")
    if meta["license_basis"] not in LICENSE_TIERS:
        raise NormativeCorpusError(f"{path}: unknown license_basis {meta['license_basis']!r}")
    meta = {key: str(value) for key, value in meta.items()}

    chunks = []
    for section in re.split(r"(?m)^## ", match.group(2))[1:]:
        heading, _, rest = section.partition("\n")
        chunks.append(_parse_chunk(path, heading.strip(), rest))
    if not chunks:
        raise NormativeCorpusError(f"{path}: no `## ` chunks")
    return meta, chunks


def _parse_chunk(path: Path, heading: str, rest: str) -> NormativeChunk:
    fields: dict[str, str] = {}
    lines = rest.strip("\n").split("\n")
    while lines and re.match(r"^(tags|categories|level|cues):", lines[0]):
        key, _, value = lines.pop(0).partition(":")
        fields[key] = value.strip()
    body = "\n".join(lines).strip()
    level = fields.get("level", "")
    if level not in LEVELS:
        raise NormativeCorpusError(f"{path} [{heading}]: unknown level {level!r}")
    categories = tuple(item.strip() for item in fields.get("categories", "").split(",") if item.strip())
    unknown = [category for category in categories if category not in CATEGORY_CODES]
    if unknown:
        raise NormativeCorpusError(f"{path} [{heading}]: unknown categories {unknown}")
    if len(body) < 80:
        raise NormativeCorpusError(f"{path} [{heading}]: chunk body too short")
    tags = tuple(item.strip() for item in fields.get("tags", "").split(",") if item.strip())
    return NormativeChunk(
        heading=heading, cues=fields.get("cues", ""), tags=tags, categories=categories, level=level, body=body
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus-dir", default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--persist-directory", default=".chroma")
    parser.add_argument("--collection-name", default=AUTHORITATIVE_COLLECTION_NAME)
    parser.add_argument("--embedding-provider", default=os.getenv("EMBEDDING_PROVIDER", "hash"))
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "embedding"))
    parser.add_argument("--commercial-only", action="store_true", help="Skip non-commercial-research sources.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without writing.")
    args = parser.parse_args()

    tiers = (COMMERCIAL_OK,) if args.commercial_only else (COMMERCIAL_OK, NONCOMMERCIAL_RESEARCH)
    documents = load_normative_documents(args.corpus_dir, allowed_license_tiers=tiers)
    summary = {
        "documents": len(documents),
        "by_source_type": {kind: sum(d.document_type == kind for d in documents) for kind in SOURCE_TYPES},
    }
    if not args.dry_run:
        embedding_function = create_embedding_function(
            provider=args.embedding_provider,
            model=args.embedding_model,
            api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("UPSTAGE_API_KEY"),
        )
        summary["collection_count"] = ingest_definition_documents(
            args.persist_directory,
            documents,
            collection_name=args.collection_name,
            embedding_function=embedding_function,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
