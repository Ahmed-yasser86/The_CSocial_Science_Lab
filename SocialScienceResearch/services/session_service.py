"""Session-context service - the researcher's active project/dataset state.

The selection is persisted as a small JSON document under the *active
workspace's* data dir (``session_context.json``) so it survives server
restarts and is shared by every API worker reading the same data directory.
Reads are tolerant: a missing or corrupt file yields the default (both ids
unset). Writes are atomic (tmp file + ``os.replace``).

The workspace pointer is stored separately in the root
``workspaces/active.json`` (a workspace cannot contain the pointer to
itself), managed by :class:`WorkspaceService`; setting it performs a full
activation (database + data-dir routing + cache clearing).

Unknown project/dataset/workspace ids raise :class:`KeyError`; the router maps
that to a 404 error envelope.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.session_models import (
    SessionContext,
    SessionContextPatch,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.utils.idgen import utcnow

_FIELDS = ("active_project_id", "active_dataset_id")


class SessionContextService:
    """Load/save the session context document."""

    def __init__(
        self,
        repos: Repositories | None = None,
        *,
        settings: SocialScienceSettings | None = None,
        workspaces=None,
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._root_data_dir = Path(self._settings.repository.data_dir)
        self._workspaces = workspaces

    def _data_dir(self) -> Path:
        """Data dir of the active workspace (root data dir when none active)."""
        if self._workspaces is not None:
            workspace_id = self._workspaces.active_workspace_id()
            if workspace_id:
                try:
                    workspace = self._workspaces.get(workspace_id)
                except KeyError:
                    return self._root_data_dir
                return Path(workspace.data_dir)
        return self._root_data_dir

    @property
    def _path(self) -> Path:
        return self._data_dir() / "session_context.json"

    def load(self) -> SessionContext:
        """Return the current context; missing/corrupt file means defaults."""
        data = dict.fromkeys(_FIELDS)
        updated_at = None
        path = self._path
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            if isinstance(raw, dict):
                for field in _FIELDS:
                    value = raw.get(field)
                    if isinstance(value, str):
                        data[field] = value
                stored = raw.get("updated_at")
                if isinstance(stored, str):
                    try:
                        updated_at = datetime.fromisoformat(stored)
                    except ValueError:
                        updated_at = None
        workspace_id = None
        if self._workspaces is not None:
            try:
                workspace_id = self._workspaces.active_workspace_id()
                if workspace_id is not None:
                    # Surface 404-consistent state: a dangling pointer is
                    # treated as "no active workspace".
                    self._workspaces.get(workspace_id)
            except KeyError:
                workspace_id = None
        return SessionContext(
            **data,
            active_workspace_id=workspace_id,
            updated_at=updated_at or utcnow(),
        )

    def update(self, patch: SessionContextPatch) -> SessionContext:
        """Apply only the fields present in ``patch.model_fields_set``."""
        # The workspace switch comes FIRST: any project/dataset ids in the
        # same patch are then validated against the NEW workspace's corpus.
        if "active_workspace_id" in patch.model_fields_set:
            if self._workspaces is None:
                raise ValueError(
                    "Workspace switching requires the workspace registry"
                )
            target = patch.active_workspace_id
            if target is None:
                self._workspaces.deactivate()
            else:
                self._workspaces.activate(target)
        data = self.load().model_dump()
        data.pop("updated_at", None)
        data.pop("active_workspace_id", None)
        for field in _FIELDS:
            if field not in patch.model_fields_set:
                continue
            value = getattr(patch, field)
            if value is not None:
                self._require(field, value)
            data[field] = value
        context = SessionContext(**data, updated_at=utcnow())
        self._save(context)
        return self.load() if self._workspaces is not None else context

    def _require(self, field: str, value: str) -> None:
        """Raise :class:`KeyError` when the referenced entity does not exist."""
        if self._repos is None:
            return
        if field == "active_project_id":
            entity = self._repos.projects.get_project(value)
            label = "Project"
        else:
            entity = self._repos.datasets.get_dataset(value)
            label = "Dataset"
        if entity is None:
            raise KeyError(f"{label} {value!r} not found")

    def _save(self, context: SessionContext) -> None:
        path = self._path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        payload = {
            field: getattr(context, field) for field in _FIELDS
        }
        payload["updated_at"] = context.updated_at.isoformat()
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
