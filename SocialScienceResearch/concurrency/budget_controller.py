"""Global Budget Controller (Phase 1): process-shared admission control.

Replaces the per-call ``_RateLimiter`` instances that previously lived inside
each scraping service. A single controller instance is shared by **all** services
and **all** jobs within a process (injected by ``build_services`` in production),
so the aggregate request rate is coordinated instead of being the sum of several
independent, uncoordinated gates.

Phase 1 keeps the controller at a *fixed* rate (adaptive AIMD arrives in Phase 4)
and treats every operation as unit cost (weighted costs arrive in Phase 3). The
interface is deliberately shaped so Phase 2 (retries through the controller) and
Phase 4 (AIMD) are drop-in changes.

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
from typing import Any, Iterator, Protocol

from SocialScienceResearch.utils.logger import get_logger

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
    ) -> None:
        self._min_interval = float(min_interval)
        self._max_ytdl_contexts = int(max_ytdl_contexts)
        self._operation_costs = dict(operation_costs or DEFAULT_OPERATION_COSTS)
        self._lock = threading.Lock()
        self._next_slot = 0.0
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
        """Live-tune the spacing (wired to the UI speed presets)."""
        with self._lock:
            self._min_interval = max(0.0, float(seconds))
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
        """Record a 429/RateLimitError. Phase 1 = observability only; Phase 4
        will trigger the multiplicative-decrease here."""
        with self._lock:
            self._rate_limited += 1
        self._emit(
            "rate_limit",
            operation=operation,
            run_id=run_id,
            reason=reason,
            detail={"session": str(session), **(detail or {})},
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

    def events(
        self, *, limit: int | None = None, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._ring.snapshot(limit=limit, run_id=run_id)

    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "min_interval": self._min_interval,
                "max_ytdl_contexts": self._max_ytdl_contexts,
                "admits": self._admits,
                "rate_limited": self._rate_limited,
                "total_waited_seconds": round(self._total_waited, 2),
            }
