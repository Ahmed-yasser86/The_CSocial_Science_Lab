"""Session-context models for the UI workspace state (B8).

The session context is the researcher's *active* project/dataset selection,
persisted server-side so the UI restores it across reloads. The PUT body uses
``model_fields_set`` semantics: an absent field leaves the stored value
unchanged, while an explicit ``null`` clears it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

_REQUEST_CONFIG = ConfigDict(extra="forbid")
_RESPONSE_CONFIG = ConfigDict(extra="allow")


class SessionContext(BaseModel):
    """Active workspace + project/dataset selection plus last-update timestamp.

    ``active_workspace_id`` is stored OUTSIDE any per-workspace session file
    (a workspace cannot contain the pointer to itself): it lives in the root
    ``workspaces/active.json`` document managed by :class:`WorkspaceService`.
    """

    model_config = _RESPONSE_CONFIG

    active_workspace_id: str | None = None
    active_project_id: str | None = None
    active_dataset_id: str | None = None
    updated_at: datetime


class SessionContextPatch(BaseModel):
    """Body for ``PUT .../session/context`` (``extra="forbid"``).

    Only explicitly provided fields are applied; ``{"active_project_id": null}``
    clears that field without touching the other one. Setting
    ``active_workspace_id`` performs a full workspace activation (one code
    path with ``POST /workspaces/{id}/activate`` semantics).
    """

    model_config = _REQUEST_CONFIG

    active_workspace_id: str | None = None
    active_project_id: str | None = None
    active_dataset_id: str | None = None
