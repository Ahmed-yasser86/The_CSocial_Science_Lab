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
