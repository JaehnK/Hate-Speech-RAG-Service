import pytest

from app.analysis.retry import RetryCancelled, RetryPolicy, parse_retry_after


def test_retry_policy_uses_exponential_backoff() -> None:
    calls = 0
    delays = []

    def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError
        return "ok"

    policy = RetryPolicy(max_attempts=3, sleep=delays.append, random_value=lambda: 0)

    assert policy.run(operation, is_retryable=lambda exc: isinstance(exc, TimeoutError)) == "ok"
    assert calls == 3
    assert delays == [0.5, 1.0]


def test_retry_policy_honors_stop_before_next_attempt() -> None:
    stopped = False

    def operation():
        nonlocal stopped
        stopped = True
        raise TimeoutError

    policy = RetryPolicy(max_attempts=3, sleep=lambda _delay: None)

    with pytest.raises(RetryCancelled):
        policy.run(operation, is_retryable=lambda _exc: True, should_stop=lambda: stopped)


def test_parse_retry_after_seconds_and_invalid_value() -> None:
    assert parse_retry_after("1.5") == 1.5
    assert parse_retry_after("invalid") is None
