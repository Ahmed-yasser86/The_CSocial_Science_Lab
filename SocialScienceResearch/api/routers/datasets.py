"""B7: Datasets / projects / quality / export router.

Endpoints for:

* persisted :class:`~SocialScienceResearch.domain.dataset_models.Project`
  (ResearchProject, ADR-0002 Phase D) - create, list, get, patch, delete;
* :class:`~SocialScienceResearch.domain.dataset_models.Dataset` - create
  (a plain corpus snapshot, or from a project's research query + variable
  selection), list, get, delete, cursor-paginated members;
* per-dataset quality (missing-value matrix + corpus coverage summary);
* dataset export as CSV or JSON via :class:`StreamingResponse` with a
  ``Content-Disposition`` attachment header.

All validation raises :class:`ValueError`, mapped to ``400`` by the app's
handler (``code: invalid_argument``) - nothing here raises ``HTTPException``.

Owned by the B7 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.domain.dataset_models import (
    CreateDatasetRequest,
    CreateProjectRequest,
    Dataset,
    DatasetQualityReport,
    Project,
    UpdateProjectRequest,
)
from SocialScienceResearch.services.dataset_service import DatasetService
from SocialScienceResearch.services.pagination import Paginated
from SocialScienceResearch.services.project_service import ProjectService
from SocialScienceResearch.utils.idgen import new_id, utcnow

from .common import get_service, paginated

router = APIRouter()

_DATASETS = "datasets"
_PROJECTS = "projects"
DEFAULT_PAGE_SIZE = 50


class DatasetMemberRow(BaseModel):
    """One member row projection (columns vary per dataset; extras allowed)."""

    model_config = ConfigDict(extra="allow")


class UpdateDatasetRequest(BaseModel):
    """PATCH body for ``PATCH .../datasets/{dataset_id}`` (``extra="forbid"``)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None


class CombineDatasetsRequest(BaseModel):
    """Body for ``POST .../datasets/combine`` (``extra="forbid"``).

    Combines multiple datasets into a new dataset, optionally deduplicating
    members and preserving lineage (which original dataset each member came from).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    deduplicate: bool = True


class DeleteProjectPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_id: str
    deleted: bool = True


class DeleteDatasetPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_id: str
    deleted: bool = True


class DatasetExportPayload(BaseModel):
    """Documentation-only response model for the streaming export endpoint.

    The route actually streams the dataset bytes via ``StreamingResponse``;
    this model exists so the route still satisfies the API contract gate that
    every route declares a ``response_model``.
    """

    model_config = ConfigDict(extra="allow")

    dataset_id: str
    format: str


def _datasets_service(request: Request) -> DatasetService:
    return get_service(
        request,
        _DATASETS,
        lambda: DatasetService(
            request.app.state.services["repos"],
            request.app.state.settings,
        ),
    )


def _projects_service(request: Request) -> ProjectService:
    return get_service(
        request,
        _PROJECTS,
        lambda: ProjectService(request.app.state.services["repos"]),
    )


def _dataset_key(dataset: Dataset) -> tuple[str, ...]:
    return (dataset.dataset_id,)


def _project_key(project: Project) -> tuple[str, ...]:
    return (project.project_id,)


# ----------------------------------------------------------------------
# Projects (ADR-0002 Phase D)
# ----------------------------------------------------------------------
@router.post("/projects", tags=["projects"], response_model=Project)
def create_project(body: CreateProjectRequest, request: Request) -> Project:
    now = utcnow()
    return _projects_service(request).create(
        Project(
            project_id=new_id("proj"),
            name=body.name,
            description=body.description,
            targets=[dict(target) for target in body.targets],
            collection_spec=dict(body.collection_spec),
            sampling_specs=[dict(spec) for spec in body.sampling_specs],
            research_query=(
                dict(body.research_query)
                if body.research_query is not None
                else None
            ),
            variable_selection=list(body.variable_selection),
            notes=body.notes,
            config_hash="",
            created_at=now,
            updated_at=now,
        )
    )


@router.get("/projects", tags=["projects"], response_model=Paginated[Project])
def list_projects(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    projects = _projects_service(request).list_projects()
    return paginated(
        projects, cursor=cursor, page_size=page_size, key=_project_key
    )


@router.get("/projects/{project_id}", tags=["projects"], response_model=Project)
def get_project(project_id: str, request: Request) -> Project:
    return _projects_service(request).get_project(project_id)


@router.patch("/projects/{project_id}", tags=["projects"], response_model=Project)
def patch_project(
    project_id: str, body: UpdateProjectRequest, request: Request
) -> Project:
    return _projects_service(request).update_project(project_id, body)


@router.delete(
    "/projects/{project_id}",
    tags=["projects"],
    response_model=DeleteProjectPayload,
)
def delete_project(project_id: str, request: Request) -> DeleteProjectPayload:
    service = _projects_service(request)
    service.delete_project(project_id)
    return DeleteProjectPayload(project_id=project_id, deleted=True)


# ----------------------------------------------------------------------
# Datasets
# ----------------------------------------------------------------------
@router.post("/datasets", tags=["datasets"], response_model=Dataset)
def create_dataset(body: CreateDatasetRequest, request: Request) -> Dataset:
    service = _datasets_service(request)
    if body.project_id is not None:
        return service.create_from_project(
            body.project_id,
            name=body.name,
            description=body.description,
            include_raw=body.include_raw,
            entity_type=body.entity_type,
        )
    if body.entity_type is None:
        raise ValueError(
            "entity_type is required when no project_id is supplied"
        )
    return service.create_dataset(
        body.name,
        body.description,
        entity_type=body.entity_type,
        include_raw=body.include_raw,
        run_ids=body.run_ids,
        channel_ids=body.channel_ids,
        video_ids=body.video_ids,
        member_ids=body.member_ids,
        criteria=body.criteria,
        variable_selection=body.variable_selection,
    )


@router.get("/datasets", tags=["datasets"], response_model=Paginated[Dataset])
def list_datasets(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    service = _datasets_service(request)
    return paginated(
        service.list_datasets(), cursor=cursor, page_size=page_size, key=_dataset_key
    )


@router.get("/datasets/{dataset_id}", tags=["datasets"], response_model=Dataset)
def get_dataset(dataset_id: str, request: Request) -> Dataset:
    return _datasets_service(request).get_dataset(dataset_id)


@router.delete(
    "/datasets/{dataset_id}",
    tags=["datasets"],
    response_model=DeleteDatasetPayload,
)
def delete_dataset(dataset_id: str, request: Request) -> DeleteDatasetPayload:
    service = _datasets_service(request)
    service.delete_dataset(dataset_id)
    return DeleteDatasetPayload(dataset_id=dataset_id, deleted=True)


@router.patch("/datasets/{dataset_id}", tags=["datasets"], response_model=Dataset)
def patch_dataset(
    dataset_id: str, body: UpdateDatasetRequest, request: Request
) -> Dataset:
    """Update dataset name and/or description."""
    service = _datasets_service(request)
    return service.update_dataset(dataset_id, body)


@router.post("/datasets/combine", tags=["datasets"], response_model=Dataset)
def combine_datasets(
    body: CombineDatasetsRequest, request: Request
) -> Dataset:
    """Combine multiple datasets into a new dataset.

    Members are deduplicated by default (based on the id_field of each member).
    When deduplication is disabled, all members from all source datasets are included.
    """
    if not body.dataset_ids:
        raise ValueError("at least one dataset_ids entry is required")
    if len(body.dataset_ids) < 2:
        raise ValueError("at least two dataset_ids are required for combining")
    service = _datasets_service(request)
    return service.combine_datasets(
        name=body.name,
        description=body.description,
        dataset_ids=body.dataset_ids,
        deduplicate=body.deduplicate,
    )


@router.get(
    "/datasets/{dataset_id}/members",
    tags=["datasets"],
    response_model=Paginated[DatasetMemberRow],
)
def dataset_members(
    request: Request,
    dataset_id: str,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    service = _datasets_service(request)
    dataset = service.get_dataset(dataset_id)
    id_field = dataset.source_projection.get("id_field") or "id"
    members = service.members(dataset_id)
    return paginated(
        members,
        cursor=cursor,
        page_size=page_size,
        key=lambda member: (str(member.get(id_field)),),
    )


@router.get(
    "/datasets/{dataset_id}/quality",
    tags=["datasets"],
    response_model=DatasetQualityReport,
)
def dataset_quality(dataset_id: str, request: Request) -> DatasetQualityReport:
    return _datasets_service(request).quality(dataset_id)


@router.get(
    "/datasets/{dataset_id}/export",
    tags=["datasets"],
    response_class=StreamingResponse,
    response_model=DatasetExportPayload,
)
def dataset_export(
    request: Request,
    dataset_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
):
    """Stream the dataset's member rows as CSV or JSON with an attachment header."""
    filename, content, media_type = _datasets_service(request).export(
        dataset_id, format=format.lower()
    )
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )