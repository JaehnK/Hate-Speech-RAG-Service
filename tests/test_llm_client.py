from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.analysis.errors import ApiKeyInvalidError, LlmRequestError
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


def test_anthropic_client_maps_authentication_failure_without_retry() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)

    class RejectedMessages(FakeMessages):
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            raise anthropic.AuthenticationError("rejected", response=response, body=None)

    fake_client = FakeAnthropicClient()
    fake_client.messages = RejectedMessages()
    client = AnthropicLlmClient(
        api_key=None,
        client=fake_client,
        retry_policy=RetryPolicy(max_attempts=3, sleep=lambda _delay: None),
    )

    with pytest.raises(ApiKeyInvalidError):
        client.complete("prompt")
    assert fake_client.messages.calls == 1


def test_anthropic_client_maps_exhausted_rate_limit_to_stable_error() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, headers={"Retry-After": "1"}, request=request)

    class LimitedMessages(FakeMessages):
        def create(self, **kwargs):
            raise anthropic.RateLimitError("limited", response=response, body=None)

    fake_client = FakeAnthropicClient()
    fake_client.messages = LimitedMessages()
    client = AnthropicLlmClient(
        api_key=None,
        client=fake_client,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(LlmRequestError, match="요청 한도") as captured:
        client.complete("prompt")
    assert captured.value.code == "LLM_RATE_LIMITED"


def test_anthropic_client_disables_hidden_sdk_retries() -> None:
    client = AnthropicLlmClient(api_key="test-key")
    try:
        assert client.client.max_retries == 0
    finally:
        client.close()


def test_anthropic_client_maps_low_credit_400_to_billing_error() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)

    class NoCreditMessages(FakeMessages):
        def create(self, **kwargs):
            raise anthropic.BadRequestError(
                "Your credit balance is too low to access the Anthropic API.", response=response, body=None
            )

    fake_client = FakeAnthropicClient()
    fake_client.messages = NoCreditMessages()
    client = AnthropicLlmClient(api_key=None, client=fake_client, retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(LlmRequestError) as error:
        client.complete("prompt")
    assert error.value.code == "LLM_BILLING_ERROR"


def test_adaptive_models_send_effort_instead_of_temperature() -> None:
    fake_client = FakeAnthropicClient()
    client = AnthropicLlmClient(api_key=None, model="claude-haiku-5-5", max_tokens=1200, client=fake_client)

    client.complete("prompt")

    kwargs = fake_client.messages.kwargs
    assert "temperature" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["max_tokens"] == 4096


def test_haiku_4_5_keeps_temperature_and_no_effort() -> None:
    fake_client = FakeAnthropicClient()
    client = AnthropicLlmClient(api_key=None, model="claude-haiku-4-5-20251001", client=fake_client)

    client.complete("prompt")

    assert fake_client.messages.kwargs["temperature"] == 0.0
    assert "output_config" not in fake_client.messages.kwargs


def test_anthropic_client_maps_usage_limit_400_to_billing_error() -> None:
    class LimitMessages(FakeMessages):
        def create(self, **kwargs):
            response = httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
            raise anthropic.BadRequestError(
                "You have reached your specified API usage limits.", response=response, body=None
            )

    client = AnthropicLlmClient(api_key=None, client=SimpleNamespace(messages=LimitMessages()))

    with pytest.raises(LlmRequestError) as error:
        client.complete("prompt")

    assert error.value.code == "LLM_BILLING_ERROR"


def test_cache_ordered_prompt_marks_shared_prefix_for_caching() -> None:
    from app.analysis.prompt_template import PROMPT_V081, PROMPT_V082, build_category_prompt

    fake_client = FakeAnthropicClient()
    client = AnthropicLlmClient(api_key=None, model="claude-haiku-5-5", max_tokens=100, temperature=0.0, client=fake_client)

    prompt = build_category_prompt("댓글", "comment", [], prompt_version=PROMPT_V082, video_title="제목")
    client.complete(prompt)
    blocks = fake_client.messages.kwargs["messages"][0]["content"]
    assert [block.get("cache_control") for block in blocks] == [{"type": "ephemeral"}, None]
    assert "".join(block["text"] for block in blocks) == prompt  # the model sees the same text
    assert "댓글" not in blocks[0]["text"] and "제목" not in blocks[0]["text"]
    assert blocks[0]["text"] == build_category_prompt("다른", "reply", [], prompt_version=PROMPT_V082).split("\n[input]\n")[0]

    client.complete(build_category_prompt("댓글", "comment", [], prompt_version=PROMPT_V081))
    assert isinstance(fake_client.messages.kwargs["messages"][0]["content"], str)
