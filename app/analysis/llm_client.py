from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext
from threading import BoundedSemaphore
from typing import Protocol

import anthropic

from app.analysis.errors import ApiKeyInvalidError, LlmRequestError
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
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
        self.gate = gate
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=1)
        self.on_retry = on_retry
        self.should_stop = should_stop

    def complete(self, prompt: str) -> LlmResponse:
        try:
            return self.retry_policy.run(
                lambda: self._complete_once(prompt),
                is_retryable=_retryable_anthropic_error,
                retry_after=_anthropic_retry_after,
                on_retry=self.on_retry,
                should_stop=self.should_stop,
            )
        except ApiKeyInvalidError:
            raise
        except anthropic.PermissionDeniedError as exc:
            raise ApiKeyInvalidError("anthropic") from exc
        except Exception as exc:
            mapped = _map_anthropic_error(exc)
            if mapped is None:
                raise
            raise mapped from exc

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


def _map_anthropic_error(exc: Exception) -> LlmRequestError | None:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(exc, anthropic.RateLimitError) or status_code == 429:
        return LlmRequestError("LLM_RATE_LIMITED", "Anthropic 요청 한도를 초과했습니다.")
    if isinstance(exc, anthropic.APITimeoutError) or status_code in {408, 504}:
        return LlmRequestError("LLM_TIMEOUT", "Anthropic 응답 시간이 초과되었습니다.")
    if isinstance(exc, anthropic.APIConnectionError):
        return LlmRequestError("LLM_CONNECTION_ERROR", "Anthropic 서비스에 연결할 수 없습니다.")
    if status_code == 402:
        return LlmRequestError("LLM_BILLING_ERROR", "Anthropic 결제 또는 크레딧 상태를 확인해주세요.")
    if status_code == 529:
        return LlmRequestError("LLM_OVERLOADED", "Anthropic 서비스가 일시적으로 혼잡합니다.")
    if status_code in {400, 413, 422}:
        return LlmRequestError("LLM_REQUEST_REJECTED", "Anthropic이 분류 요청을 거부했습니다.")
    if isinstance(exc, anthropic.InternalServerError) or (status_code is not None and status_code >= 500):
        return LlmRequestError("LLM_PROVIDER_ERROR", "Anthropic 서비스 내부 오류가 발생했습니다.")
    if isinstance(exc, anthropic.APIStatusError):
        return LlmRequestError("LLM_PROVIDER_REJECTED", "Anthropic 요청이 처리되지 않았습니다.")
    return None
