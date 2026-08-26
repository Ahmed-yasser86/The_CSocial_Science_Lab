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
import contextvars
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Protocol

from SocialScienceResearch.domain.job_models import CollectionJob
from SocialScienceResearch.utils.idgen import new_id, utcnow
from SocialScienceResearch.utils.logger import get_logger

logger = get_logger(__name__)

#: Id of the job executed on THIS thread (set by :meth:`JobManager._run`).
#: Collection bookkeeping reads it to stamp ``CollectionRun.job_id`` so every
#: run created under a job links back to the user intent (plan J1).
_job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "active_job_id", default=None
)
#: Tags of the active job, stamped onto every run it creates.
_job_tags_var: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "active_job_tags", default=[]
)


def current_job_id() -> str | None:
    """The job id of the worker thread calling this, or ``None`` outside a job."""
    return _job_id_var.get()


def current_job_tags() -> list[str]:
    """Tags of the worker thread's job (empty list outside a job)."""
    return _job_tags_var.get()

#: Signature of the progress callback handed to a worker function.
ProgressCallback = Callable[[], None] | None

#: Number of (timestamp, completed) samples kept for the rolling ETA window.
_ETA_SAMPLE_WINDOW = 20
#: Minimum wall-clock span between the oldest/newest ETA sample before an
#: estimate is trusted (below this the rate is noise).
_MIN_ETA_SPAN_SECONDS = 1.0


def _iso(value: Any) -> str | None:
    """Best-effort ISO-8601 string for a timestamp; tolerates odd inputs."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class _ProgressSink(Protocol):
    def __call__(
        self,
        *,
        stage: str = "",
        discovered: int = 0,
        succeeded: int = 0,
        failed: int = 0,
        message: str | None = None,
        edges_saved: int | None = None,
        current_target: dict[str, Any] | None = None,
        failures: list[dict[str, Any]] | None = None,
    ) -> None: ...


def _percent_complete(
    discovered: int, succeeded: int, failed: int
) -> float | None:
    """Honest completion percentage over known units, or ``None`` when unknown."""
    if discovered <= 0:
        return None
    done = succeeded + failed
    return round(min(100.0, max(0.0, done / discovered * 100.0)), 1)


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
    tags: list[str] = field(default_factory=list)
    last_progress_at: datetime | None = None
    """When the job last emitted progress (or started). Used by the stall watchdog."""

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe snapshot of the job's live state (no result/error bodies)."""
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status.value if isinstance(self.status, JobStatus) else str(self.status),
                "tags": list(self.tags),
            "created_at": _iso(self.created_at),
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "progress": self.progress,
            "message": self.message,
            "cancel_requested": self.cancel_requested,
        }


class JobManager:
    """Thread-backed job registry. Safe to call from any thread."""

    def __init__(
        self,
        max_workers: int = 2,
        max_run_seconds: int = 3600,
        max_stall_seconds: int = 900,
        *,
        store=None,
    ) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_workers = max_workers
        self._store = store
        """Optional ``JobRepository`` write-through target (plan J1).

        Only submit/running-start/milestone-free terminal transitions hit the
        store; per-second progress stays in-memory (R-J1: never hammer SQL on
        the hot progress path). A persistence failure is logged and never
        breaks the live job.
        """
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="collect"
        )
        self._max_run_seconds = max_run_seconds
        self._max_stall_seconds = max_stall_seconds
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._watchdog_stop = threading.Event()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            name="job-watchdog",
            daemon=True,
        )
        self._watchdog.start()

    def persist_job(self, job: Job) -> None:
        """Public write-through for external state changes (e.g. tagging)."""
        self._persist(job)

    def set_store(self, store) -> None:
        """Rebind the persistence store (workspace switch).

        The manager survives workspace switches by design (its queue must stay
        intact), but its write-through store belongs to the OLD workspace's
        database. Without a rebind, persisted-job lookups after a switch read
        the wrong DB and jobs 404 even though their rows exist.
        """
        with self._lock:
            self._store = store

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
    # Write-through persistence (plan J1)
    # ------------------------------------------------------------------
    def _persist(self, job: Job) -> None:
        """Mirror the job's current state into the store (best-effort)."""
        if self._store is None:
            return
        try:
            result = job.result
            if isinstance(result, dict):
                result_json = result
            else:
                result_json = (
                    {"result_type": type(result).__name__}
                    if result is not None
                    else {}
                )
            self._store.save_job(
                CollectionJob(
                    job_id=job.job_id,
                    kind=job.kind,
                    status=(
                        job.status.value
                        if isinstance(job.status, JobStatus)
                        else str(job.status)
                    ),
                    tags=list(job.tags),
                    result_json=result_json,
                    message=job.message,
                    error=job.error,
                    created_at=job.created_at if isinstance(job.created_at, datetime) else None,
                    started_at=job.started_at if isinstance(job.started_at, datetime) else None,
                    finished_at=job.finished_at if isinstance(job.finished_at, datetime) else None,
                    updated_at=utcnow(),
                )
            )
        except Exception as exc:  # noqa: BLE001 - persistence must never break a job
            logger.warning(
                "Failed to persist job %s state (%s): %s",
                job.job_id,
                job.status,
                exc,
            )

    def is_cancel_requested(self, job_id: str) -> bool:
        """True when cancellation was requested for a pending/running job.

        Long-running workers (e.g. the echo-chamber layer chain) poll this at
        unit boundaries so ``stop`` terminates between layers instead of only
        after the whole queue drains.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.cancel_requested)

    def persisted_jobs(
        self, kind: str | None = None, status: str | None = None
    ) -> list[Any]:
        """Persisted job rows (read-through for restart survival)."""
        if self._store is None:
            return []
        try:
            return self._store.list_jobs(kind=kind, status=status)
        except Exception as exc:  # noqa: BLE001 - degrade to memory-only view
            logger.warning("Failed to read persisted jobs: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Submission / lifecycle
    # ------------------------------------------------------------------
    def submit(
        self,
        fn: Callable[[_ProgressSink], Any],
        *,
        kind: str = "collect",
        job_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Job:
        """Schedule ``fn(progress_cb)`` on a worker thread; returns the job.

        ``job_id`` lets callers stamp dependent records BEFORE submission
        (e.g. the echo detection row), avoiding a post-submit save that could
        clobber the worker's earlier writes. ``tags`` labels the job (and, via
        the worker context, every run it spawns) for researchers to
        distinguish related work.
        """
        job = Job(job_id=job_id or new_id("job"), kind=kind, tags=list(tags or []))
        with self._lock:
            self._jobs[job.job_id] = job
        self._persist(job)
        self._executor.submit(self._run, job, fn)
        return job

    def _watchdog_loop(self) -> None:
        """Force-fail jobs that exceed the run-time or stall caps.

        Extraction workers block on yt-dlp which can stall indefinitely; a job
        that never returns would otherwise stay ``running`` forever. The
        watchdog sweeps periodically and fails any job over the hard cap, or
        any job that has reported *no progress* for ``max_stall_seconds`` (a
        sure sign of a blocked network/yt-dlp call). Failing it surfaces a
        terminal error to the UI instead of an indefinite "running" spinner.
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
                        self._persist(job)
                        continue
                    if self._max_stall_seconds and self._max_stall_seconds > 0:
                        last = job.last_progress_at or job.started_at
                        stalled = (now - last).total_seconds()
                        if stalled > self._max_stall_seconds:
                            job.status = JobStatus.FAILED
                            job.finished_at = now
                            job.error = (
                                f"job stalled after {int(stalled)}s with no progress "
                                "(likely a blocked network/yt-dlp call); auto-failed "
                                "by the watchdog so it cannot hang indefinitely"
                            )
                            job.message = "job stalled"
                            to_notify.append(job)
                            self._persist(job)

            for job in to_notify:
                self._notify(job)

    def _run(self, job: Job, fn: Callable[[_ProgressSink], Any]) -> None:
        job.status = JobStatus.RUNNING
        started = utcnow()
        job.started_at = started
        job.last_progress_at = started
        self._persist(job)
        self._notify(job)
        # Stamp this worker thread with the job id so ALL runs created inside
        # the worker (including per-video sub-runs spawned by layer crawls and
        # expansions) link back to the job (plan J1 linkage).
        token = _job_id_var.set(job.job_id)
        _job_tags_var.set(list(job.tags))
        try:
            result = fn(self._progress_cb(job))
            # Only transition if still RUNNING: a concurrent kill/stall action
            # may have already terminalised this job, and the orphaned worker
            # thread must not resurrect it.
            if job.status != JobStatus.RUNNING:
                return
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.message = "cancelled after the current unit of work finished"
            else:
                job.status = JobStatus.SUCCEEDED
                job.result = result
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            if job.status != JobStatus.RUNNING:
                return
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.message = "cancelled after the current unit of work finished"
            else:
                job.status = JobStatus.FAILED
                job.error = str(exc)
        finally:
            _job_id_var.reset(token)
            _job_tags_var.set([])
            job.finished_at = utcnow()
            self._persist(job)
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

    def recycle_executor(self) -> None:
        """Discard the worker pool and start a fresh one.

        Python cannot forcibly kill a worker thread, so a job blocked on a
        stalled yt-dlp/network call keeps running in the background even after
        we mark it terminal. Recreating the pool abandons those orphaned
        threads and immediately frees capacity for new work. In-flight tasks
        in the old pool are cancelled; already-running ones continue detached.
        """
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001 - best-effort; a fresh pool always starts
            pass
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="collect"
        )

    def kill_stuck(self) -> dict[str, Any]:
        """Force-terminate every non-terminal (pending/running) job.

        Marks pending jobs cancelled and running jobs failed (with a clear
        "killed by user" error), then recycles the worker pool so the orphaned
        threads holding worker slots are abandoned and the queue is unblocked.
        Returns how many jobs were killed and their ids.
        """
        killed: list[Job] = []
        with self._lock:
            for job in self._jobs.values():
                if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                    continue
                now = utcnow()
                if job.status == JobStatus.PENDING:
                    job.status = JobStatus.CANCELLED
                    job.finished_at = now
                    job.message = "cancelled by user (kill-all-stuck)"
                else:
                    job.status = JobStatus.FAILED
                    job.finished_at = now
                    job.error = "killed by user via 'Kill all stuck jobs'"
                    job.message = "killed by user"
                killed.append(job)
        for job in killed:
            self._persist(job)
            self._notify(job)
        if killed:
            self.recycle_executor()
        return {
            "killed": len(killed),
            "job_ids": [j.job_id for j in killed],
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(
                self._jobs.values(),
                key=lambda j: (
                    j.created_at.isoformat()
                    if isinstance(j.created_at, datetime)
                    else str(j.created_at)
                ),
                reverse=True,
            )

    def _progress_cb(self, job: Job) -> _ProgressSink:
        # Rolling-ETA state: (timestamp, completed) samples for the current
        # stage/total epoch. Reset whenever the stage or the discovered total
        # changes, because the denominator then means something different and
        # mixing epochs would fabricate a rate.
        eta_samples: list[tuple[float, int]] = []
        eta_epoch: tuple[str, int] | None = None

        def _report(
            *,
            stage: str = "",
            discovered: int = 0,
            succeeded: int = 0,
            failed: int = 0,
            message: str | None = None,
            edges_saved: int | None = None,
            current_target: dict[str, Any] | None = None,
            failures: list[dict[str, Any]] | None = None,
        ) -> None:
            nonlocal eta_epoch
            completed = succeeded + failed
            epoch = (stage, discovered)
            if epoch != eta_epoch:
                eta_samples.clear()
                eta_epoch = epoch
            now = time.monotonic()
            if not eta_samples or eta_samples[-1][1] != completed:
                # Only real completions advance the sample window, so the
                # rolling rate is computed from observed progress, never from
                # idle time.
                eta_samples.append((now, completed))
                del eta_samples[:-_ETA_SAMPLE_WINDOW]

            eta_seconds: float | None = None
            if discovered > 0 and len(eta_samples) >= 2:
                oldest_t, oldest_c = eta_samples[0]
                span = now - oldest_t
                progressed = completed - oldest_c
                if span >= _MIN_ETA_SPAN_SECONDS and progressed > 0:
                    remaining = max(0, discovered - completed)
                    if remaining == 0:
                        eta_seconds = 0.0
                    else:
                        eta_seconds = round(remaining / (progressed / span), 1)

            snapshot = {
                "stage": stage,
                "discovered": discovered,
                "succeeded": succeeded,
                "failed": failed,
                "message": message,
                "percent_complete": _percent_complete(discovered, succeeded, failed),
                "eta_seconds": eta_seconds,
                "eta_available": eta_seconds is not None,
                "edges_saved": edges_saved,
                "current_target": current_target,
                "failures": failures,
            }
            with self._lock:
                job.progress = snapshot
                job.message = message
                job.last_progress_at = utcnow()
            self._notify(job)

        return _report

    def shutdown(self) -> None:
        """Stop accepting work and release the worker pool (non-blocking)."""
        self._watchdog_stop.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
