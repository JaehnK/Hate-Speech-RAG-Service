from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExperimentInput:
    item_id: str
    text: str
    source_type: str


def read_inputs(path: Path | str, limit: int | None = None) -> list[ExperimentInput]:
    inputs = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            inputs.append(
                ExperimentInput(
                    item_id=str(row["item_id"]),
                    text=str(row["text"]),
                    source_type=str(row.get("source_type", "comment")),
                )
            )
            if limit is not None and len(inputs) >= limit:
                break
    return inputs


def append_jsonl(path: Path | str, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows
