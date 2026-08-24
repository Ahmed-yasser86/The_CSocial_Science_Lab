"""Session-context service - the researcher's active project/dataset state.

The selection is persisted as a small JSON document under the settings data
dir (``session_context.json``) so it survives server restarts and is shared by
every API worker reading the same data directory. Reads are tolerant: a
missing or corrupt file yields the default (both ids unset). Writes are
atomic (tmp file + ``os.replace``).

Unknown project/dataset ids raise :class:`KeyError`; the router maps that to
a 404 error envelope.
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
    ) -> None:
        self._repos = repos
        self._path = Path(
            (settings or SocialScienceSettings()).repository.data_dir
        ) / "session_context.json"

    def load(self) -> SessionContext:
        """Return the current context; missing/corrupt file means defaults."""
        data = dict.fromkeys(_FIELDS)
        updated_at = None
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
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
        return SessionContext(
            **data, updated_at=updated_at or utcnow()
        )

    def update(self, patch: SessionContextPatch) -> SessionContext:
        """Apply only the fields present in ``patch.model_fields_set``."""
        data = self.load().model_dump()
        data.pop("updated_at", None)
        for field in _FIELDS:
            if field not in patch.model_fields_set:
                continue
            value = getattr(patch, field)
            if value is not None:
                self._require(field, value)
            data[field] = value
        context = SessionContext(**data, updated_at=utcnow())
        self._save(context)
        return context

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
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            json.dumps(context.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        os.replace(tmp, self._path)
