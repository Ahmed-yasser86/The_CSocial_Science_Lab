"""Budget controller observability endpoints.

Exposes the detailed, per-event budget log and the current controller state so
the user can audit and explain exactly what the crawler did and why (the
research-project observability requirement). This is a read-only view over the
process-global ``BudgetController`` stored on ``app.state.budget_controller``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/budget/events", tags=["budget"])
def get_budget_events(
    request: Request,
    limit: int = 500,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Return the most recent budget events.

    One entry per admission decision / rate-limit signal, newest last. Use
    ``run_id`` to scope to a single run. This is the raw detail stream - not an
    aggregate - so every individual request decision is visible.
    """
    controller = request.app.state.budget_controller
    return {
        "events": controller.events(limit=limit, run_id=run_id),
        "min_interval": controller.min_interval,
        "max_ytdl_contexts": controller.max_ytdl_contexts,
    }


@router.get("/budget/state", tags=["budget"])
def get_budget_state(request: Request) -> dict[str, Any]:
    """Return the controller's live counters (admits, 429 count, waited total)."""
    controller = request.app.state.budget_controller
    return controller.state()
