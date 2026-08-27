"""Priority-weighted Task Queue feeding the Global Budget Controller (Phase 5).

Per the pipeline design, all scraping work flows through one queue ordered by
priority (discovery > enrichment > recommendations > comments). The queue's
workers pull the highest-priority ready task, charge it to the shared Budget
Controller (so the bucket still paces the *aggregate* rate), then run it. Queue
state (queued / running / waiting, broken down by task type) is observable.

This is deliberately thin: it orders and gates work. It does NOT decide timing
that is the Budget Controller's job, nor session health (that is the Circuit
Breaker's job). A task that fails with a rate-limit error is surfaced to the
caller (and therefore to the budget's AIMD + the breaker) exactly as if it had
been called directly.
"""

from __future__ import annotations

import heapq
import threading
import time
from collections import defaultdict
from concurrent.futures import Future
from typing import Any, Callable

from SocialScienceResearch.concurrency.budget_controller import EventSink


class TaskPriority:
    """Lower number = higher priority. Mirrors the plan's weighting."""

    DISCOVERY = 0
    ENRICHMENT = 1
    RECOMMENDATIONS = 2
    COMMENTS = 3


# Fallback type when a task doesn't supply one.
_DEFAULT_TYPE = "other"


class PriorityTaskQueue:
    def __init__(
        self,
        budget,
        *,
        circuit_breaker: Any = None,
        max_workers: int = 4,
        emit: Callable[[dict], None] | None = None,
        sinks: list[EventSink] | None = None,
    ) -> None:
        self._budget = budget
        self._cb = circuit_breaker
        self._max_workers = max(1, int(max_workers))
        self._emit = emit
        self._sinks = list(sinks or [])
        self._heap: list[tuple[int, int, Future, Callable, str, Any, Any, str]] = []
        self._seq = 0
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._running = 0
        self._counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"queued": 0, "running": 0, "waiting": 0}
        )
        self._stop = False
        self._started = False
        self._workers: list[threading.Thread] = []

    # -- lifecycle -------------------------------------------------------
    def _ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop = False
        for _ in range(self._max_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._workers.append(t)

    def shutdown(self) -> None:
        with self._lock:
            self._stop = True
        with self._cv:
            self._cv.notify_all()

    # -- enqueue ---------------------------------------------------------
    def enqueue(
        self,
        *,
        operation: str,
        priority: int,
        func: Callable[[], Any],
        run_id: str | None = None,
        cost: float | None = None,
        type: str | None = None,
    ) -> Future:
        """Schedule ``func`` and return a Future for its result.

        ``func`` is expected to already be wrapped with the budgeted retry policy
        (``retry_policy_budgeted(..., budget_on_first=False)``) so that the queue's
        own ``acquire`` covers the first attempt and each retry re-charges the
        budget. The Circuit Breaker (if any) is consulted by the caller's wrapper.
        """
        self._ensure_started()
        ttype = type or operation or _DEFAULT_TYPE
        with self._lock:
            self._seq += 1
            future: Future = Future()
            item = (priority, self._seq, future, func, operation, run_id, cost, ttype)
            heapq.heappush(self._heap, item)
            self._counts[ttype]["queued"] += 1
        with self._cv:
            self._cv.notify()
        self._event("enqueue", ttype, operation)
        return future

    # -- worker ----------------------------------------------------------
    def _worker(self) -> None:
        while True:
            with self._lock:
                if self._stop:
                    return
                while not self._heap:
                    if self._stop:
                        return
                    self._cv.wait()
                priority, _seq, future, func, operation, run_id, cost, ttype = heapq.heappop(
                    self._heap
                )
                self._counts[ttype]["queued"] -= 1
                self._counts[ttype]["running"] += 1
                self._running += 1
            self._event("dispatch", ttype, operation)
            try:
                if future.cancelled():
                    with self._lock:
                        self._counts[ttype]["running"] -= 1
                        self._running -= 1
                    continue
                if self._budget is not None:
                    # cost=None -> controller applies the operation's weighted cost.
                    self._budget.acquire(operation, run_id=run_id, cost=cost)
                result = func()
                if not future.cancelled():
                    future.set_result(result)
            except BaseException as exc:  # noqa: BLE001 - propagate to caller
                if not future.cancelled():
                    future.set_exception(exc)
            finally:
                with self._lock:
                    self._counts[ttype]["running"] -= 1
                    self._running -= 1
                self._event("complete", ttype, operation)

    # -- observability ---------------------------------------------------
    def queue_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "queued_total": sum(c["queued"] for c in self._counts.values()),
                "by_type": {k: dict(v) for k, v in self._counts.items()},
            }

    def _event(self, action: str, ttype: str, operation: str | None) -> None:
        payload = {
            "ts": time.time(),
            "kind": "queue",
            "action": action,
            "type": ttype,
            "operation": operation,
        }
        if self._emit is not None:
            try:
                self._emit(payload)
            except Exception:  # noqa: BLE001
                pass
        for sink in self._sinks:
            try:
                sink.emit(payload)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
