import httpx
import pytest

from app.analysis.jev_client import JEV_ENDPOINT, JevClient, JevError
from app.analysis.retry import RetryPolicy
from experiments.simulate_jev_cascade import cascade_rows, choose_threshold, paired_differences


def _client(handler, attempts=3):
    return JevClient(
        "test-key",
        retry_policy=RetryPolicy(max_attempts=attempts, sleep=lambda _: None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_jev_client_parses_noul_score() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == JEV_ENDPOINT
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {"is_hate": {"type": "noul", "noul": 0.03}},
                "usage": {"input_tokens": 300, "output_tokens": 22},
            },
        )

    score = _client(handler).score("안녕하세요")

    assert score.p_hate == 0.03
    assert score.model == "jev-1.14.0"
    assert score.input_tokens == 300


def test_jev_client_retries_rate_limit_then_fails_on_auth_error() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429 if len(calls) == 1 else 401)

    with pytest.raises(JevError) as error:
        _client(handler).score("text")

    assert error.value.status_code == 401
    assert len(calls) == 2


def test_jev_client_requires_key() -> None:
    with pytest.raises(ValueError):
        JevClient("")


def test_choose_threshold_stops_before_leakage_budget() -> None:
    gold = {f"h{i}": {"is_hate_speech": True} for i in range(100)}
    gold |= {f"n{i}": {"is_hate_speech": False} for i in range(100)}
    scores = {f"h{i}": 0.9 for i in range(100)} | {f"n{i}": 0.02 for i in range(100)}
    scores |= {"h0": 0.05, "h1": 0.08, "h2": 0.08}

    tuned = choose_threshold(scores, gold, max_leakage=0.02)

    # t=0.06..0.08 filters only h0 (1%); t=0.09 also filters h1, h2 (3%).
    assert tuned["threshold"] == 0.08
    assert tuned["leakage"] == 0.01


def _row(item_id, hate, variant="three_vector_rag"):
    return {
        "item_id": item_id,
        "variant": variant,
        "status": "succeeded",
        "repeat_index": 0,
        "payload": {"is_hate_speech": hate, "categories": ["gender"] if hate else ["unclassified"]},
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def test_cascade_overrides_only_filtered_items() -> None:
    rows = [_row("a", True), _row("b", True), _row("c", False, variant="haiku_only")]

    cascaded = cascade_rows(rows, {"a": 0.01, "b": 0.5}, threshold=0.07)

    assert [row["item_id"] for row in cascaded] == ["a", "b"]
    assert {row["variant"] for row in cascaded} == {"jev_cascade_0.07"}
    assert cascaded[0]["payload"]["is_hate_speech"] is False
    assert cascaded[0]["jev_filtered"] is True
    assert cascaded[1]["payload"]["is_hate_speech"] is True


def test_paired_differences_measures_lost_true_positive() -> None:
    gold = {
        "a": {"is_hate_speech": True, "categories": ["gender"]},
        "b": {"is_hate_speech": True, "categories": ["gender"]},
        "c": {"is_hate_speech": False, "categories": ["unclassified"]},
    }
    reference = [_row("a", True), _row("b", True), _row("c", False)]
    candidate = cascade_rows(reference, {"a": 0.01}, threshold=0.07)

    diff = paired_differences(reference, candidate, gold, samples=50)

    assert diff["binary_recall"]["diff"] == pytest.approx(-0.5)
    assert diff["binary_precision"]["diff"] == 0.0
