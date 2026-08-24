"""Workspace models - fully isolated research environments (plan §0).

A workspace owns its own PostgreSQL database *and* its own ``data_dir``
(transcripts, session file, exports). The registry record (:class:`Workspace`)
is persisted in ``<root data_dir>/workspaces/registry.json``; API payloads
(:class:`WorkspacePayload`) never expose file paths or connection strings.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_REQUEST_CONFIG = ConfigDict(extra="forbid")
_RESPONSE_CONFIG = ConfigDict(extra="allow")


class Workspace(BaseModel):
    """One registry entry: identity + where its database and data dir live."""

    model_config = _RESPONSE_CONFIG

    workspace_id: str
    name: str
    database_url: str
    data_dir: str
    research_topic: str | None = None
    created_at: datetime
    last_opened_at: datetime
    is_legacy: bool = False


class WorkspaceStats(BaseModel):
    """Volume counters shown on a chooser card (observed, never estimated)."""

    model_config = _RESPONSE_CONFIG

    runs: int = 0
    videos: int = 0
    channels: int = 0
    comments: int = 0
    datasets: int = 0
    samples: int = 0
    projects: int = 0


class WorkspacePayload(BaseModel):
    """API projection of a workspace (no paths / connection strings)."""

    model_config = _RESPONSE_CONFIG

    workspace_id: str
    name: str
    research_topic: str | None = None
    is_legacy: bool = False
    active: bool = False
    created_at: datetime
    last_opened_at: datetime
    stats: WorkspaceStats = Field(default_factory=WorkspaceStats)

    @classmethod
    def from_workspace(
        cls,
        workspace: Workspace,
        *,
        active: bool,
        stats: WorkspaceStats,
    ) -> "WorkspacePayload":
        """Project a registry record WITHOUT its ``database_url``/``data_dir``."""
        return cls(
            workspace_id=workspace.workspace_id,
            name=workspace.name,
            research_topic=workspace.research_topic,
            is_legacy=workspace.is_legacy,
            active=active,
            created_at=workspace.created_at,
            last_opened_at=workspace.last_opened_at,
            stats=stats,
        )


class CreateWorkspaceRequest(BaseModel):
    """Body for ``POST .../workspaces``."""

    model_config = _REQUEST_CONFIG

    name: str = Field(min_length=1, max_length=80)
    research_topic: str | None = Field(default=None, max_length=500)


class UpdateWorkspaceRequest(BaseModel):
    """PATCH body for ``PATCH .../workspaces/{workspace_id}``.

    ``model_fields_set`` semantics like the session patch: absent fields stay
    unchanged. ``is_legacy`` is immutable by construction (not patchable).
    """

    model_config = _REQUEST_CONFIG

    name: str | None = Field(default=None, min_length=1, max_length=80)
    research_topic: str | None = Field(default=None, max_length=500)


class ActiveWorkspacePointer(BaseModel):
    """Content of ``workspaces/active.json``."""

    model_config = _RESPONSE_CONFIG

    workspace_id: str | None = None
    updated_at: datetime
