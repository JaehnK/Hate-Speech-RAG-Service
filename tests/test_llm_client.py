from types import SimpleNamespace

import anthropic
import httpx

from app.analysis.llm_client import AnthropicLlmClient
from app.analysis.retry import RetryPolicy


class FakeMessages:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(text='{"ok": true}')],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


class FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def test_anthropic_client_uses_configured_haiku_model() -> None:
    fake_client = FakeAnthropicClient()
    client = AnthropicLlmClient(
        api_key=None,
        model="claude-haiku-4-5-20251001",
        max_tokens=321,
        temperature=0.1,
        client=fake_client,
    )

    response = client.complete("prompt")

    assert response.text == '{"ok": true}'
    assert response.model == "claude-haiku-4-5-20251001"
    assert response.usage == {"input_tokens": 10, "output_tokens": 5}
    assert fake_client.messages.kwargs["model"] == "claude-haiku-4-5-20251001"
    assert fake_client.messages.kwargs["max_tokens"] == 321
    assert fake_client.messages.kwargs["temperature"] == 0.1


def test_anthropic_client_retries_rate_limit_with_retry_after() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, headers={"Retry-After": "3"}, request=request)

    class RetryMessages(FakeMessages):
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise anthropic.RateLimitError("limited", response=response, body=None)
            return super().create(**kwargs)

    fake_client = FakeAnthropicClient()
    fake_client.messages = RetryMessages()
    delays = []
    retries = []
    client = AnthropicLlmClient(
        api_key=None,
        client=fake_client,
        retry_policy=RetryPolicy(max_attempts=3, sleep=delays.append),
        on_retry=lambda _exc, attempt, delay: retries.append((attempt, delay)),
    )

    assert client.complete("prompt").usage == {"input_tokens": 10, "output_tokens": 5}
    assert fake_client.messages.calls == 2
    assert delays == [3.0]
    assert retries == [(1, 3.0)]
