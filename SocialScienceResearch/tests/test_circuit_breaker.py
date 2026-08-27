"""Tests for the Phase 5 per-session Circuit Breaker + its integration with the
Global Budget Controller's rate-limit feedback."""

from __future__ import annotations

import time

from SocialScienceResearch.concurrency.budget_controller import BudgetController
from SocialScienceResearch.concurrency.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitState,
)


def test_breaker_starts_closed_and_allows():
    reg = CircuitBreakerRegistry(failure_threshold=3, cooldown=100.0)
    assert reg.state("s1") is None  # unknown until first record
    reg.record_success("s1")
    assert reg.state("s1")["state"] == CircuitState.CLOSED.value
    assert reg.allow_request("s1") is True


def test_breaker_opens_after_threshold_and_blocks_during_cooldown():
    reg = CircuitBreakerRegistry(failure_threshold=3, cooldown=100.0)
    for _ in range(3):
        reg.record_failure("s1")
    assert reg.state("s1")["state"] == CircuitState.OPEN.value
    # While the (long) cooldown is in effect, requests are blocked.
    assert reg.allow_request("s1") is False


def test_breaker_recovers_via_half_open_on_success():
    # cooldown=0 so an OPEN breaker moves to HALF_OPEN on the next probe.
    reg = CircuitBreakerRegistry(failure_threshold=3, cooldown=0.0)
    for _ in range(3):
        reg.record_failure("s1")
    assert reg.state("s1")["state"] == CircuitState.OPEN.value
    assert reg.allow_request("s1") is True  # transitions to HALF_OPEN
    assert reg.state("s1")["state"] == CircuitState.HALF_OPEN.value
    reg.record_success("s1")
    assert reg.state("s1")["state"] == CircuitState.CLOSED.value


def test_breaker_failure_in_half_open_reopens():
    reg = CircuitBreakerRegistry(failure_threshold=2, cooldown=0.0)
    reg.record_failure("s1")
    reg.record_failure("s1")  # opens
    assert reg.allow_request("s1") is True  # half-open
    reg.record_failure("s1")  # fails probe -> reopen
    assert reg.state("s1")["state"] == CircuitState.OPEN.value


def test_breaker_emits_transition_callback():
    transitions = []
    reg = CircuitBreakerRegistry(
        failure_threshold=2, cooldown=0.0, on_transition=lambda k, o, n, d: transitions.append((k, o.value, n.value))
    )
    reg.record_failure("s1")
    reg.record_failure("s1")
    reg.allow_request("s1")  # -> half_open
    reg.record_success("s1")  # -> closed
    kinds = [t[2] for t in transitions]
    assert CircuitState.OPEN.value in kinds
    assert CircuitState.HALF_OPEN.value in kinds
    assert CircuitState.CLOSED.value in kinds


def test_budget_controller_forwards_rate_limits_to_breaker():
    reg = CircuitBreakerRegistry(failure_threshold=3, cooldown=100.0)
    # aimd_ceiling_ratio=1.0 -> the AIMD ceiling equals the baseline, so a 429 means
    # the backoff is already saturated and the breaker SHOULD trip.
    ctrl = BudgetController(
        min_interval=0.5, max_ytdl_contexts=4, aimd_ceiling_ratio=1.0, circuit_breaker=reg
    )
    for _ in range(3):
        ctrl.on_rate_limited(operation="extract_video", session="sessA")
    assert reg.state("sessA")["state"] == CircuitState.OPEN.value
    # Surfaced through the controller's state() for the dashboard.
    assert ctrl.state()["circuit_breakers"]["sessA"]["state"] == CircuitState.OPEN.value
    # A different session stays healthy.
    assert ctrl.state()["circuit_breakers"].get("other") is None


def test_budget_does_not_feed_breaker_on_transient_throttle():
    # With a normal ceiling (baseline*ratio) the backoff is NOT saturated during a
    # routine throttle, so on_rate_limited must NOT trip the breaker (otherwise a
    # single throttle event would freeze the whole session for the cooldown).
    reg = CircuitBreakerRegistry(failure_threshold=1, cooldown=100.0)
    ctrl = BudgetController(
        min_interval=0.5, max_ytdl_contexts=4, aimd_ceiling_ratio=4.0, circuit_breaker=reg
    )
    for _ in range(3):
        ctrl.on_rate_limited(operation="extract_video", session="sessA")
    assert reg.state("sessA") is None


def test_budget_only_feeds_breaker_when_backoff_is_saturated():
    # Saturated: min_interval already at the AIMD ceiling => a 429 is a genuine,
    # persistent failure and SHOULD trip the breaker.
    reg = CircuitBreakerRegistry(failure_threshold=1, cooldown=10.0)
    ctrl = BudgetController(
        min_interval=1.0, max_ytdl_contexts=4, aimd_ceiling_ratio=1.0, circuit_breaker=reg
    )
    ctrl.on_rate_limited(operation="extract_transcript", session="s1")
    assert reg.state("s1")["state"] == CircuitState.OPEN.value

    # Not saturated: ceiling is 10x the current interval, so a transient 429 is just
    # normal throttle and must NOT trip the breaker (prevents freezing the session).
    reg2 = CircuitBreakerRegistry(failure_threshold=1, cooldown=10.0)
    ctrl2 = BudgetController(
        min_interval=1.0, max_ytdl_contexts=4, aimd_ceiling_ratio=10.0, circuit_breaker=reg2
    )
    ctrl2.on_rate_limited(operation="extract_transcript", session="s2")
    assert reg2.state("s2") is None


def test_wait_until_allowed_returns_immediately_when_closed():
    reg = CircuitBreakerRegistry(cooldown=10.0)
    reg.record_success("s1")
    t0 = time.monotonic()
    reg.wait_until_allowed("s1")
    assert time.monotonic() - t0 < 0.2


def test_wait_until_allowed_blocks_until_cooldown_then_allows():
    reg = CircuitBreakerRegistry(failure_threshold=1, cooldown=0.1)
    reg.record_failure("s1")  # -> OPEN
    assert reg.state("s1")["state"] == CircuitState.OPEN.value
    t0 = time.monotonic()
    reg.wait_until_allowed("s1")
    dt = time.monotonic() - t0
    assert 0.08 <= dt <= 1.0
    # After the wait the breaker is in HALF_OPEN and allows a probe.
    assert reg.state("s1")["state"] == CircuitState.HALF_OPEN.value
    assert reg.allow_request("s1") is True

