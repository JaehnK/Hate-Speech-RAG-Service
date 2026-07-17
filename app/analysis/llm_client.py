from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext
from threading import BoundedSemaphore
from typing import Protocol

import anthropic

from app.analysis.errors import ApiKeyInvalidError
from app.analysis.retry import RetryPolicy, parse_retry_after


DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_SYSTEM_PROMPT = (
    "You are a Korean hate speech classification engine. "
    "Return only valid JSON that matches the requested schema."
)


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str
    usage: dict[str, int]


class LlmClient(Protocol):
    model: str

    def complete(self, prompt: str) -> LlmResponse:
        pass


class AnthropicLlmClient:
    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        max_tokens: int = 1200,
        temperature: float = 0.0,
        timeout: float = 30.0,
        client=None,
        gate: BoundedSemaphore | None = None,
        retry_policy: RetryPolicy | None = None,
        on_retry=None,
        should_stop=None,
    ) -> None:
        if client is None and not api_key:
            raise ValueError("Anthropic API key is required for LLM classification.")

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.gate = gate
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=1)
        self.on_retry = on_retry
        self.should_stop = should_stop

    def complete(self, prompt: str) -> LlmResponse:
        return self.retry_policy.run(
            lambda: self._complete_once(prompt),
            is_retryable=_retryable_anthropic_error,
            retry_after=_anthropic_retry_after,
            on_retry=self.on_retry,
            should_stop=self.should_stop,
        )

    def _complete_once(self, prompt: str) -> LlmResponse:
        try:
            with (self.gate if self.gate is not None else nullcontext()):
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=DEFAULT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
        except anthropic.AuthenticationError as exc:
            raise ApiKeyInvalidError("anthropic") from exc
        return LlmResponse(
            text=_message_text(message),
            model=self.model,
            usage=_message_usage(message),
        )

    def close(self) -> None:
        self.client.close()


def _message_text(message) -> str:
    texts = []
    for block in getattr(message, "content", []):
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
    return "".join(texts)


def _message_usage(message) -> dict[str, int]:
    usage = getattr(message, "usage", None)
    if usage is None:
        return {}

    result = {}
    for key in ("input_tokens", "output_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = int(value)
    return result


def _retryable_anthropic_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ),
    )


def _anthropic_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    return parse_retry_after(headers.get("Retry-After") if headers is not None else None)
