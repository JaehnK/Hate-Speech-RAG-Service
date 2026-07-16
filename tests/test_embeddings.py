from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
from time import sleep

import httpx
import pytest

from app.analysis.embeddings import UpstageEmbeddingClient, UpstageEmbeddingFunction, create_embedding_function
from app.analysis.retry import RetryPolicy


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls = []
        self.close_calls = 0

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self.calls.append((texts, model))
        return [[float(len(text))] for text in texts]

    def close(self) -> None:
        self.close_calls += 1


def test_upstage_embedding_uses_passage_and_query_models() -> None:
    client = FakeEmbeddingClient()
    embedding = UpstageEmbeddingFunction(model="embedding", client=client)

    assert embedding.embed_documents(["문서"]) == [[2.0]]
    assert embedding.embed_query(["질문"]) == [[2.0]]
    assert client.calls == [
        (["문서"], "embedding-passage"),
        (["질문"], "embedding-query"),
    ]
    embedding.close()
    assert client.close_calls == 1


def test_embedding_factory_supports_hash_and_upstage() -> None:
    assert create_embedding_function("hash").name() == "hash-embedding-v0"
    assert create_embedding_function("upstage", api_key="key").name() == "upstage-embedding-v0"


def test_upstage_embedding_normalizes_suffixed_model_names() -> None:
    client = FakeEmbeddingClient()
    embedding = UpstageEmbeddingFunction(model="embedding-query", client=client)

    embedding.embed_documents(["문서"])
    embedding.embed_query(["질문"])

    assert client.calls == [
        (["문서"], "embedding-passage"),
        (["질문"], "embedding-query"),
    ]


def test_upstage_embedding_retries_429_with_retry_after() -> None:
    request = httpx.Request("POST", "https://example.test/embeddings")
    responses = [
        httpx.Response(429, headers={"Retry-After": "2"}, request=request),
        httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]}, request=request),
    ]

    class FakeHttpClient:
        def post(self, *_args, **_kwargs):
            return responses.pop(0)

    delays = []
    client = UpstageEmbeddingClient(
        "key",
        http_client=FakeHttpClient(),
        retry_policy=RetryPolicy(max_attempts=3, sleep=delays.append),
    )

    assert client.embed(["query"], "model") == [[0.1]]
    assert delays == [2.0]
    assert responses == []


def test_upstage_embedding_does_not_retry_authentication_error() -> None:
    request = httpx.Request("POST", "https://example.test/embeddings")

    class FakeHttpClient:
        calls = 0

        def post(self, *_args, **_kwargs):
            self.calls += 1
            return httpx.Response(401, request=request)

    http_client = FakeHttpClient()
    client = UpstageEmbeddingClient(
        "key",
        http_client=http_client,
        retry_policy=RetryPolicy(max_attempts=3, sleep=lambda _delay: None),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.embed(["query"], "model")
    assert http_client.calls == 1


def test_upstage_embedding_gate_limits_concurrent_requests() -> None:
    state = {"active": 0, "max_active": 0}
    lock = Lock()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1]}]}

    class FakeHttpClient:
        def post(self, *_args, **_kwargs):
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            sleep(0.01)
            with lock:
                state["active"] -= 1
            return FakeResponse()

    client = UpstageEmbeddingClient("key", http_client=FakeHttpClient(), gate=BoundedSemaphore(1))
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(lambda _index: client.embed(["query"], "model"), range(3)))

    assert state["max_active"] == 1
