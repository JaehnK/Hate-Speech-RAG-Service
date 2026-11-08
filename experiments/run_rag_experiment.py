from __future__ import annotations

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from app.analysis.embeddings import create_embedding_function
from app.analysis.llm_client import AnthropicLlmClient, LlmResponse
from app.analysis.observability import LangfuseConfig, build_observability_client
from app.analysis.rag_classifier import ClassificationError, RagClassifier
from app.core.config import load_settings
from experiments.io import ExperimentInput, append_jsonl, read_inputs, read_jsonl
from pathlib import Path
from queue import Queue
from experiments.variants import ExperimentVariant, get_variants


class DryRunLlmClient:
    model = "dry-run"

    def complete(self, prompt: str) -> LlmResponse:
        return LlmResponse(
            text=(
                '{"input_text": "dry-run", "is_hate_speech": false, '
                '"categories": ["unclassified"], "target_group": null, '
                '"hate_type": null, "reasoning": "드라이런 결과입니다.", '
                '"similar_cases_used": [], "definition_docs_used": []}'
            ),
            model=self.model,
            usage={"input_tokens": len(prompt.split()), "output_tokens": 24},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG classification experiment variants.")
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--output-path", default="experiments/outputs/rag_results.jsonl")
    parser.add_argument("--persist-directory", default=None)
    parser.add_argument("--variant", action="append", choices=list(get_variant_names()))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel classifier slots.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip (item, variant, repeat) rows that already succeeded in --output-path.",
    )
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    settings = load_settings()
    persist_directory = args.persist_directory or settings.chroma_persist_directory
    embedding_function = create_embedding_function(
        provider="hash" if args.dry_run else settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.upstage_embedding_base_url,
    )
    llm_client = DryRunLlmClient() if args.dry_run else _build_llm_client(settings)
    observability = build_observability_client(
        LangfuseConfig(
            enabled=settings.langfuse_enabled,
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            capture_io=settings.langfuse_capture_io,
        )
    )

    inputs = read_inputs(args.input_path, limit=args.limit)
    done = completed_keys(args.output_path) if args.resume else set()
    tasks = [
        (variant, repeat_index, item)
        for variant in get_variants(args.variant)
        for repeat_index in range(args.repeat)
        for item in inputs
        if (item.item_id, variant.name, repeat_index) not in done
    ]
    print(f"{len(tasks)} tasks to run ({len(done)} already succeeded)", flush=True)

    # Chroma clients race when created concurrently, so build every slot up front and
    # hand them out through a per-variant queue (one classifier per in-flight task).
    pools: dict[str, Queue[RagClassifier]] = {}
    for variant in get_variants(args.variant):
        pools[variant.name] = Queue()
        for _ in range(args.concurrency):
            pools[variant.name].put(
                RagClassifier(
                    persist_directory=persist_directory,
                    llm_client=llm_client,
                    embedding_function=embedding_function,
                    observability=observability,
                    taxonomy_k=variant.taxonomy_k,
                    definition_k=variant.definition_k,
                    example_k=variant.example_k,
                )
            )
    write_lock = threading.Lock()

    def run(task: tuple[ExperimentVariant, int, ExperimentInput]) -> dict[str, Any]:
        variant, repeat_index, item = task
        classifier = pools[variant.name].get()
        try:
            row = _run_item(classifier, variant, item, repeat_index)
        finally:
            pools[variant.name].put(classifier)
        with write_lock:
            append_jsonl(args.output_path, [row])
        return row

    failed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run, task) for task in tasks]
        for count, future in enumerate(as_completed(futures), start=1):
            failed += future.result()["status"] != "succeeded"
            if count % 50 == 0 or count == len(futures):
                print(f"{count}/{len(futures)} done, {failed} failed", flush=True)
    observability.flush()
    print(f"wrote {len(tasks)} rows to {args.output_path}")


def completed_keys(path: Path | str) -> set[tuple[str, str, int]]:
    if not Path(path).exists():
        return set()
    return {
        (str(row["item_id"]), str(row["variant"]), int(row.get("repeat_index", 0)))
        for row in read_jsonl(path)
        if row.get("status") == "succeeded"
    }


def get_variant_names() -> list[str]:
    from experiments.variants import ALIASES, VARIANTS

    return [*VARIANTS, *ALIASES]


def _build_llm_client(settings):
    if settings.llm_provider != "anthropic":
        raise ValueError(f"unsupported LLM provider: {settings.llm_provider}")
    return AnthropicLlmClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )


def _run_item(
    classifier: RagClassifier,
    variant: ExperimentVariant,
    item: ExperimentInput,
    repeat_index: int = 0,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    try:
        result = classifier.classify_text(item.text, item.source_type)  # type: ignore[arg-type]
        return {
            "item_id": item.item_id,
            "variant": variant.name,
            "repeat_index": repeat_index,
            "status": "succeeded",
            "source_type": item.source_type,
            "text_hash": _stable_hash(item.text),
            "payload": result.payload,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "usage": result.usage,
            "attempts": result.attempts,
            "error": None,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
    except ClassificationError as exc:
        return {
            "item_id": item.item_id,
            "variant": variant.name,
            "repeat_index": repeat_index,
            "status": "failed",
            "source_type": item.source_type,
            "text_hash": _stable_hash(item.text),
            "payload": None,
            "model": classifier.llm_client.model,
            "prompt_version": None,
            "usage": {},
            "attempts": 2,
            "error": str(exc),
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
