"""Score experiment inputs with Jev, one JSONL row per item (resumable)."""

from __future__ import annotations

import argparse
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from app.analysis.jev_client import JEV_QUESTION_VERSION, JevClient
from experiments.io import ExperimentInput, append_jsonl, read_inputs, read_jsonl


def scored_ids(path: Path | str) -> set[str]:
    if not Path(path).exists():
        return set()
    return {row["item_id"] for row in read_jsonl(path) if row.get("status") == "succeeded"}


def score_item(client: JevClient, item: ExperimentInput) -> dict:
    try:
        score = client.score(item.text)
    except Exception as exc:  # recorded so a rerun with --resume retries only failures
        return {"item_id": item.item_id, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "item_id": item.item_id,
        "status": "succeeded",
        "p_hate": score.p_hate,
        "model": score.model,
        "question_version": JEV_QUESTION_VERSION,
        "input_tokens": score.input_tokens,
        "output_tokens": score.output_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    client = JevClient(os.environ.get("TYPESAFE_API_KEY", ""))
    items = read_inputs(args.input_path)
    if args.resume:
        done = scored_ids(args.output_path)
        items = [item for item in items if item.item_id not in done]
    elif Path(args.output_path).exists():
        raise SystemExit(f"{args.output_path} exists; pass --resume or remove it")

    lock = threading.Lock()
    failed = 0

    def run(item: ExperimentInput) -> None:
        nonlocal failed
        row = score_item(client, item)
        with lock:
            append_jsonl(args.output_path, [row])
            failed += row["status"] != "succeeded"

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(run, items))
    print(f"scored {len(items)} items, failed {failed}")


if __name__ == "__main__":
    main()
