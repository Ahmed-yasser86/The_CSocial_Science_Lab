"""Session-context router - the UI's active workspace/project/dataset state.

Endpoints:

* ``GET /session/context`` - current selection (defaults to all unset);
* ``PUT /session/context`` - partial update: absent fields are left
  unchanged, explicit ``null`` clears the field. Unknown project/dataset/
  workspace ids surface as ``404``.

Setting ``active_workspace_id`` performs a full workspace activation (one
code path); the switch is refused with ``409`` while any collection job is
pending/running, because in-flight jobs write into their originating
workspace's database (plan §2.3 concurrency guard).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.domain.session_models import (
    SessionContext,
    SessionContextPatch,
)
from SocialScienceResearch.services.session_service import SessionContextService

router = APIRouter()


def _service(request: Request) -> SessionContextService:
    runtime = getattr(request.app.state, "workspace_runtime", None)
    workspaces = runtime.workspaces if runtime is not None else None
    return get_service(
        request,
        "session_context",
        lambda: SessionContextService(
            request.app.state.services["repos"],
            settings=request.app.state.settings,
            workspaces=workspaces,
        ),
    )


def _guard_workspace_switch(request: Request) -> None:
    """409 while jobs are pending/running (they pin their workspace's DB)."""
    runtime = getattr(request.app.state, "workspace_runtime", None)
    if runtime is None:
        return
    active = runtime.active_jobs()
    if active:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot switch workspace while "
                f"{len(active)} job(s) are pending/running"
            ),
        )


@router.get(
    "/session/context",
    tags=["session"],
    response_model=SessionContext,
)
def get_session_context(request: Request) -> SessionContext:
    """Return the active workspace + project/dataset selection."""
    return _service(request).load()


@router.put(
    "/session/context",
    tags=["session"],
    response_model=SessionContext,
)
def update_session_context(body: SessionContextPatch, request: Request) -> SessionContext:
    """Update the active workspace/project/dataset selection.

    Absent fields stay unchanged; explicit ``null`` clears a field.
    """
    if "active_workspace_id" in body.model_fields_set:
        _guard_workspace_switch(request)
    try:
        return _service(request).update(body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from None
