"""Tests for the Phase 5 priority-weighted Task Queue (ordering + budget gating)."""

from __future__ import annotations

import threading
import time

from SocialScienceResearch.concurrency.priority_queue import (
    PriorityTaskQueue,
    TaskPriority,
)


class FakeBudget:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def acquire(self, operation, run_id=None, cost=None):
        with self._lock:
            self.calls.append(operation)
        time.sleep(0.01)  # force serialization so ordering is observable


def test_queue_runs_tasks_in_priority_order_with_single_worker():
    budget = FakeBudget()
    q = PriorityTaskQueue(budget, max_workers=1)
    order: list[str] = []
    # Enqueue out of order; discovery (0) should run first, comments (3) last.
    specs = [
        ("comments", TaskPriority.COMMENTS),
        ("recommendations", TaskPriority.RECOMMENDATIONS),
        ("enrichment", TaskPriority.ENRICHMENT),
        ("discovery", TaskPriority.DISCOVERY),
    ]
    futures = [
        q.enqueue(
            operation=name,
            priority=p,
            func=lambda n=name: order.append(n),
            type=name,
        )
        for name, p in specs
    ]
    for f in futures:
        f.result()
    assert order == ["discovery", "enrichment", "recommendations", "comments"]


def test_queue_returns_results_and_charges_budget_once_per_task():
    budget = FakeBudget()
    q = PriorityTaskQueue(budget, max_workers=2)

    def make(x):
        return lambda: x * 2

    futures = [q.enqueue(operation="op", priority=1, func=make(i)) for i in range(5)]
    results = sorted(f.result() for f in futures)
    assert results == [0, 2, 4, 6, 8]
    assert len(budget.calls) == 5  # one acquire per task


def test_queue_tracks_state_counts():
    budget = FakeBudget()
    q = PriorityTaskQueue(budget, max_workers=1)
    started = threading.Event()

    def slow():
        started.wait(2.0)

    # Enqueue one slow task; while it runs, queued_total should be 0 but running 1.
    f = q.enqueue(operation="op", priority=1, func=slow, type="video")
    # Give the worker time to pick it up.
    time.sleep(0.05)
    state = q.queue_state()
    assert state["running"] == 1
    assert state["by_type"]["video"]["running"] == 1
    started.set()
    f.result()
    final = q.queue_state()
    assert final["running"] == 0
    assert final["queued_total"] == 0


def test_queue_propagates_exceptions_to_caller():
    budget = FakeBudget()
    q = PriorityTaskQueue(budget, max_workers=1)

    def boom():
        raise ValueError("nope")

    f = q.enqueue(operation="op", priority=1, func=boom)
    try:
        f.result()
        assert False, "expected exception"
    except ValueError:
        pass
