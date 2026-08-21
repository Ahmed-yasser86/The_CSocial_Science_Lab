"""Persisted ResearchProject service (ADR-0002 Phase D) - B7.

Projects keep a researcher's design on disk so it can be re-run and audited:
targets, collection/sampling specs, the research query and the chosen analysis
variables. ``config_hash`` is a **stable** sha256 over the mutable definition
(``ProjectService.config_hash``) - recomputed on update and guaranteed equal
for two projects with the same definition, and different for a changed one.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from SocialScienceResearch.domain.dataset_models import (
    Project,
    UpdateProjectRequest,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.utils.idgen import utcnow

_MUTABLE_FIELDS = (
    "name",
    "description",
    "notes",
    "targets",
    "collection_spec",
    "sampling_specs",
    "research_query",
    "variable_selection",
)


class ProjectService:
    """CRUD + design-hashing for persisted research projects."""

    def __init__(self, repos: Repositories) -> None:
        self._projects = repos.projects

    # ------------------------------------------------------------------
    @staticmethod
    def config_hash(definition: dict[str, Any]) -> str:
        """Stable sha256 (first 16 hex) of the mutable project definition.

        Mirrors ``CollectionSpec.spec_hash``: canonical JSON sorted by key, so
        two identical definitions hash identically regardless of field order.
        """
        canonical = json.dumps(definition, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _definition(cls, project: Project) -> dict[str, Any]:
        return {field: getattr(project, field) for field in _MUTABLE_FIELDS}

    # ------------------------------------------------------------------
    def create(self, project: Project) -> Project:
        """Persist a project after stamping its ``config_hash``.

        Identity/timestamps come from the caller (already on ``project``);
        the hash is computed here so it always matches the persisted definition.
        """
        project.config_hash = self.config_hash(self._definition(project))
        self._projects.save_project(project)
        return project

    def list_projects(self) -> list[Project]:
        return self._projects.list_projects()

    def get_project(self, project_id: str) -> Project:
        project = self._projects.get_project(project_id)
        if project is None:
            raise ValueError(f"Project {project_id!r} not found")
        return project

    def update_project(
        self, project_id: str, patch: UpdateProjectRequest
    ) -> Project:
        """Apply ``patch`` (only explicitly provided fields), re-hash, persist."""
        current = self.get_project(project_id)
        data = current.model_dump(exclude={"config_hash", "created_at", "updated_at"})
        for field in ("name", "description", "notes", "variable_selection", "research_query"):
            if field in patch.model_fields_set:
                data[field] = getattr(patch, field)
        updated = Project(
            **data,
            config_hash="",
            created_at=current.created_at,
            updated_at=utcnow(),
        )
        updated.config_hash = self.config_hash(self._definition(updated))
        self._projects.update_project(updated)
        return updated

    def delete_project(self, project_id: str) -> None:
        """Raise :class:`ValueError` for an unknown id, then delete."""
        self.get_project(project_id)
        self._projects.delete_project(project_id)