from types import SimpleNamespace

from app.analysis.llm_client import AnthropicLlmClient


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
