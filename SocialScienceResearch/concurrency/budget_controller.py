"""Global Budget Controller (Phase 1): process-shared admission control.

Replaces the per-call ``_RateLimiter`` instances that previously lived inside
each scraping service. A single controller instance is shared by **all** services
and **all** jobs within a process (injected by ``build_services`` in production),
so the aggregate request rate is coordinated instead of being the sum of several
independent, uncoordinated gates.

Phase 1 keeps the controller at a *fixed* rate (adaptive AIMD arrives in Phase 4)
and treats every operation as unit cost (weighted costs arrive in Phase 3). The
interface is deliberately shaped so Phase 2 (retries through the controller) and
Phase 4 (AIMD) are drop-in changes. As of Phase 4 the controller also adapts its
rate via AIMD (additive increase under no 429s, multiplicative decrease on 429s).

Every admission decision and every rate-limit signal is emitted as a structured
``BudgetEvent`` to pluggable ``EventSink``s (INFO logs + in-memory ring buffer +
optional JSONL file). This is the research-project observability requirement:
per-event detail is surfaced in real time and is queryable, never aggregated away.
"""

from __future__ import annotations

import contextvars
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol, TYPE_CHECKING

from SocialScienceResearch.utils.logger import get_logger

if TYPE_CHECKING:
    from SocialScienceResearch.concurrency.circuit_breaker import CircuitBreakerRegistry

logger = get_logger(__name__)

# Operation label vocabulary (Phase 3 will map these to weights; Phase 1 charges
# all of them as unit cost so logs are already future-proof).
OPER_EXTRACT_CHANNEL = "extract_channel"
OPER_EXTRACT_VIDEO = "extract_video"
OPER_EXTRACT_VIDEO_COMMENTS = "extract_video_comments"
OPER_EXTRACT_TRANSCRIPT = "extract_transcript"
OPER_EXTRACT_RECOMMENDATIONS = "extract_recommendations"
OPER_RETRY = "retry"

# Phase 3: weighted cost per operation. These are *estimates of extraction /
# network pressure* (how many YouTube requests an operation tends to trigger),
# NOT exact HTTP counts. A heavier operation reserves proportionally more of the
# shared timeline: ``next_slot += min_interval * cost``. Override per-process via
# ``BudgetController(operation_costs=...)``.
DEFAULT_OPERATION_COSTS: dict[str, float] = {
    OPER_EXTRACT_CHANNEL: 4.0,          # discovery: multiple playlist tabs
    OPER_EXTRACT_VIDEO: 2.0,           # metadata only
    OPER_EXTRACT_VIDEO_COMMENTS: 6.0,  # full comment pagination
    OPER_EXTRACT_TRANSCRIPT: 1.5,      # caption track + single fetch
    OPER_EXTRACT_RECOMMENDATIONS: 1.5, # sidebar / innertube fallback
    OPER_RETRY: 1.0,                   # a retry is ~one attempt's worth
}

# Phase 4: AIMD adaptive rate. The controller starts at a conservative baseline
# ``min_interval`` and learns the highest safe rate over time:
#   * additive increase  - while healthy (no recent 429), shrink the interval by
#     ``aimd_increase_factor`` every ``aimd_increase_interval`` seconds (faster);
#   * multiplicative decrease - on the first 429 within a cooldown window, double
#     the interval (halve the budget) and block increases for ``aimd_cooldown``.
# Floor/ceiling bound the interval to ``baseline * aimd_floor_ratio`` (fastest) and
# ``baseline * aimd_ceiling_ratio`` (slowest). All values are constructor params so
# the learned behaviour stays configurable, never permanently hardcoded.
AIMD_INCREASE_INTERVAL = 60.0    # seconds between additive-increase checks
AIMD_INCREASE_FACTOR = 0.05      # interval shrinks 5% per healthy tick
AIMD_DECREASE_FACTOR = 2.0       # 429 -> interval doubles (budget halved)
AIMD_COOLDOWN = 300.0            # seconds increases are blocked after a decrease
AIMD_FLOOR_RATIO = 0.25          # fastest interval = baseline * this (4x faster)
AIMD_CEILING_RATIO = 8.0         # slowest interval = baseline * this (8x slower)

# Run-context for budget events. The service sets the active run id before
# calling the acquisition provider; the provider's budget hooks read it so that
# retries (and the first attempt) are attributed to the correct run without
# threading ``run_id`` through every provider method signature. Falls back to
# ``None`` for callers that don't set it (e.g. ad-hoc search).
_CURRENT_RUN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "budget_run_id", default=None
)


@contextmanager
def run_context(run_id: str | None) -> Iterator[None]:
    """Temporarily set the active run id for budget event attribution."""
    token = _CURRENT_RUN_ID.set(run_id)
    try:
        yield
    finally:
        _CURRENT_RUN_ID.reset(token)


def get_current_run_id() -> str | None:
    return _CURRENT_RUN_ID.get()


@dataclass
class BudgetEvent:
    """One observable decision/signal from the budget controller."""

    ts: float
    kind: str  # acquire | admit | wait | state_change | rate_limit | semaphore
    operation: str | None = None
    run_id: str | None = None
    cost: float = 0.0
    waited_seconds: float = 0.0
    budget_after: float = 0.0
    reason: str | None = None
    detail: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventSink(Protocol):
    """Pluggable destination for ``BudgetEvent``s."""

    def emit(self, event: BudgetEvent) -> None: ...


class LoggingSink:
    """Emits every event as a single INFO-level structured record.

    INFO (not DEBUG) so it lands in the normal console/file stream the user
    already watches, satisfying the "real-time, not buried in debug" requirement.
    """

    def emit(self, event: BudgetEvent) -> None:
        logger.info(
            "BUDGET[%s] op=%s run=%s cost=%.2f waited=%.2f budget=%.2f%s%s",
            event.kind,
            event.operation or "-",
            event.run_id or "-",
            event.cost,
            event.waited_seconds,
            event.budget_after,
            f" reason={event.reason}" if event.reason else "",
            f" detail={event.detail}" if event.detail else "",
        )


class RingBufferSink:
    """Thread-safe in-memory ring buffer, exposed via the query API."""

    def __init__(self, capacity: int = 2000) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        self._events: list[BudgetEvent] = []

    def emit(self, event: BudgetEvent) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._capacity:
                self._events = self._events[-self._capacity :]

    def snapshot(
        self, *, limit: int | None = None, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            evs = self._events
            if run_id is not None:
                evs = [e for e in evs if e.run_id == run_id]
            if limit is not None:
                evs = evs[-limit:]
            return [e.as_dict() for e in evs]


class JsonlFileSink:
    """Append-only JSONL audit log (best-effort; never breaks scraping)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def emit(self, event: BudgetEvent) -> None:
        try:
            with self._lock:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event.as_dict()) + "\n")
        except Exception:  # noqa: BLE001 - observability must never break scraping
            pass


class BudgetController:
    """Process-shared admission controller with a fixed minimum spacing.

    ``acquire`` blocks the calling thread until the controller admits one unit of
    work, charges it, emits an ``acquire`` event (including how long it waited),
    and returns the waited time. Thread-safe via a single lock.
    """

    def __init__(
        self,
        *,
        min_interval: float,
        max_ytdl_contexts: int = 4,
        event_sinks: list[EventSink] | None = None,
        jsonl_path: str | Path | None = None,
        operation_costs: dict[str, float] | None = None,
        aimd_increase_interval: float = AIMD_INCREASE_INTERVAL,
        aimd_increase_factor: float = AIMD_INCREASE_FACTOR,
        aimd_decrease_factor: float = AIMD_DECREASE_FACTOR,
        aimd_cooldown: float = AIMD_COOLDOWN,
        aimd_floor_ratio: float = AIMD_FLOOR_RATIO,
        aimd_ceiling_ratio: float = AIMD_CEILING_RATIO,
        circuit_breaker: "CircuitBreakerRegistry | None" = None,
    ) -> None:
        self._min_interval = float(min_interval)
        self._max_ytdl_contexts = int(max_ytdl_contexts)
        self._operation_costs = dict(operation_costs or DEFAULT_OPERATION_COSTS)
        self._circuit_breaker = circuit_breaker
        if self._circuit_breaker is not None:
            # Surface breaker state transitions through the same event stream.
            try:
                self._circuit_breaker._on_transition = self._cb_transition
            except Exception:  # noqa: BLE001
                pass
        self._aimd_increase_interval = float(aimd_increase_interval)
        self._aimd_increase_factor = float(aimd_increase_factor)
        self._aimd_decrease_factor = float(aimd_decrease_factor)
        self._aimd_cooldown = float(aimd_cooldown)
        self._aimd_floor_ratio = float(aimd_floor_ratio)
        self._aimd_ceiling_ratio = float(aimd_ceiling_ratio)
        # Baseline anchors the floor/ceiling bounds; AIMD only drifts `_min_interval`.
        self._baseline_interval = self._min_interval
        self._floor = self._baseline_interval * self._aimd_floor_ratio
        self._ceiling = self._baseline_interval * self._aimd_ceiling_ratio
        self._lock = threading.Lock()
        self._next_slot = 0.0
        # AIMD state. First 429 is allowed immediately; additive increase is
        # scheduled one interval out so fast tests (well under a minute) see no drift.
        self._next_ai_check = time.monotonic() + self._aimd_increase_interval
        self._last_decrease_at = -self._aimd_cooldown
        self._in_cooldown_until = 0.0
        # Always keep the ring buffer so the query API has something to read.
        self._ring = RingBufferSink()
        self._sinks: list[EventSink] = [self._ring]
        if event_sinks:
            self._sinks.extend(event_sinks)
        if jsonl_path is not None:
            self._sinks.append(JsonlFileSink(jsonl_path))
        # Guarantee at least one human-visible sink.
        if not any(isinstance(s, LoggingSink) for s in self._sinks):
            self._sinks.append(LoggingSink())
        self._admits = 0
        self._rate_limited = 0
        self._total_waited = 0.0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def set_min_interval(self, seconds: float) -> None:
        """Live-tune the spacing (wired to the UI speed presets).

        Also re-anchors the AIMD floor/ceiling to the new baseline so adaptive
        drift stays bounded around whatever the operator selected.
        """
        with self._lock:
            self._min_interval = max(0.0, float(seconds))
            self._baseline_interval = self._min_interval
            self._floor = self._baseline_interval * self._aimd_floor_ratio
            self._ceiling = self._baseline_interval * self._aimd_ceiling_ratio
        self._emit(
            "state_change",
            reason="min_interval_update",
            detail={"min_interval": self._min_interval},
        )

    @property
    def min_interval(self) -> float:
        with self._lock:
            return self._min_interval

    @property
    def max_ytdl_contexts(self) -> int:
        return self._max_ytdl_contexts

    def _resolve_cost(self, operation: str, cost: float | None) -> float:
        """Resolve the effective cost: explicit override else the operation's weight."""
        if cost is not None:
            return float(cost)
        return float(self._operation_costs.get(operation, 1.0))

    def _maybe_aimd_increase(self, now: float) -> None:
        """Additive-increase step (called from ``acquire`` under ``self._lock``).

        While healthy (no 429 within the cooldown window) shrink the interval by
        ``aimd_increase_factor`` every ``aimd_increase_interval`` seconds, down to
        the floor. This is the "increase" half of AIMD; the "decrease" half lives
        in ``on_rate_limited``.
        """
        if now < self._next_ai_check:
            return
        self._next_ai_check = now + self._aimd_increase_interval
        if now < self._in_cooldown_until:
            return  # a recent 429 blocked increases until cooldown expires
        new_interval = max(
            self._floor, self._min_interval * (1.0 - self._aimd_increase_factor)
        )
        if new_interval < self._min_interval:
            self._min_interval = new_interval
            self._emit(
                "state_change",
                reason="aimd_additive_increase",
                detail={"min_interval": self._min_interval},
            )

    # ------------------------------------------------------------------
    # Core admission
    # ------------------------------------------------------------------
    def acquire(
        self,
        operation: str,
        *,
        run_id: str | None = None,
        cost: float | None = None,
    ) -> float:
        """Block until the controller admits one `cost` unit of work.

        ``cost`` defaults to the operation's weighted cost (see
        ``DEFAULT_OPERATION_COSTS``); a heavier operation reserves proportionally
        more of the shared timeline: ``next_slot += min_interval * cost``.
        Returns seconds waited.
        """
        cost = self._resolve_cost(operation, cost)
        waited = 0.0
        if self._min_interval > 0:
            with self._lock:
                now = time.monotonic()
                self._maybe_aimd_increase(now)
                slot = max(self._next_slot, now)
                self._next_slot = slot + self._min_interval * cost
            waited = slot - now
            if waited > 0:
                time.sleep(waited)
        with self._lock:
            self._admits += 1
            self._total_waited += waited
            budget_after = self._next_slot
        self._emit(
            "acquire",
            operation=operation,
            run_id=run_id,
            cost=cost,
            waited_seconds=waited,
            budget_after=budget_after,
        )
        return waited

    def on_rate_limited(
        self,
        *,
        operation: str | None = None,
        run_id: str | None = None,
        session: Any = None,
        reason: str = "429/RateLimitError",
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Record a 429/RateLimitError and apply AIMD multiplicative-decrease.

        On the first 429 within a cooldown window the interval is doubled (the
        available budget is halved) and increases are blocked for ``aimd_cooldown``
        seconds, so we don't keep speeding up into a wall of 429s. Subsequent 429s
        inside the same window are still counted/observed but don't re-halve.

        The failure is also forwarded to the per-session Circuit Breaker (if any),
        which independently tracks session/proxy health and may OPEN that identity.
        """
        decreased = False
        with self._lock:
            self._rate_limited += 1
            now = time.monotonic()
            if now - self._last_decrease_at >= self._aimd_cooldown:
                new_interval = min(
                    self._ceiling, self._min_interval * self._aimd_decrease_factor
                )
                if new_interval > self._min_interval:
                    self._min_interval = new_interval
                    decreased = True
                self._last_decrease_at = now
                self._in_cooldown_until = now + self._aimd_cooldown
        if decreased:
            self._emit(
                "state_change",
                reason="aimd_multiplicative_decrease",
                detail={"min_interval": self._min_interval},
            )
        if self._circuit_breaker is not None:
            key = str(session) if session is not None else "default"
            self._circuit_breaker.record_failure(key, operation=operation)
        self._emit(
            "rate_limit",
            operation=operation,
            run_id=run_id,
            reason=reason,
            detail={"session": str(session), **(detail or {})},
        )

    def _cb_transition(self, key: str, old: Any, new: Any, detail: dict) -> None:
        """Forward a Circuit Breaker state transition into the budget event stream."""
        self._emit(
            "circuit_breaker",
            reason="state_change",
            detail={"key": key, "from": getattr(old, "value", old), "to": getattr(new, "value", new), **detail},
        )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    def _emit(
        self,
        kind: str,
        *,
        operation: str | None = None,
        run_id: str | None = None,
        cost: float = 0.0,
        waited_seconds: float = 0.0,
        budget_after: float = 0.0,
        reason: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        event = BudgetEvent(
            ts=time.time(),
            kind=kind,
            operation=operation,
            run_id=run_id,
            cost=cost,
            waited_seconds=waited_seconds,
            budget_after=budget_after,
            reason=reason,
            detail=detail,
        )
        for sink in self._sinks:
            sink.emit(event)

    def attach_sink(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    def emit_raw(self, event: dict[str, Any]) -> None:
        """Emit an already-shaped event dict through the normal sinks.

        Used by companion components (the priority queue, circuit breaker) that
        build their own event payloads but want them in the same observable
        stream as the budget events.
        """
        kind = str(event.get("kind", "event"))
        self._emit(kind, detail=event)

    def events(
        self, *, limit: int | None = None, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._ring.snapshot(limit=limit, run_id=run_id)

    def state(self) -> dict[str, Any]:
        with self._lock:
            cooldown_remaining = max(0.0, self._in_cooldown_until - time.monotonic())
            return {
                "min_interval": self._min_interval,
                "max_ytdl_contexts": self._max_ytdl_contexts,
                "admits": self._admits,
                "rate_limited": self._rate_limited,
                "total_waited_seconds": round(self._total_waited, 2),
                "aimd_floor": self._floor,
                "aimd_ceiling": self._ceiling,
                "in_cooldown": cooldown_remaining > 0,
                "cooldown_remaining_seconds": round(cooldown_remaining, 1),
                "circuit_breakers": (
                    self._circuit_breaker.state() if self._circuit_breaker else {}
                ),
            }
