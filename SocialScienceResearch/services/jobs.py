"""In-process asynchronous job registry for long-running collection work.

Collection runs are synchronous under the hood (yt-dlp extraction is
blocking), so each job runs in a dedicated worker thread and the registry
exposes async-friendly status, progress and cancellation semantics.

Cancellation is cooperative and honest: it is honoured before a job starts
and acknowledged once the current unit of work finishes (a job is never torn
down mid-extraction, because that could leave a run half-persisted).
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Protocol

from SocialScienceResearch.utils.idgen import new_id, utcnow

#: Signature of the progress callback handed to a worker function.
ProgressCallback = Callable[[], None] | None


class _ProgressSink(Protocol):
    def __call__(
        self,
        *,
        stage: str = "",
        discovered: int = 0,
        succeeded: int = 0,
        failed: int = 0,
        message: str | None = None,
    ) -> None: ...


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """One submitted collection job and its lifecycle state."""

    job_id: str
    kind: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    cancel_requested: bool = False
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe snapshot of the job's live state (no result/error bodies)."""
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
            "message": self.message,
            "cancel_requested": self.cancel_requested,
        }


class JobManager:
    """Thread-backed job registry. Safe to call from any thread."""

    def __init__(self, max_workers: int = 2, max_run_seconds: int = 3600) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="collect"
        )
        self._max_run_seconds = max_run_seconds
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._watchdog_stop = threading.Event()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            name="job-watchdog",
            daemon=True,
        )
        self._watchdog.start()

    # ------------------------------------------------------------------
    # Streaming (SSE) subscriptions
    # ------------------------------------------------------------------
    def subscribe(self, job_id: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        """Register an SSE subscriber for a job; returns its event queue.

        The queue receives JSON-serializable job snapshots (``Job.to_dict``)
        on every state/progress change. Safe to call from the event-loop
        thread only; worker threads push through ``loop.call_soon_threadsafe``.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers.setdefault(job_id, []).append((queue, loop))
        # Replay the current state immediately so a late subscriber catches up.
        job = self._jobs.get(job_id)
        if job is not None:
            loop.call_soon_threadsafe(queue.put_nowait, job.to_dict())
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """Drop a subscriber's queue (called when the SSE client disconnects)."""
        with self._lock:
            subs = self._subscribers.get(job_id)
            if subs:
                self._subscribers[job_id] = [
                    (q, _) for (q, _) in subs if q is not queue
                ]
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    def _notify(self, job: Job) -> None:
        """Push a snapshot to every subscriber of ``job``.

        Called from any thread; state mutations always happen under
        ``self._lock`` first, then subscribers are scheduled via
        ``call_soon_threadsafe`` so asyncio queues are only touched on the
        loop thread.
        """
        snapshot = job.to_dict()
        with self._lock:
            subs = list(self._subscribers.get(job.job_id, ()))
        for queue, loop in subs:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, snapshot)
            except RuntimeError:
                # Loop is shutting down; drop the dead subscriber.
                self.unsubscribe(job.job_id, queue)

    # ------------------------------------------------------------------
    # Submission / lifecycle
    # ------------------------------------------------------------------
    def submit(
        self, fn: Callable[[_ProgressSink], Any], *, kind: str = "collect"
    ) -> Job:
        """Schedule ``fn(progress_cb)`` on a worker thread; returns the job."""
        job = Job(job_id=new_id("job"), kind=kind)
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job, fn)
        return job

    def _watchdog_loop(self) -> None:
        """Force-fail jobs that exceed the run-time cap.

        Extraction workers block on yt-dlp which can stall indefinitely; a job
        that never returns would otherwise stay ``running`` forever. The
        watchdog sweeps periodically and fails any job over the cap so the UI
        always shows a terminal state.
        """
        while not self._watchdog_stop.wait(5):
            now = utcnow()
            to_notify: list[Job] = []
            with self._lock:
                for job in self._jobs.values():
                    if job.status != JobStatus.RUNNING or job.started_at is None:
                        continue
                    elapsed = (now - job.started_at).total_seconds()
                    if elapsed > self._max_run_seconds:
                        job.status = JobStatus.FAILED
                        job.finished_at = now
                        job.error = (
                            f"job timed out after {self._max_run_seconds}s of "
                            "execution (a network call stalled past the cap)"
                        )
                        job.message = "job timed out"
                        to_notify.append(job)

            for job in to_notify:
                self._notify(job)

    def _run(self, job: Job, fn: Callable[[_ProgressSink], Any]) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        self._notify(job)
        try:
            result = fn(self._progress_cb(job))
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.message = "cancelled after the current unit of work finished"
            else:
                job.status = JobStatus.SUCCEEDED
                job.result = result
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.message = "cancelled after the current unit of work finished"
            else:
                job.status = JobStatus.FAILED
                job.error = str(exc)
        finally:
            job.finished_at = utcnow()
            self._notify(job)

    def cancel(self, job_id: str) -> bool:
        """Request cancellation. True if the job could accept the request."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                job.cancel_requested = True
                accepted = True
            else:
                accepted = False
        if accepted:
            self._notify(job)
        return accepted

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _progress_cb(self, job: Job) -> _ProgressSink:
        def _report(
            *,
            stage: str = "",
            discovered: int = 0,
            succeeded: int = 0,
            failed: int = 0,
            message: str | None = None,
        ) -> None:
            snapshot = {
                "stage": stage,
                "discovered": discovered,
                "succeeded": succeeded,
                "failed": failed,
                "message": message,
            }
            with self._lock:
                job.progress = snapshot
                job.message = message
            self._notify(job)

        return _report

    def shutdown(self) -> None:
        """Stop accepting work and release the worker pool (non-blocking)."""
        self._watchdog_stop.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
