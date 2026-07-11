from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
import math
import os
import re
from typing import Protocol

import httpx


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
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("Upstage API key is required for embeddings.")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()

        rows = sorted(payload["data"], key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in rows]


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


def create_embedding_function(
    provider: str = "hash",
    model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_UPSTAGE_EMBEDDING_BASE_URL,
):
    if provider == "hash":
        return HashEmbeddingFunction()
    if provider == "upstage":
        return UpstageEmbeddingFunction(api_key=api_key, model=model, base_url=base_url)
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
