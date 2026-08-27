"""Integration tests: the provider consults the per-session Circuit Breaker and
routes work through the priority queue (Phase 5 second half)."""

from __future__ import annotations

import pytest

from SocialScienceResearch.acquisition.errors import RateLimitError
from SocialScienceResearch.acquisition.yt_dlp_adapter import YtDlpAcquisitionProvider
from SocialScienceResearch.config.settings import ScraperSettings
from SocialScienceResearch.concurrency.budget_controller import BudgetController
from SocialScienceResearch.concurrency.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitState,
)
from SocialScienceResearch.concurrency.priority_queue import PriorityTaskQueue


def _provider(retries=1, circuit_breaker=None, task_queue=None):
    settings = ScraperSettings(retries=retries, retry_backoff=0.0)
    ctrl = BudgetController(
        min_interval=0.0, max_ytdl_contexts=4, circuit_breaker=circuit_breaker
    )
    return YtDlpAcquisitionProvider(
        settings=settings,
        budget_controller=ctrl,
        circuit_breaker=circuit_breaker,
        task_queue=task_queue,
    )


def test_provider_records_success_on_healthy_session():
    cb = CircuitBreakerRegistry(failure_threshold=2, cooldown=100.0)
    provider = _provider(circuit_breaker=cb)
    provider._extract_video = lambda url, include_comments=None: {"id": "v1"}
    out = provider.extract_video("https://youtube.com/watch?v=v1")
    assert out == {"id": "v1"}
    assert cb.state("default")["state"] == CircuitState.CLOSED.value


def test_provider_circuit_breaker_opens_and_short_circuits():
    cb = CircuitBreakerRegistry(failure_threshold=2, cooldown=100.0)
    provider = _provider(circuit_breaker=cb)
    calls: list[str] = []

    def failing(url, include_comments=None):
        calls.append(url)
        raise RateLimitError("429")

    provider._extract_video = failing

    for _ in range(2):
        with pytest.raises(RateLimitError):
            provider.extract_video("https://youtube.com/watch?v=v1")
    # After 2 consecutive failures the breaker for this session is OPEN.
    assert cb.state("default")["state"] == CircuitState.OPEN.value
    # The next attempt is short-circuited by the breaker without hitting yt-dlp.
    with pytest.raises(RateLimitError):
        provider.extract_video("https://youtube.com/watch?v=v1")
    assert len(calls) == 2


def test_provider_routes_through_priority_queue():
    queue = PriorityTaskQueue(BudgetController(min_interval=0.0, max_ytdl_contexts=4), max_workers=2)
    provider = _provider(task_queue=queue)
    provider._extract_video = lambda url, include_comments=None: {"id": "v1"}
    out = provider.extract_video("https://youtube.com/watch?v=v1")
    assert out == {"id": "v1"}
    queue.shutdown()
