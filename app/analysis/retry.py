from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import time
from typing import TypeVar


T = TypeVar("T")


class RetryCancelled(Exception):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_ratio: float = 0.2
    sleep: Callable[[float], None] = time.sleep
    random_value: Callable[[], float] = random.random

    def run(
        self,
        operation: Callable[[], T],
        *,
        is_retryable: Callable[[Exception], bool],
        retry_after: Callable[[Exception], float | None] | None = None,
        on_retry: Callable[[Exception, int, float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> T:
        for attempt in range(1, self.max_attempts + 1):
            if should_stop is not None and should_stop():
                raise RetryCancelled
            try:
                return operation()
            except Exception as exc:
                if attempt == self.max_attempts or not is_retryable(exc):
                    raise
                if should_stop is not None and should_stop():
                    raise RetryCancelled from exc
                delay = retry_after(exc) if retry_after is not None else None
                if delay is None:
                    base = min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)
                    delay = min(base + base * self.jitter_ratio * self.random_value(), self.max_delay_seconds)
                if on_retry is not None:
                    on_retry(exc, attempt, delay)
                self.sleep(delay)
        raise RuntimeError("retry loop exited unexpectedly")


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
