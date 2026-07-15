from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import anthropic


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
    ) -> None:
        if client is None and not api_key:
            raise ValueError("Anthropic API key is required for LLM classification.")

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def complete(self, prompt: str) -> LlmResponse:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
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
