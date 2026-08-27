"""Per-session / per-proxy Circuit Breaker (Phase 5, second half).

The Global Budget Controller governs *total load* on YouTube (aggregate rate).
The Circuit Breaker is a *separate* concern: it tracks the *health* of an
individual session/proxy identity. When a given session accumulates repeated
429s / rate-limit errors, it is marked UNHEALTHY (OPEN) for a cooldown so the
system stops hammering YouTube from that identity; after the cooldown it is
probed (HALF_OPEN) and restored to HEALTHY (CLOSED) on success.

This is intentionally decoupled from the budget: the budget decides *how fast*,
the breaker decides *whether a given identity is allowed to try at all*. Today
there is a single session identity (the configured proxy, or "default"), but the
registry is keyed so Phase 6 (multiple proxies) slots in without changes.

Every state transition is emitted as an observable event so the research project
can audit exactly which session was marked unhealthy, when, and why.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from SocialScienceResearch.concurrency.budget_controller import EventSink


class CircuitState(str, Enum):
    CLOSED = "closed"  # healthy
    OPEN = "open"  # unhealthy; requests blocked during cooldown
    HALF_OPEN = "half_open"  # cooldown elapsed; one probe allowed


# on_transition(key, old_state, new_state, detail)
TransitionHook = Callable[[str, "CircuitState", "CircuitState", dict], None]


@dataclass
class _Breaker:
    failure_threshold: int
    success_threshold: int
    cooldown: float
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    opened_at: float = 0.0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_at: float | None = None
    last_success_at: float | None = None


class CircuitBreakerRegistry:
    """Holds one :class:`_Breaker` per session/proxy key and emits transitions."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        success_threshold: int = 1,
        cooldown: float = 300.0,
        on_transition: TransitionHook | None = None,
        sinks: list[EventSink] | None = None,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._cooldown = cooldown
        self._on_transition = on_transition
        self._sinks = list(sinks or [])
        self._lock = threading.Lock()
        self._breakers: dict[str, _Breaker] = {}

    # -- internal -------------------------------------------------------
    def _get(self, key: str) -> _Breaker:
        b = self._breakers.get(key)
        if b is None:
            b = _Breaker(
                self._failure_threshold,
                self._success_threshold,
                self._cooldown,
            )
            self._breakers[key] = b
        return b

    def _transition(
        self, key: str, b: _Breaker, new: CircuitState, detail: dict | None
    ) -> None:
        old = b.state
        if old == new:
            return
        b.state = new
        if new == CircuitState.OPEN:
            b.opened_at = time.monotonic()
        detail = dict(detail or {})
        detail.update({"key": key, "from": old.value, "to": new.value})
        if self._on_transition is not None:
            self._on_transition(key, old, new, detail)
        event = {
            "ts": time.time(),
            "kind": "circuit_breaker",
            "key": key,
            "from": old.value,
            "to": new.value,
            "detail": detail,
        }
        for sink in self._sinks:
            try:
                sink.emit(event)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - observability must never break work
                pass

    # -- API -------------------------------------------------------------
    def allow_request(self, key: str) -> bool:
        """Return True if the given session may attempt a request now."""
        with self._lock:
            b = self._get(key)
            if b.state == CircuitState.OPEN:
                if time.monotonic() - b.opened_at >= b.cooldown:
                    self._transition(key, b, CircuitState.HALF_OPEN, {"reason": "cooldown_elapsed"})
                    return True
                return False
            return True

    def wait_until_allowed(self, key: str, poll: float = 0.5) -> None:
        """Block until the breaker allows a request (cooldown elapsed -> HALF_OPEN).

        This lets the provider treat an OPEN breaker as a *cooperative, bounded*
        backoff: it waits out the remaining cooldown once and then probes, instead
        of raising an error that tenacity would retry forever. The call returns as
        soon as the breaker is no longer OPEN (HALF_OPEN or CLOSED).
        """
        while True:
            with self._lock:
                b = self._get(key)
                if b.state != CircuitState.OPEN:
                    return
                remaining = b.cooldown - (time.monotonic() - b.opened_at)
            if remaining <= 0:
                # Cooldown elapsed; allow_request() will flip OPEN -> HALF_OPEN.
                if self.allow_request(key):
                    return
                continue
            time.sleep(min(poll, remaining))

    def record_failure(self, key: str, *, operation: str | None = None) -> None:
        with self._lock:
            b = self._get(key)
            b.total_failures += 1
            b.consecutive_successes = 0
            b.consecutive_failures += 1
            b.last_failure_at = time.monotonic()
            if b.state == CircuitState.CLOSED and b.consecutive_failures >= b.failure_threshold:
                self._transition(
                    key,
                    b,
                    CircuitState.OPEN,
                    {
                        "reason": "failure_threshold",
                        "operation": operation,
                        "consecutive_failures": b.consecutive_failures,
                    },
                )
            elif b.state == CircuitState.HALF_OPEN:
                self._transition(
                    key,
                    b,
                    CircuitState.OPEN,
                    {"reason": "failure_in_half_open", "operation": operation},
                )

    def record_success(self, key: str, *, operation: str | None = None) -> None:
        with self._lock:
            b = self._get(key)
            b.total_successes += 1
            b.consecutive_failures = 0
            b.consecutive_successes += 1
            b.last_success_at = time.monotonic()
            if b.state == CircuitState.HALF_OPEN and b.consecutive_successes >= b.success_threshold:
                self._transition(key, b, CircuitState.CLOSED, {"reason": "recovered", "operation": operation})

    def state(self, key: str | None = None) -> Any:
        with self._lock:
            if key is not None:
                b = self._breakers.get(key)
                return self._snapshot(key, b) if b is not None else None
            return {k: self._snapshot(k, b) for k, b in self._breakers.items()}

    def _snapshot(self, key: str, b: _Breaker) -> dict:
        return {
            "key": key,
            "state": b.state.value,
            "consecutive_failures": b.consecutive_failures,
            "consecutive_successes": b.consecutive_successes,
            "total_failures": b.total_failures,
            "total_successes": b.total_successes,
            "cooldown": b.cooldown,
            "opened_at": b.opened_at,
        }

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._breakers.clear()
            else:
                self._breakers.pop(key, None)
