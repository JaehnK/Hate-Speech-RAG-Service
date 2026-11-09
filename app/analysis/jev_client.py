"""TypeSafe Jev client used as a cheap pre-filter in front of the RAG classifier.

Jev answers a yes/no ("noul") question with a probability. The cascade only trusts it
in one direction: items scored as confidently *not* hateful skip the LLM. Everything
else, including every uncertain item, still goes through three-vector RAG.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.analysis.retry import RetryPolicy, parse_retry_after

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_QUESTION_VERSION = "jev-gate-v1"
# Deliberately broad: profanity and insults count as "yes" so that the filter only
# drops comments that are clearly benign.
JEV_QUESTION = (
    "Is this Korean online comment hate speech or offensive/abusive language "
    "(attacking or insulting a person or group, including profanity)?"
)
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class JevError(Exception):
    def __init__(self, message: str, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class JevScore:
    p_hate: float
    model: str
    input_tokens: int
    output_tokens: int


class JevClient:
    def __init__(
        self,
        api_key: str,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ValueError("TypeSafe API key is required")
        self._api_key = api_key
        self._retry = retry_policy or RetryPolicy(max_attempts=5, max_delay_seconds=30.0)
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def score(self, text: str) -> JevScore:
        return self._retry.run(
            lambda: self._score_once(text),
            is_retryable=lambda exc: isinstance(exc, httpx.TransportError)
            or (isinstance(exc, JevError) and exc.status_code in RETRYABLE_STATUS),
            retry_after=lambda exc: exc.retry_after if isinstance(exc, JevError) else None,
        )

    def _score_once(self, text: str) -> JevScore:
        response = self._client.post(
            JEV_ENDPOINT,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": JEV_MODEL,
                "state": text,
                "questions": {"is_hate": {"type": "noul", "instructions": JEV_QUESTION}},
            },
        )
        if response.status_code != 200:
            raise JevError(
                f"Jev request failed with HTTP {response.status_code}",
                status_code=response.status_code,
                retry_after=parse_retry_after(response.headers.get("retry-after")),
            )
        body = response.json()
        usage = body.get("usage") or {}
        return JevScore(
            p_hate=float(body["answers"]["is_hate"]["noul"]),
            model=str(body.get("model", JEV_MODEL)),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
