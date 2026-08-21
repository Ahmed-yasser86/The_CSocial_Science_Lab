"""Result models returned by the collection workflows.

These are plain data holders describing what a collection run observed and
persisted, including per-entity failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import CollectionError


@dataclass
class CollectionResult:
    """Summary of a completed collection run."""

    run_id: str
    run_type: RunType
    status: CollectionStatus
    target_url: str
    target_id: str | None
    entities_discovered: int
    entities_created: int
    entities_existing: int
    entities_failed: int
    comments_collected: int
    errors: list[CollectionError] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataset_id: str | None = None

    @property
    def ok(self) -> bool:
        """True when the run completed without a hard failure.

        ``SUCCESS`` and ``PARTIAL`` both count as acceptable outcomes: a
        partial run is an observable, auditable result, not a silent loss.
        """
        return self.status in (CollectionStatus.SUCCESS, CollectionStatus.PARTIAL)
