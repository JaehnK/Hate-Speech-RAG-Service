from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Protocol


class ObservabilityClient(Protocol):
    def observation(
        self,
        name: str,
        as_type: str = "span",
        input_value: Any | None = None,
        output_value: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
    ):
        pass

    def flush(self) -> None:
        pass


class NoopObservabilityClient:
    @contextmanager
    def observation(
        self,
        name: str,
        as_type: str = "span",
        input_value: Any | None = None,
        output_value: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> Iterator[None]:
        yield None

    def flush(self) -> None:
        return None


@dataclass(frozen=True)
class LangfuseConfig:
    enabled: bool
    public_key: str | None
    secret_key: str | None
    host: str
    capture_io: bool = False


class LangfuseObservabilityClient:
    def __init__(self, config: LangfuseConfig) -> None:
        from langfuse import Langfuse

        self.capture_io = config.capture_io
        self.client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            host=config.host,
        )

    def observation(
        self,
        name: str,
        as_type: str = "span",
        input_value: Any | None = None,
        output_value: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
    ):
        return self.client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input_value if self.capture_io else None,
            output=output_value if self.capture_io else None,
            metadata=metadata,
            model=model,
        )

    def flush(self) -> None:
        self.client.flush()


def build_observability_client(config: LangfuseConfig) -> ObservabilityClient:
    if not config.enabled:
        return NoopObservabilityClient()
    if not config.public_key or not config.secret_key:
        return NoopObservabilityClient()
    return LangfuseObservabilityClient(config)
