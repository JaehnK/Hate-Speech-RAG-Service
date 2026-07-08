from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from experiments.io import read_jsonl


HAIKU_INPUT_PER_MILLION = 1.0
HAIKU_OUTPUT_PER_MILLION = 5.0


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["variant"])].append(row)

    summaries = []
    for variant, items in sorted(grouped.items()):
        succeeded = [item for item in items if item["status"] == "succeeded"]
        failed = [item for item in items if item["status"] != "succeeded"]
        input_tokens = sum(int(item.get("usage", {}).get("input_tokens", 0)) for item in succeeded)
        output_tokens = sum(int(item.get("usage", {}).get("output_tokens", 0)) for item in succeeded)
        attempts = sum(int(item.get("attempts", 0)) for item in items)
        summaries.append(
            {
                "variant": variant,
                "total": len(items),
                "succeeded": len(succeeded),
                "failed": len(failed),
                "failure_rate": _rate(len(failed), len(items)),
                "retry_rate": _rate(attempts - len(items), len(items)),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_haiku_cost_usd": _haiku_cost(input_tokens, output_tokens),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize RAG experiment JSONL results.")
    parser.add_argument("--results-path", required=True)
    args = parser.parse_args()

    for summary in summarize(read_jsonl(Path(args.results_path))):
        print(
            "\t".join(
                [
                    summary["variant"],
                    f"total={summary['total']}",
                    f"succeeded={summary['succeeded']}",
                    f"failed={summary['failed']}",
                    f"failure_rate={summary['failure_rate']:.3f}",
                    f"retry_rate={summary['retry_rate']:.3f}",
                    f"cost_usd={summary['estimated_haiku_cost_usd']:.6f}",
                ]
            )
        )


def _haiku_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000 * HAIKU_INPUT_PER_MILLION) + (
        output_tokens / 1_000_000 * HAIKU_OUTPUT_PER_MILLION
    )


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


if __name__ == "__main__":
    main()
