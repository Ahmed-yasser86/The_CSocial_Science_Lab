"""B8: Explorer + provenance router.

Endpoints for browsing structured rows per entity (``ExplorerService``, built on
``QueryService.resolve_latest_rows``) and for reconstructing each record's
collection provenance chain (``ProvenanceService``).

* ``GET {prefix}/explore/records`` - cursor-paginated, searchable, filterable
  rows with a per-entity column catalogue and sort options. ``filters`` is a
  JSON-encoded array of ``{"variable", "operator", "value"}`` objects decoded
  here (malformed JSON or non-list payloads -> HTTP 400).
* ``GET {prefix}/explore/records/{entity}/{entity_id}/raw`` - the sanitized
  ``raw_json`` of the persisted record (HTTP 404 for unknown ids).
* ``GET {prefix}/explore/provenance/{entity}/{entity_id}`` - the provenance
  chain (first-observed run, observation history, run summaries).

Domain errors map to the app's error envelope: unknown entity/variable/operator
raise ``ValueError`` (HTTP 400); missing ids raise 404.

Owned by the B8 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.services.explorer_service import (
    ExploreResult,
    ExplorerService,
)
from SocialScienceResearch.services.provenance_service import (
    EntityNotFoundError,
    ProvenanceRecord,
    ProvenanceService,
)

router = APIRouter()

#: Default page size for explorer pages (mirrors the app's list endpoints).
DEFAULT_PAGE_SIZE = 25


def _explorer(request: Request) -> ExplorerService:
    return get_service(
        request,
        "explorer",
        lambda: ExplorerService(
            request.app.state.services["repos"], request.app.state.settings
        ),
    )


def _provenance(request: Request) -> ProvenanceService:
    return get_service(
        request,
        "provenance",
        lambda: ProvenanceService(request.app.state.services["repos"]),
    )


def _decode_filters(raw: str | None) -> list[dict[str, Any]] | None:
    """Safely decode the JSON-encoded ``filters`` query parameter.

    Expected shape: ``[{"variable": "...", "operator": "...", "value": ...}]``.
    Malformed JSON, non-list payloads or entries without the two required keys
    raise ``ValueError`` -> HTTP 400 via the app's error envelope.
    """
    if raw is None or raw == "":
        return None
    try:
        decoded = json.loads(raw)
    except ValueError as exc:
        raise ValueError(
            "filters must be a valid JSON array of "
            "{variable, operator, value} objects"
        ) from exc
    if not isinstance(decoded, list):
        raise ValueError(
            "filters must decode to a JSON array of {variable, operator, value} objects"
        )
    for index, item in enumerate(decoded):
        if not isinstance(item, dict) or "variable" not in item or "operator" not in item:
            raise ValueError(
                f"filter #{index} must be an object with 'variable' and 'operator' keys"
            )
    return decoded


class RawRecordPayload(BaseModel):
    """The sanitized source payload behind one persisted record."""

    model_config = ConfigDict(extra="allow")

    entity: str
    entity_id: str
    raw_json: dict[str, Any] = Field(default_factory=dict)


@router.get("/explore/records", response_model=ExploreResult, tags=["explorer"])
def explore_records(
    request: Request,
    entity: str = Query(..., description="Entity kind: video, comment, channel, recommendation, author"),
    q: str | None = Query(None, description="Case-insensitive text search over the entity's text fields"),
    filters: str | None = Query(None, description="JSON array of {variable, operator, value} filter objects"),
    sort: str | None = Query(None, description="Sort variable; prefix '-' for descending. None values sort last."),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Browse one page of entity rows with search, filters, sort and cursor pagination."""
    return _explorer(request).explore(
        entity=entity,
        q=q,
        filters=_decode_filters(filters),
        sort=sort,
        cursor=cursor,
        page_size=page_size,
    )


@router.get(
    "/explore/records/{entity}/{entity_id}/raw",
    response_model=RawRecordPayload,
    tags=["explorer"],
)
def explore_raw_record(request: Request, entity: str, entity_id: str):
    """Return the sanitized ``raw_json`` payload of one persisted record."""
    raw = _explorer(request).get_row_raw(entity, entity_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"{entity} {entity_id} not found")
    return raw


@router.get(
    "/explore/provenance/{entity}/{entity_id}",
    response_model=ProvenanceRecord,
    tags=["explorer"],
)
def explore_provenance(request: Request, entity: str, entity_id: str):
    """Return the provenance chain (first run, observation history, run summaries)."""
    try:
        return _provenance(request).provenance(entity, entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
