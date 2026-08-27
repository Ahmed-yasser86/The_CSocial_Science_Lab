"""Tests for the Phase 5 per-session Circuit Breaker + its integration with the
Global Budget Controller's rate-limit feedback."""

from __future__ import annotations

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
    ctrl = BudgetController(
        min_interval=0.5, max_ytdl_contexts=4, circuit_breaker=reg
    )
    for _ in range(3):
        ctrl.on_rate_limited(operation="extract_video", session="sessA")
    assert reg.state("sessA")["state"] == CircuitState.OPEN.value
    # Surfaced through the controller's state() for the dashboard.
    assert ctrl.state()["circuit_breakers"]["sessA"]["state"] == CircuitState.OPEN.value
    # A different session stays healthy.
    assert ctrl.state()["circuit_breakers"].get("other") is None
