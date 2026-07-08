from app.analysis.embeddings import UpstageEmbeddingFunction, create_embedding_function


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls = []

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self.calls.append((texts, model))
        return [[float(len(text))] for text in texts]


def test_upstage_embedding_uses_passage_and_query_models() -> None:
    client = FakeEmbeddingClient()
    embedding = UpstageEmbeddingFunction(model="solar-embedding-1-large", client=client)

    assert embedding.embed_documents(["문서"]) == [[2.0]]
    assert embedding.embed_query(["질문"]) == [[2.0]]
    assert client.calls == [
        (["문서"], "solar-embedding-1-large-passage"),
        (["질문"], "solar-embedding-1-large-query"),
    ]


def test_embedding_factory_supports_hash_and_upstage() -> None:
    assert create_embedding_function("hash").name() == "hash-embedding-v0"
    assert create_embedding_function("upstage", api_key="key").name() == "upstage-embedding-v0"


def test_upstage_embedding_normalizes_suffixed_model_names() -> None:
    client = FakeEmbeddingClient()
    embedding = UpstageEmbeddingFunction(model="solar-embedding-1-large-query", client=client)

    embedding.embed_documents(["문서"])
    embedding.embed_query(["질문"])

    assert client.calls == [
        (["문서"], "solar-embedding-1-large-passage"),
        (["질문"], "solar-embedding-1-large-query"),
    ]
