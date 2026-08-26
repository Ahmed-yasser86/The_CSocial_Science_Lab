"""Persisted-job domain model (jobs_runs_restructure_plan.md phase J1).

A :class:`CollectionJob` row mirrors the in-memory :class:`~services.jobs.Job`
lifecycle so completed jobs survive UI-session/server restarts and runs can be
linked back to the user intent that spawned them via
``CollectionRun.job_id``. Only milestones + terminal states are written
through (progress stays in-memory) to keep the single worker cheap.

Response/record models use ``extra="allow"``; this row is written by
``JobManager`` write-through hooks, never by hand.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_RESPONSE_CONFIG = ConfigDict(extra="allow")


class CollectionJob(BaseModel):
    """One persisted collection job (write-through mirror of a live Job)."""

    model_config = _RESPONSE_CONFIG

    job_id: str
    kind: str = "collect"
    status: str = "pending"
    tags: list[str] = Field(default_factory=list)
    params_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None
