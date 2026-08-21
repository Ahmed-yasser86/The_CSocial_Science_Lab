"""Project models for research organization (ADR-0002 Phase D extension).

Defines lightweight Project and Dataset models for combining samples into
datasets with lineage tracking and organizing datasets into projects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.utils.idgen import utcnow

_RESPONSE_CONFIG = ConfigDict(extra="allow")
_REQUEST_CONFIG = ConfigDict(extra="forbid")


class DatasetLabels(BaseModel):
    """Three-namespace labeling system for datasets (mirrors SampleLabels)."""

    system: dict[str, Any] = Field(default_factory=dict)
    research: dict[str, Any] = Field(default_factory=dict)
    custom: dict[str, Any] = Field(default_factory=dict)


class Dataset(BaseModel):
    """A combined dataset built from one or more samples with lineage tracking.

    Tracks source samples via ``sample_ids`` and parent datasets via
    ``parent_dataset_ids`` for full provenance. ``deduplicated`` indicates
    whether duplicate member IDs were removed during combination.
    ``lineage_preserved`` indicates whether each member tracks its source.
    """

    model_config = _RESPONSE_CONFIG

    dataset_id: str
    name: str
    description: str = ""

    sample_ids: list[str] = Field(default_factory=list)
    parent_dataset_ids: list[str] = Field(default_factory=list)

    labels: dict[str, Any] = Field(default_factory=dict)

    total_members: int = 0
    entity_types: list[str] = Field(default_factory=list)
    source_scopes: list[str] = Field(default_factory=list)

    deduplicated: bool = True
    lineage_preserved: bool = True

    created_at: datetime = Field(default_factory=utcnow)
    created_by: str = ""
    updated_at: datetime = Field(default_factory=utcnow)


class Project(BaseModel):
    """A research project that groups datasets for a study.

    Provides organizational structure above datasets, allowing researchers
    to organize combined samples into coherent research projects.
    """

    model_config = _RESPONSE_CONFIG

    project_id: str
    name: str
    description: str = ""
    dataset_ids: list[str] = Field(default_factory=list)
    labels: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CreateDatasetRequest(BaseModel):
    """Body for ``POST .../datasets`` (new style, extra="forbid")."""

    model_config = _REQUEST_CONFIG

    name: str
    description: str = ""
    sample_ids: list[str] = Field(default_factory=list)
    parent_dataset_ids: list[str] = Field(default_factory=list)
    labels: dict[str, Any] = Field(default_factory=dict)
    deduplicated: bool = True
    lineage_preserved: bool = True
    created_by: str = ""


class CreateProjectRequest(BaseModel):
    """Body for ``POST .../projects`` (extra="forbid")."""

    model_config = _REQUEST_CONFIG

    name: str
    description: str = ""
    dataset_ids: list[str] = Field(default_factory=list)
    labels: dict[str, Any] = Field(default_factory=dict)


class UpdateDatasetRequest(BaseModel):
    """PATCH body for ``PATCH .../datasets/{dataset_id}``."""

    model_config = _REQUEST_CONFIG

    name: str | None = None
    description: str | None = None
    labels: dict[str, Any] | None = None


class UpdateProjectRequest(BaseModel):
    """PATCH body for ``PATCH .../projects/{project_id}``."""

    model_config = _REQUEST_CONFIG

    name: str | None = None
    description: str | None = None
    dataset_ids: list[str] | None = None
    labels: dict[str, Any] | None = None


class DeleteDatasetResponse(BaseModel):
    """Response of ``DELETE .../datasets/{dataset_id}``."""

    model_config = _RESPONSE_CONFIG

    dataset_id: str
    deleted: bool = True


class DeleteProjectResponse(BaseModel):
    """Response of ``DELETE .../projects/{project_id}``."""

    model_config = _RESPONSE_CONFIG

    project_id: str
    deleted: bool = True
