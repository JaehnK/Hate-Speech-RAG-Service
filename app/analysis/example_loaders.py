from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import hf_hub_download

from app.analysis.license_policy import DEFAULT_EXAMPLE_LICENSE_TIERS, examples_allowed
from app.analysis.license_policy import normalize_license_tier
from app.analysis.models import ExampleDocument


SPLIT_SEED = "20260709"


def load_example_documents(
    manifest_path: Path | str,
    split: str = "train",
    allowed_license_tiers: tuple[str, ...] = DEFAULT_EXAMPLE_LICENSE_TIERS,
    project_root: Path | str | None = None,
    limit_per_dataset: int | None = None,
) -> list[ExampleDocument]:
    manifest_path = Path(manifest_path)
    root = Path(project_root) if project_root else Path.cwd()
    sources = _load_sources(manifest_path)
    documents: list[ExampleDocument] = []

    for source in sources:
        if not examples_allowed(source, allowed_license_tiers):
            continue
        loader = _loader_for(source.get("id"))
        if loader is None:
            continue
        source_documents = loader(source, split, root)
        documents.extend(_limit(source_documents, limit_per_dataset))

    return documents


def _load_sources(manifest_path: Path) -> list[dict[str, Any]]:
    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file)
    return list(manifest.get("datasets") or [])


def _loader_for(dataset_id: str | None):
    return {
        "beep": _load_beep,
        "kodoli": _load_kodoli,
        "k-haters": _load_k_haters,
    }.get(dataset_id)


def _load_beep(source: dict[str, Any], split: str, root: Path) -> Iterator[ExampleDocument]:
    split_files = {
        "train": "labeled/train.tsv",
        "validation": "labeled/dev.tsv",
        "val": "labeled/dev.tsv",
    }
    relative_path = split_files.get(split)
    if relative_path is None:
        return

    path = _source_path(source, root) / relative_path
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for index, row in enumerate(reader):
            text = row["comments"]
            bias = row["bias"].strip().lower()
            hate = row["hate"].strip().lower()
            is_hate = hate != "none" or bias != "none"
            categories = _beep_categories(bias, hate)
            yield _example(
                doc_id=f"beep:{_normal_split(split)}:{index}",
                text=text,
                source=source,
                split=_normal_split(split),
                raw_labels={
                    "contain_gender_bias": row["contain_gender_bias"],
                    "bias": bias,
                    "hate": hate,
                },
                mapped_categories=categories,
                is_hate_speech=is_hate,
                target_labels=(bias,) if bias != "none" else (),
                hate_type_labels=(hate,) if hate != "none" else (),
            )


def _load_k_haters(source: dict[str, Any], split: str, root: Path) -> Iterator[ExampleDocument]:
    split_files = {
        "train": "train.jsonl",
        "validation": "val.jsonl",
        "val": "val.jsonl",
        "test": "test.jsonl",
    }
    relative_path = split_files.get(split)
    if relative_path is None:
        return

    path = _source_path(source, root, path_key="data_local_path") / relative_path
    if not path.exists():
        path = _download_huggingface_dataset_file(source, relative_path)
    with path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            row = json.loads(line)
            label = str(row["label"]).strip().lower()
            target_labels = tuple(str(label).strip().lower() for label in row.get("target_label", []))
            is_hate = label != "normal"
            categories = _k_haters_categories(label, target_labels)
            yield _example(
                doc_id=f"k-haters:{_normal_split(split)}:{index}",
                text=row["text"],
                source=source,
                split=_normal_split(split),
                raw_labels={"label": label, "target_label": list(target_labels)},
                mapped_categories=categories,
                is_hate_speech=is_hate,
                target_labels=target_labels,
                hate_type_labels=(label,) if label != "normal" else (),
            )


def _load_kodoli(source: dict[str, Any], split: str, root: Path) -> Iterator[ExampleDocument]:
    path = _source_path(source, root) / "data/kodoli.csv"
    normalized_split = _normal_split(split)
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            text = row["sentences"]
            doc_split = _deterministic_split(f"kodoli:{row['index']}:{text}")
            if doc_split != normalized_split:
                continue

            abuse = row["abuse"].strip().upper()
            offensiveness = row["offensiveness"].strip().upper()
            is_hate = abuse != "NON" or offensiveness != "NOT"
            yield _example(
                doc_id=f"kodoli:{doc_split}:{row['index']}",
                text=text,
                source=source,
                split=doc_split,
                raw_labels={
                    "abuse": abuse,
                    "sentiment": row["sentiment"].strip().upper(),
                    "offensiveness": offensiveness,
                },
                mapped_categories=("profanity",) if is_hate else ("unclassified",),
                is_hate_speech=is_hate,
                hate_type_labels=(offensiveness,) if offensiveness != "NOT" else (),
            )


def _beep_categories(bias: str, hate: str) -> tuple[str, ...]:
    categories: list[str] = []
    if bias == "gender":
        categories.append("gender")
    elif bias == "others":
        categories.append("identity")

    if hate == "offensive" and not categories:
        categories.append("profanity")
    if hate == "hate" and not categories:
        categories.append("other")

    return tuple(categories or ["unclassified"])


def _k_haters_categories(label: str, target_labels: tuple[str, ...]) -> tuple[str, ...]:
    if label == "normal":
        return ("unclassified",)

    categories: list[str] = []
    for target_label in target_labels:
        if target_label == "gender":
            categories.append("gender")
        elif target_label == "age":
            categories.append("age")
        elif target_label in {"race", "religion", "disability"}:
            categories.append("identity")

    if label == "offensive" and not categories:
        categories.append("profanity")

    return tuple(dict.fromkeys(categories or ["other"]))


def _example(
    doc_id: str,
    text: str,
    source: dict[str, Any],
    split: str,
    raw_labels: dict[str, Any],
    mapped_categories: tuple[str, ...],
    is_hate_speech: bool,
    target_labels: tuple[str, ...] = (),
    hate_type_labels: tuple[str, ...] = (),
) -> ExampleDocument:
    return ExampleDocument(
        doc_id=doc_id,
        text=text,
        source_dataset=str(source["id"]),
        source_split=split,
        source_revision=source.get("source_revision"),
        license_tier=normalize_license_tier(source.get("license_status")),
        raw_labels=raw_labels,
        mapped_categories=mapped_categories,
        is_hate_speech=is_hate_speech,
        target_labels=target_labels,
        hate_type_labels=hate_type_labels,
        text_hash=sha256(text.encode("utf-8")).hexdigest(),
    )


def _source_path(source: dict[str, Any], root: Path, path_key: str = "local_path") -> Path:
    raw_path = source.get(path_key) or source.get("local_path")
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return root / path


def _download_huggingface_dataset_file(source: dict[str, Any], filename: str) -> Path:
    repo_id = source.get("huggingface_repo")
    if not repo_id:
        raise FileNotFoundError(filename)
    cache_dir = os.getenv("HF_HOME") or "/tmp/huggingface"
    return Path(hf_hub_download(repo_id=str(repo_id), filename=filename, repo_type="dataset", cache_dir=cache_dir))


def _limit(documents: Iterator[ExampleDocument], limit: int | None) -> list[ExampleDocument]:
    limited = []
    for document in documents:
        if not document.text.strip():
            continue
        limited.append(document)
        if limit is not None and len(limited) >= limit:
            break
    return limited


def _normal_split(split: str) -> str:
    return "validation" if split == "val" else split


def _deterministic_split(key: str) -> str:
    bucket = int(sha256(f"{SPLIT_SEED}:{key}".encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "validation"
    return "test"
