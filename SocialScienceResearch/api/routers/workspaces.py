"""Workspace router - the outermost isolation container (plan §6.1).

Endpoints:

* ``GET  /workspaces``            - list with per-card volume stats;
* ``POST /workspaces``            - provision a NEW isolated workspace
  (fresh PostgreSQL database + schema + dedicated data dir); does NOT
  auto-activate (the UI activates right after via the session context);
* ``GET  /workspaces/{id}``       - one workspace;
* ``PATCH /workspaces/{id}``      - rename / edit topic (Legacy is renamable).

Activation/deactivation intentionally has NO endpoint of its own: it flows
through ``PUT /session/context`` with ``active_workspace_id`` so there is a
single code path for pointer updates. All endpoints operate exclusively on the
active workspace's database by construction (database-per-workspace routing).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.domain.workspace_models import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspacePayload,
)
from SocialScienceResearch.services.workspace_service import WorkspaceService

router = APIRouter()


def _service(request: Request) -> WorkspaceService:
    runtime = getattr(request.app.state, "workspace_runtime", None)
    if runtime is not None:
        return runtime.workspaces
    return get_service(request, "workspace_registry", lambda: WorkspaceService(
        request.app.state.settings
    ))


def _payload(request: Request, workspace) -> WorkspacePayload:
    service = _service(request)
    return WorkspacePayload.from_workspace(
        workspace,
        active=workspace.workspace_id == service.active_workspace_id(),
        stats=service.stats(workspace),
    )


@router.get("/workspaces", tags=["workspaces"], response_model=list[WorkspacePayload])
def list_workspaces(request: Request) -> list[WorkspacePayload]:
    """All registered workspaces with chooser-card stats (Legacy included)."""
    service = _service(request)
    active_id = service.active_workspace_id()
    return [
        WorkspacePayload.from_workspace(
            workspace,
            active=workspace.workspace_id == active_id,
            stats=service.stats(workspace),
        )
        for workspace in service.list_workspaces()
    ]


@router.post("/workspaces", tags=["workspaces"], response_model=WorkspacePayload)
def create_workspace(body: CreateWorkspaceRequest, request: Request) -> WorkspacePayload:
    """Provision a new fully isolated workspace (fresh DB + data dir)."""
    try:
        workspace = _service(request).create(
            body.name, research_topic=body.research_topic
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return _payload(request, workspace)


@router.get(
    "/workspaces/{workspace_id}",
    tags=["workspaces"],
    response_model=WorkspacePayload,
)
def get_workspace(workspace_id: str, request: Request) -> WorkspacePayload:
    """One workspace by id."""
    try:
        workspace = _service(request).get(workspace_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc.args[0])
        ) from None
    return _payload(request, workspace)


@router.patch(
    "/workspaces/{workspace_id}",
    tags=["workspaces"],
    response_model=WorkspacePayload,
)
def update_workspace(
    workspace_id: str, body: UpdateWorkspaceRequest, request: Request
) -> WorkspacePayload:
    """Rename / retitle a workspace. ``is_legacy`` is immutable; Legacy stays
    renamable like any other workspace."""
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise ValueError("Provide at least one field to update")
    try:
        workspace = _service(request).update(workspace_id, changes)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc.args[0])
        ) from None
    return _payload(request, workspace)
