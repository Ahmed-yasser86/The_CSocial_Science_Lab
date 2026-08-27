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


def test_provider_circuit_breaker_opens_and_probes():
    cb = CircuitBreakerRegistry(failure_threshold=2, cooldown=0.05)
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
    # The next attempt no longer hard-rejects (which used to spin tenacity forever);
    # it waits out the (short) cooldown and probes, hitting yt-dlp again and still
    # failing. So the breaker still protects, but self-heals instead of freezing.
    with pytest.raises(RateLimitError):
        provider.extract_video("https://youtube.com/watch?v=v1")
    assert len(calls) == 3


def test_provider_routes_through_priority_queue():
    queue = PriorityTaskQueue(BudgetController(min_interval=0.0, max_ytdl_contexts=4), max_workers=2)
    provider = _provider(task_queue=queue)
    provider._extract_video = lambda url, include_comments=None: {"id": "v1"}
    out = provider.extract_video("https://youtube.com/watch?v=v1")
    assert out == {"id": "v1"}
    queue.shutdown()


def test_guarded_waits_out_open_breaker_then_probes():
    # An OPEN breaker must not hard-reject (which made tenacity spin forever);
    # _guarded should wait out the cooldown cooperatively and then probe.
    cb = CircuitBreakerRegistry(failure_threshold=1, cooldown=0.05)
    provider = _provider(circuit_breaker=cb)
    cb.record_failure("default")  # -> OPEN
    assert cb.state("default")["state"] == CircuitState.OPEN.value
    result = provider._guarded("extract_transcript", lambda: "probed")
    assert result == "probed"
    # Successful probe closes the breaker (HALF_OPEN -> CLOSED).
    assert cb.state("default")["state"] == CircuitState.CLOSED.value

