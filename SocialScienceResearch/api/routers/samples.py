"""B5: Persisted research samples router.

Endpoints for creating, listing, fetching, comparing and deleting immutable
samples (ADR-0011) backed by a ``SampleRepository``.

Router paths are relative; ``api/app.py`` mounts this router under the API
prefix (``app.include_router(samples.router, prefix=prefix)``). Each endpoint
declares a pydantic ``response_model``; list endpoints use opaque cursor
pagination (``{items, next_cursor, has_more, total}`` envelope). Bad input
raises ``ValueError``, mapped to HTTP 400 by ``api/app.py``.

Owned by the B5 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.domain.sample_models import (
    CreateSampleRequest,
    DeleteSampleResponse,
    Sample,
    SampleCompareRequest,
    SampleCompareResult,
)
from SocialScienceResearch.services.pagination import Paginated, page_sorted
from SocialScienceResearch.services.sample_service import SampleService
from SocialScienceResearch.utils.idgen import utcnow

from .common import get_service, paginated

router = APIRouter()

_DEFAULT_PAGE_SIZE = 50


def _samples(request: Request) -> SampleService:
    """Lazily build/cache the shared ``SampleService`` on ``app.state``."""
    return get_service(
        request,
        "samples",
        lambda: SampleService(request.app.state.services["repos"]),
    )


def _sample_key(sample: Sample) -> tuple[str, ...]:
    return (sample.created_at.isoformat(), sample.sample_id)


def _member_key(member_id: str) -> tuple[str, ...]:
    return (member_id,)


@router.post("/samples", response_model=Sample, tags=["samples"])
def create_sample(body: CreateSampleRequest, request: Request) -> Sample:
    """Persist a new immutable sample; returns the stored record."""
    return _samples(request).save(
        Sample(
            sample_id="",
            entity_type=body.entity_type,
            strategy=body.strategy,
            population_query_hash=body.population_query_hash,
            population_size=body.population_size,
            sample_size=len(body.member_ids),
            seed=body.seed,
            criteria_json=body.criteria_json,
            member_ids=body.member_ids,
            created_at=utcnow(),
            created_by_run_id=body.created_by_run_id,
        )
    )


@router.post("/samples/compare", response_model=SampleCompareResult, tags=["samples"])
def compare_samples(body: SampleCompareRequest, request: Request) -> SampleCompareResult:
    """Overlap / union / Jaccard / criteria diff across persisted samples."""
    result = _samples(request).compare_samples(body.sample_ids)
    return result.model_copy(update={"metrics": body.metrics})


@router.get("/samples", response_model=Paginated[Sample], tags=["samples"])
def list_samples(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=500),
) -> Paginated[Sample]:
    """All persisted, non-deleted samples (cursor-paginated)."""
    return paginated(
        _samples(request).list_samples(),
        cursor=cursor,
        page_size=page_size,
        key=_sample_key,
    )


@router.get("/samples/{sample_id}", response_model=Sample, tags=["samples"])
def get_sample(request: Request, sample_id: str) -> Sample:
    """One sample with its full, ordered member list."""
    sample = _samples(request).get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found")
    return sample


@router.get(
    "/samples/{sample_id}/members",
    response_model=Paginated[str],
    tags=["samples"],
)
def sample_members(
    request: Request,
    sample_id: str,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=500),
) -> Paginated[str]:
    """The ordered member ids of a sample (cursor-paginated)."""
    sample = _samples(request).get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found")
    full = sorted(sample.member_ids, key=_member_key)
    return page_sorted(
        full,
        cursor=cursor,
        page_size=page_size,
        key_func=_member_key,
        total=len(full),
    )


@router.delete("/samples/{sample_id}", response_model=DeleteSampleResponse, tags=["samples"])
def delete_sample(request: Request, sample_id: str) -> DeleteSampleResponse:
    """Delete an immutable sample (the only mutation, ADR-0011)."""
    if not _samples(request).delete_sample(sample_id):
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found")
    return DeleteSampleResponse(sample_id=sample_id, deleted=True)