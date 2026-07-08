from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
import math
import re


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
