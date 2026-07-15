from __future__ import annotations

from collections.abc import Iterable
from contextlib import nullcontext
from hashlib import sha256
import math
import os
import re
from typing import Protocol
from threading import BoundedSemaphore

import httpx

from app.analysis.retry import RetryPolicy, parse_retry_after


DEFAULT_UPSTAGE_EMBEDDING_MODEL = "solar-embedding-1-large"
DEFAULT_UPSTAGE_EMBEDDING_BASE_URL = "https://api.upstage.ai/v1/solar/embeddings"


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        pass


class HashEmbeddingFunction:
    """Deterministic embedding for local Chroma smoke tests."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "hash-embedding-v0"

    @staticmethod
    def build_from_config(config: dict[str, int]) -> "HashEmbeddingFunction":
        return HashEmbeddingFunction(dimensions=int(config["dimensions"]))

    def get_config(self) -> dict[str, int]:
        return {"dimensions": self.dimensions}

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine"]

    def is_legacy(self) -> bool:
        return False

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embed_documents(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return [_embed_text(text, self.dimensions) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.embed_documents(input)


class UpstageEmbeddingClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = DEFAULT_UPSTAGE_EMBEDDING_BASE_URL,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
        gate: BoundedSemaphore | None = None,
        retry_policy: RetryPolicy | None = None,
        on_retry=None,
        should_stop=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.http_client = http_client or httpx.Client(timeout=timeout)
        self._owns_http_client = http_client is None
        self.gate = gate
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=1)
        self.on_retry = on_retry
        self.should_stop = should_stop

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("Upstage API key is required for embeddings.")

        return self.retry_policy.run(
            lambda: self._embed_once(texts, model),
            is_retryable=_retryable_http_error,
            retry_after=_http_retry_after,
            on_retry=self.on_retry,
            should_stop=self.should_stop,
        )

    def _embed_once(self, texts: list[str], model: str) -> list[list[float]]:
        with (self.gate if self.gate is not None else nullcontext()):
            response = self.http_client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "input": texts},
            )
        response.raise_for_status()
        payload = response.json()

        rows = sorted(payload["data"], key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in rows]

    def close(self) -> None:
        if self._owns_http_client:
            self.http_client.close()


class UpstageEmbeddingFunction:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL,
        base_url: str = DEFAULT_UPSTAGE_EMBEDDING_BASE_URL,
        client: EmbeddingClient | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.document_model = _upstage_model_for(model, "passage")
        self.query_model = _upstage_model_for(model, "query")
        self.client = client or UpstageEmbeddingClient(api_key=api_key, base_url=base_url)

    @staticmethod
    def name() -> str:
        return "upstage-embedding-v0"

    @staticmethod
    def build_from_config(config: dict[str, str]) -> "UpstageEmbeddingFunction":
        return UpstageEmbeddingFunction(
            api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("UPSTAGE_API_KEY"),
            model=config.get("model", DEFAULT_UPSTAGE_EMBEDDING_MODEL),
            base_url=config.get("base_url", DEFAULT_UPSTAGE_EMBEDDING_BASE_URL),
        )

    def get_config(self) -> dict[str, str]:
        return {"model": self.model, "base_url": self.base_url}

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine"]

    def is_legacy(self) -> bool:
        return False

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embed_documents(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self.client.embed(input, model=self.document_model)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.client.embed(input, model=self.query_model)

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            close()


def create_embedding_function(
    provider: str = "hash",
    model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_UPSTAGE_EMBEDDING_BASE_URL,
    timeout: float = 30.0,
    gate: BoundedSemaphore | None = None,
    retry_policy: RetryPolicy | None = None,
    on_retry=None,
    should_stop=None,
):
    if provider == "hash":
        return HashEmbeddingFunction()
    if provider == "upstage":
        return UpstageEmbeddingFunction(
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=UpstageEmbeddingClient(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                gate=gate,
                retry_policy=retry_policy,
                on_retry=on_retry,
                should_stop=should_stop,
            ),
        )
    raise ValueError(f"unsupported embedding provider: {provider}")


def _embed_text(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for term in _terms(text):
        digest = sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector

    return [value / norm for value in vector]


def _terms(text: str) -> Iterable[str]:
    for token in re.findall(r"[0-9a-zA-Z_]+|[가-힣]+", text.lower()):
        yield token
        for size in (2, 3):
            if len(token) < size:
                continue
            for index in range(len(token) - size + 1):
                yield token[index : index + size]


def _upstage_model_for(model: str, mode: str) -> str:
    if model.endswith("-query"):
        return f"{model[:-6]}-{mode}"
    if model.endswith("-passage"):
        return f"{model[:-8]}-{mode}"
    return f"{model}-{mode}"


def _retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 500, 502, 503, 504}


def _http_retry_after(exc: Exception) -> float | None:
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    return parse_retry_after(exc.response.headers.get("Retry-After"))
