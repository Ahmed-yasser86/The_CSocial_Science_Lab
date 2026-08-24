"""Session-context router - the UI's active project/dataset selection.

Endpoints:

* ``GET /session/context`` - current selection (defaults to both unset);
* ``PUT /session/context`` - partial update: absent fields are left
  unchanged, explicit ``null`` clears the field. Unknown project/dataset ids
  surface as ``404``.
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
    return get_service(
        request,
        "session_context",
        lambda: SessionContextService(
            request.app.state.services["repos"],
            settings=request.app.state.settings,
        ),
    )


@router.get(
    "/session/context",
    tags=["session"],
    response_model=SessionContext,
)
def get_session_context(request: Request) -> SessionContext:
    """Return the active project/dataset selection for this data directory."""
    return _service(request).load()


@router.put(
    "/session/context",
    tags=["session"],
    response_model=SessionContext,
)
def update_session_context(body: SessionContextPatch, request: Request) -> SessionContext:
    """Update the active project/dataset selection.

    Absent fields stay unchanged; explicit ``null`` clears a field.
    """
    try:
        return _service(request).update(body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from None
