"""Unit tests for the acquisition retry policy and 429 classification."""

from __future__ import annotations

import pytest

from SocialScienceResearch.acquisition.errors import (
    NetworkError,
    RateLimitError,
    TranscriptUnsupportedError,
)
from SocialScienceResearch.acquisition.retry import retry_policy


def test_retry_succeeds_after_rate_limit_with_retry_after() -> None:
    calls = {"n": 0}

    @retry_policy(retries=5, backoff=0.01, max_wait=0.05)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("429", retry_after=0)
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_succeeds_after_network_error() -> None:
    calls = {"n": 0}

    @retry_policy(retries=4, backoff=0.01, max_wait=0.05)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise NetworkError("boom")
        return "ok"

    assert flaky() == "ok"


def test_non_retryable_propagates_immediately() -> None:
    @retry_policy(retries=5, backoff=0.01)
    def bad() -> None:
        raise TranscriptUnsupportedError("genuinely unavailable")

    with pytest.raises(TranscriptUnsupportedError):
        bad()
