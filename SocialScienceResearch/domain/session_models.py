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
    """Active project/dataset selection plus its last-update timestamp."""

    model_config = _RESPONSE_CONFIG

    active_project_id: str | None = None
    active_dataset_id: str | None = None
    updated_at: datetime


class SessionContextPatch(BaseModel):
    """Body for ``PUT .../session/context`` (``extra="forbid"``).

    Only explicitly provided fields are applied; ``{"active_project_id": null}``
    clears that field without touching the other one.
    """

    model_config = _REQUEST_CONFIG

    active_project_id: str | None = None
    active_dataset_id: str | None = None
