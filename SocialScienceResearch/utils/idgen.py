"""Stable identifier and timestamp helpers.

IDs follow the project's ``run_<ts>_<uuid8>`` convention. All timestamps are
UTC and timezone-aware so that observations are comparable across runs and
machines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Generate a short, sortable, unique id like ``<prefix>_<ts>_<uuid8>``.

    The timestamp prefix makes ids roughly sortable by creation order; the
    uuid suffix guarantees uniqueness within the same second.
    """
    stamp = utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid4().hex[:8]}"


def new_run_id() -> str:
    """Generate a collection-run id (``run_<ts>_<uuid8>``)."""
    return new_id("run")
