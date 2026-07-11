from app.analysis.observability import LangfuseConfig, NoopObservabilityClient
from app.analysis.observability import build_observability_client


def test_observability_is_noop_when_disabled() -> None:
    client = build_observability_client(
        LangfuseConfig(
            enabled=False,
            public_key=None,
            secret_key=None,
            host="http://localhost:3000",
        )
    )

    assert isinstance(client, NoopObservabilityClient)
    with client.observation("test"):
        pass
    client.flush()


def test_observability_is_noop_when_keys_are_missing() -> None:
    client = build_observability_client(
        LangfuseConfig(
            enabled=True,
            public_key=None,
            secret_key=None,
            host="http://localhost:3000",
        )
    )

    assert isinstance(client, NoopObservabilityClient)
