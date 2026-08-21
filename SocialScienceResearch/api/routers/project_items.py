"""Project Items router - manage sub-items within research projects.

ProjectItems group related samples and datasets for organized research workflows.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.domain.dataset_models import (
    ProjectItem,
    CreateProjectItemRequest,
    UpdateProjectItemRequest,
)
from SocialScienceResearch.services.project_item_service import ProjectItemService

router = APIRouter()


def _project_items(request: Request) -> ProjectItemService:
    """Lazily build/cache the shared ``ProjectItemService`` on ``app.state``."""
    return get_service(
        request,
        "project_items",
        lambda: ProjectItemService(request.app.state.services["repos"]),
    )


def _item_key(item: ProjectItem) -> tuple[str, ...]:
    return (item.created_at.isoformat(), item.item_id)


@router.post(
    "/projects/{project_id}/items",
    response_model=ProjectItem,
    tags=["projects"],
)
def create_project_item(project_id: str, body: CreateProjectItemRequest, request: Request) -> ProjectItem:
    """Create a new project item within a project."""
    return _project_items(request).create_item(project_id, body)


@router.get(
    "/projects/{project_id}/items",
    response_model=list[ProjectItem],
    tags=["projects"],
)
def list_project_items(project_id: str, request: Request) -> list[ProjectItem]:
    """List all items within a project."""
    return _project_items(request).list_items_by_project(project_id)


@router.get(
    "/projects/{project_id}/items/{item_id}",
    response_model=ProjectItem,
    tags=["projects"],
)
def get_project_item(project_id: str, item_id: str, request: Request) -> ProjectItem:
    """Get a specific project item."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    return item


@router.patch(
    "/projects/{project_id}/items/{item_id}",
    response_model=ProjectItem,
    tags=["projects"],
)
def update_project_item(project_id: str, item_id: str, body: UpdateProjectItemRequest, request: Request) -> ProjectItem:
    """Update a project item."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    return _project_items(request).update_item(item_id, body)


@router.post(
    "/projects/{project_id}/items/{item_id}/samples",
    response_model=ProjectItem,
    tags=["projects"],
)
def add_samples_to_item(project_id: str, item_id: str, body: dict, request: Request) -> ProjectItem:
    """Add sample IDs to a project item. Body: {"sample_ids": [...]}."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    sample_ids = body.get("sample_ids", [])
    return _project_items(request).add_samples(item_id, sample_ids)


@router.delete(
    "/projects/{project_id}/items/{item_id}/samples",
    response_model=ProjectItem,
    tags=["projects"],
)
def remove_samples_from_item(project_id: str, item_id: str, body: dict, request: Request) -> ProjectItem:
    """Remove sample IDs from a project item. Body: {"sample_ids": [...]}."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    sample_ids = body.get("sample_ids", [])
    return _project_items(request).remove_samples(item_id, sample_ids)


@router.post(
    "/projects/{project_id}/items/{item_id}/datasets",
    response_model=ProjectItem,
    tags=["projects"],
)
def add_datasets_to_item(project_id: str, item_id: str, body: dict, request: Request) -> ProjectItem:
    """Add dataset IDs to a project item. Body: {"dataset_ids": [...]}."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    dataset_ids = body.get("dataset_ids", [])
    return _project_items(request).add_datasets(item_id, dataset_ids)


@router.delete(
    "/projects/{project_id}/items/{item_id}/datasets",
    response_model=ProjectItem,
    tags=["projects"],
)
def remove_datasets_from_item(project_id: str, item_id: str, body: dict, request: Request) -> ProjectItem:
    """Remove dataset IDs from a project item. Body: {"dataset_ids": [...]}."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    dataset_ids = body.get("dataset_ids", [])
    return _project_items(request).remove_datasets(item_id, dataset_ids)


@router.delete(
    "/projects/{project_id}/items/{item_id}",
    tags=["projects"],
)
def delete_project_item(project_id: str, item_id: str, request: Request):
    """Delete a project item."""
    item = _project_items(request).get_item(item_id)
    if item.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in project {project_id}")
    _project_items(request).delete_item(item_id)
    return {"item_id": item_id, "deleted": True}