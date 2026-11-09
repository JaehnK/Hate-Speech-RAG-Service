import httpx
import pytest

from app.analysis.executor import _classify
from app.analysis.jev_client import JEV_ENDPOINT, JevClient, JevError, JevScore
from app.analysis.jev_gate import JEV_FILTERED_STATUS, JevGatedClassifier
from app.analysis.models import AnalysisItem
from app.analysis.retry import RetryPolicy
from app.core.config import Settings
from app.worker_main import _build_jev_client, _maybe_gate
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


# --- service gate -------------------------------------------------------------


class FakeJev:
    def __init__(self, p_hate=None, error=None):
        self.p_hate, self.error, self.calls, self.closed = p_hate, error, 0, False

    def score(self, _text):
        self.calls += 1
        if self.error:
            raise self.error
        return JevScore(p_hate=self.p_hate, model="jev-1.14.0", input_tokens=300, output_tokens=20)

    def close(self):
        self.closed = True


class FakeRag:
    invalid_provider = "anthropic"

    def __init__(self):
        self.calls, self.closed = 0, False

    def classify_text(self, _text, _source_type):
        self.calls += 1
        return "rag-result"

    def close(self):
        self.closed = True


def test_gate_skips_rag_below_threshold_and_marks_result() -> None:
    rag = FakeRag()
    gate = JevGatedClassifier(rag, FakeJev(p_hate=0.03), threshold=0.07)

    result = gate.classify_text("영상 잘 봤어요", "comment")

    assert rag.calls == 0
    assert result.payload["is_hate_speech"] is False
    assert result.payload["jev_p_hate"] == 0.03
    assert result.rag_context_status == JEV_FILTERED_STATUS
    assert result.model == "jev-1.14.0"
    assert result.usage == {}


def test_gate_sends_threshold_and_above_to_rag() -> None:
    rag = FakeRag()
    gate = JevGatedClassifier(rag, FakeJev(p_hate=0.07), threshold=0.07)

    assert gate.classify_text("text", "comment") == "rag-result"
    assert rag.calls == 1


def test_gate_falls_back_to_rag_when_jev_fails() -> None:
    rag = FakeRag()
    gate = JevGatedClassifier(rag, FakeJev(error=JevError("down", status_code=503)))

    assert gate.classify_text("text", "comment") == "rag-result"


def test_gate_forwards_worker_attributes_and_closes_both() -> None:
    rag, jev = FakeRag(), FakeJev(p_hate=0.5)
    gate = JevGatedClassifier(rag, jev)

    assert gate.invalid_provider == "anthropic"
    gate.close()
    assert rag.closed and jev.closed


def test_filtered_result_flows_through_executor() -> None:
    gate = JevGatedClassifier(FakeRag(), FakeJev(p_hate=0.01))
    item = AnalysisItem(source_id="c1", text="좋은 영상", source_type="comment")

    outcome = _classify(gate, item)

    assert outcome.status == "succeeded"
    assert outcome.result_values["rag_context_status"] == JEV_FILTERED_STATUS
    assert outcome.result_values["is_hate_speech"] is False
    assert "Jev" in outcome.result_values["reasoning"]


def test_settings_require_key_when_prefilter_enabled() -> None:
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        Settings(_env_file=None, jev_prefilter_enabled=True, typesafe_api_key=None)
    assert Settings(_env_file=None).jev_prefilter_enabled is False


def test_worker_wraps_classifier_only_when_enabled() -> None:
    off = Settings(_env_file=None)
    assert _build_jev_client(off) is None
    assert _maybe_gate(None, off, "classifier") == "classifier"

    on = Settings(_env_file=None, jev_prefilter_enabled=True, typesafe_api_key="k", jev_threshold=0.05)
    client = _build_jev_client(on)
    gated = _maybe_gate(client, on, FakeRag())
    assert isinstance(gated, JevGatedClassifier)
    assert gated.threshold == 0.05
    assert client.model == "jev-1.14.0"
