"""B7: Dataset and persisted-research-project domain models (ADR-0002 Phase D).

A :class:`Dataset` is a *materialized, immutable row set* selected from the
corpus - either a snapshot of an entity population or the rows matching a
persisted :class:`Project`'s research query. Members are persisted separately
as chunked row projections (see ``persistence.dataset_repository``); the
dataset header records provenance (``source_projection``), size and whether
the member list overflowed a single storage chunk.

A :class:`Project` persists a researcher's design so it can be re-run:
collection targets, the collection/sampling specs, the research query and the
chosen analysis variables, plus a ``config_hash`` over the *mutable*
definition so the exact design is auditable and reproducible.

Style follows the module conventions: request models use ``extra="forbid"``
(the API rejects unknown fields), response models use ``extra="allow"`` (the
UI never silently loses a column).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_REQUEST_CONFIG = ConfigDict(extra="forbid")
_RESPONSE_CONFIG = ConfigDict(extra="allow")

_ALLOWED_TARGET_KINDS = frozenset({"channel", "video", "recommendation"})
_ALLOWED_ENTITIES = frozenset({"channel", "video", "comment", "recommendation", "author"})


class Dataset(BaseModel):
    """A materialized, immutable row set built from the corpus.

    ``member_count`` mirrors the persisted member rows; ``overflow`` is ``True``
    when the members needed more than one storage chunk (see ADR-0001 / the
    ~32k Excel cell limit implemented in :mod:`persistence.dataset_repository`).
    """

    model_config = _RESPONSE_CONFIG

    dataset_id: str
    name: str
    description: str | None = None
    entity_type: str
    created_at: datetime
    created_by_run_id: str | None = None
    source_projection: dict[str, Any] = Field(default_factory=dict)
    member_count: int = 0
    overflow: bool = False


class Project(BaseModel):
    """A persisted ResearchProject design (ADR-0002 Phase D).

    ``targets`` items are ``{"kind": ..., "url": ...}`` dicts; the research
    query is the ``{"entity", "root", "query_context"}`` shape of
    ``domain.query.ResearchQueryRequest.model_dump()``. ``config_hash`` is a
    stable sha256 over the mutable definition (``ProjectService.config_hash``)
    and changes only when the researcher edits the design.
    """

    model_config = _RESPONSE_CONFIG

    project_id: str
    name: str
    description: str | None = None
    targets: list[dict[str, Any]] = Field(default_factory=list)
    collection_spec: dict[str, Any] = Field(default_factory=dict)
    sampling_specs: list[dict[str, Any]] = Field(default_factory=list)
    research_query: dict[str, Any] | None = None
    variable_selection: list[str] = Field(default_factory=list)
    notes: str | None = None
    config_hash: str
    created_at: datetime
    updated_at: datetime


class CreateDatasetRequest(BaseModel):
    """Body for ``POST .../datasets`` (``extra="forbid"``).

    When ``project_id`` is set the dataset is built from the project's research
    query and variable selection; otherwise a plain dataset snapshots the whole
    ``entity_type`` population. ``entity_type`` is the corpus slice in both
    cases and is only optional when the project's research query names it.
    """

    model_config = _REQUEST_CONFIG

    name: str
    description: str | None = None
    entity_type: str | None = None
    project_id: str | None = None
    include_raw: bool = False
    run_ids: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    channel_ids: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)
    member_ids: list[str] = Field(default_factory=list)
    criteria: dict[str, Any] | None = None
    variable_selection: list[str] = Field(default_factory=list)

    @field_validator("entity_type")
    @classmethod
    def _entity_type_normalized(cls, value: str | None) -> str | None:
        if value is None:
            return None
        entity = value.strip().lower()
        if entity not in _ALLOWED_ENTITIES:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of "
                f"{sorted(_ALLOWED_ENTITIES)}"
            )
        return entity


class CreateProjectRequest(BaseModel):
    """Body for ``POST .../projects`` (``extra="forbid"``)."""

    model_config = _REQUEST_CONFIG

    name: str
    description: str | None = None
    targets: list[dict[str, Any]] = Field(default_factory=list)
    collection_spec: dict[str, Any] = Field(default_factory=dict)
    sampling_specs: list[dict[str, Any]] = Field(default_factory=list)
    research_query: dict[str, Any] | None = None
    variable_selection: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("targets")
    @classmethod
    def _targets_valid(cls, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not targets:
            raise ValueError("at least one target is required")
        for target in targets:
            kind = target.get("kind")
            if kind not in _ALLOWED_TARGET_KINDS:
                raise ValueError(
                    f"target kind {kind!r} must be one of "
                    f"{sorted(_ALLOWED_TARGET_KINDS)}"
                )
            url = (target.get("url") or "").strip()
            if not url:
                raise ValueError("target url must not be empty")
        return targets


class UpdateProjectRequest(BaseModel):
    """PATCH body for ``PATCH .../projects/{project_id}`` (``extra="forbid"``).

    Only explicitly provided fields are applied (pydantic ``model_fields_set``
    semantics); sending ``research_query: null`` clears the query.
    """

    model_config = _REQUEST_CONFIG

    name: str | None = None
    description: str | None = None
    notes: str | None = None
    variable_selection: list[str] | None = None
    research_query: dict[str, Any] | None = None


class ColumnCoverage(BaseModel):
    """Missing-value statistics for one column of a dataset's stored rows."""

    model_config = _RESPONSE_CONFIG

    name: str
    present: int
    missing: int
    missing_share: float


class ProjectItem(BaseModel):
    """A project item that groups related samples and datasets for a research project.

    A project item can contain multiple samples and datasets, allowing researchers
    to organize their work into logical units (e.g., "Pilot Study", "Main Analysis",
    "Replication"). Each item tracks its constituent samples and datasets with
    provenance information.
    """

    model_config = _RESPONSE_CONFIG

    item_id: str
    project_id: str
    name: str
    description: str | None = None
    item_type: Literal["sample_group", "dataset_group", "mixed"] = "mixed"
    sample_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateProjectItemRequest(BaseModel):
    """Body for ``POST .../projects/{project_id}/items`` (``extra="forbid"``)."""

    model_config = _REQUEST_CONFIG

    name: str
    description: str | None = None
    item_type: Literal["sample_group", "dataset_group", "mixed"] = "mixed"
    sample_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class UpdateProjectItemRequest(BaseModel):
    """PATCH body for ``PATCH .../projects/{project_id}/items/{item_id}``."""

    model_config = _REQUEST_CONFIG

    name: str | None = None
    description: str | None = None
    sample_ids: list[str] | None = None
    dataset_ids: list[str] | None = None
    tags: list[str] | None = None


class DatasetQualityReport(BaseModel):
    """Dataset quality report: per-column missing-value matrix plus coverage.

    ``corpus`` embeds the reused ``QualityService.dataset_summary()`` snapshot
    so the dataset-level numbers sit next to the corpus-level ones.
    """

    model_config = _RESPONSE_CONFIG

    dataset_id: str
    columns: list[ColumnCoverage] = Field(default_factory=list)
    overall_coverage: float
    generated_at: datetime
    corpus: dict[str, Any] = Field(default_factory=dict)