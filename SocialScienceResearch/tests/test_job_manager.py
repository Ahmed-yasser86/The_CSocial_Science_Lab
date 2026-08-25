"""Tests for the job manager's stuck-job handling.

Covers the two safeguards added for jobs that block on a stalled
yt-dlp/network call:

* ``kill_stuck``  — operator escape hatch that terminalises every
  pending/running job and recycles the worker pool so the queue is
  unblocked (cooperative cancel cannot stop a thread mid-extraction).
* stall watchdog — auto-fails a running job that reports no progress for
  ``max_stall_seconds`` (treated as a hung network call).
"""

from __future__ import annotations

import time

from SocialScienceResearch.services.jobs import JobManager, JobStatus


def test_kill_stuck_terminates_pending_and_running_and_unblocks_pool():
    mgr = JobManager(max_workers=1, max_stall_seconds=900)
    try:
        # A job that occupies the only worker slot "forever".
        running = mgr.submit(lambda cb: time.sleep(30), kind="test")
        # A second job that can never start while the slot is taken.
        pending = mgr.submit(lambda cb: None, kind="test")

        # Let the running job actually start.
        deadline = time.time() + 5
        while time.time() < deadline and mgr.get(running.job_id).status != JobStatus.RUNNING:
            time.sleep(0.05)
        assert mgr.get(running.job_id).status == JobStatus.RUNNING
        assert mgr.get(pending.job_id).status == JobStatus.PENDING

        result = mgr.kill_stuck()
        assert result["killed"] == 2
        assert set(result["job_ids"]) == {running.job_id, pending.job_id}

        # Running -> failed (killed by user); pending -> cancelled.
        assert mgr.get(running.job_id).status == JobStatus.FAILED
        assert "killed by user" in (mgr.get(running.job_id).error or "")
        assert mgr.get(pending.job_id).status == JobStatus.CANCELLED

        # The pool was recycled, so a brand-new job runs immediately.
        fresh = mgr.submit(lambda cb: "ok", kind="test")
        deadline = time.time() + 10
        while time.time() < deadline and mgr.get(fresh.job_id).status == JobStatus.PENDING:
            time.sleep(0.1)
        assert mgr.get(fresh.job_id).status == JobStatus.SUCCEEDED
    finally:
        mgr.shutdown()


def test_kill_stuck_is_a_noop_when_nothing_is_active():
    mgr = JobManager(max_workers=2, max_stall_seconds=900)
    try:
        result = mgr.kill_stuck()
        assert result["killed"] == 0
        assert result["job_ids"] == []
    finally:
        mgr.shutdown()


def test_stall_watchdog_fails_a_job_with_no_progress():
    # Very short stall window so the watchdog trips quickly.
    mgr = JobManager(max_workers=1, max_stall_seconds=1)
    try:
        stuck = mgr.submit(lambda cb: time.sleep(20), kind="test")
        # Let it start, then wait for the watchdog (5s sweep) to fail it.
        deadline = time.time() + 12
        while time.time() < deadline and mgr.get(stuck.job_id).status == JobStatus.RUNNING:
            time.sleep(0.2)
        assert mgr.get(stuck.job_id).status == JobStatus.FAILED
        assert "stalled" in (mgr.get(stuck.job_id).error or "").lower()
    finally:
        mgr.shutdown()


def test_killed_job_is_not_resurrected_by_orphaned_worker():
    mgr = JobManager(max_workers=1, max_stall_seconds=900)
    try:
        # This job will be killed while its worker thread is still sleeping.
        job = mgr.submit(lambda cb: time.sleep(30), kind="test")
        deadline = time.time() + 5
        while time.time() < deadline and mgr.get(job.job_id).status != JobStatus.RUNNING:
            time.sleep(0.05)
        mgr.kill_stuck()
        assert mgr.get(job.job_id).status == JobStatus.FAILED
        # Give the orphaned thread time to wake, finish and (wrongly) try to
        # mark the job succeeded — the guard in _run must prevent that.
        time.sleep(1)
        assert mgr.get(job.job_id).status == JobStatus.FAILED
    finally:
        mgr.shutdown()


# ----------------------------------------------------------------------
# Structured progress payload (percent + rolling ETA, observed-only)
# ----------------------------------------------------------------------
def test_progress_cb_computes_percent_and_eta():
    from SocialScienceResearch.services.jobs import Job

    mgr = JobManager(max_workers=1, max_stall_seconds=900)
    try:
        job = Job(job_id="job_progress", kind="layer")
        cb = mgr._progress_cb(job)

        cb(stage="layer/scrape", discovered=4)
        first = job.progress
        assert first["percent_complete"] == 0.0
        # A single sample is not a rate: ETA stays unknown, never fabricated.
        assert first["eta_seconds"] is None
        assert first["eta_available"] is False
        assert first["edges_saved"] is None
        assert first["current_target"] is None
        assert first["failures"] is None

        time.sleep(1.1)
        cb(
            stage="layer/scrape",
            discovered=4,
            succeeded=2,
            edges_saved=5,
            current_target={"video_id": "t3", "title": "T3", "url": None},
        )
        mid = job.progress
        assert mid["percent_complete"] == 50.0
        assert mid["edges_saved"] == 5
        assert mid["current_target"]["video_id"] == "t3"
        assert mid["eta_available"] is True
        assert 0 < mid["eta_seconds"] <= 2.5

        cb(stage="layer/scrape", discovered=4, succeeded=3, failed=1)
        done = job.progress
        assert done["percent_complete"] == 100.0
        assert done["eta_seconds"] == 0.0
        assert done["eta_available"] is True
    finally:
        mgr.shutdown()


def test_progress_cb_eta_resets_when_stage_or_total_changes():
    from SocialScienceResearch.services.jobs import Job

    mgr = JobManager(max_workers=1, max_stall_seconds=900)
    try:
        job = Job(job_id="job_epoch", kind="layer")
        cb = mgr._progress_cb(job)

        cb(stage="layer/scrape", discovered=10, succeeded=5)
        time.sleep(1.1)
        cb(stage="layer/scrape", discovered=10, succeeded=6)
        assert job.progress["eta_available"] is True

        # A stage change restarts the denominator: the old rate must not leak.
        cb(stage="layer/enrich", discovered=3, succeeded=0)
        reset = job.progress
        assert reset["percent_complete"] == 0.0
        assert reset["eta_available"] is False
    finally:
        mgr.shutdown()
