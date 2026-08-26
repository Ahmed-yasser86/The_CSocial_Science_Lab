"""Content Homophily router (Content Homophily spec §2, §19, §24).

Opt-in, on-demand CONTENT evidence layer endpoints (usable from ANY supported
network scope - not echo-chamber-specific):

* ``POST /network/content-homophily``            - start the on-demand job;
* ``GET  /network/content-homophily``            - list past analyses;
* ``GET  /network/content-homophily/{id}``       - status + progress (incl.
  embedding observability fields) + results when finished.

Nothing here runs as part of any default pipeline; transcript collection is
targeted at sampled videos and happens ONLY inside the requested job.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.api.schemas import (
    ContentHomophilyStartPayload,
    ContentHomophilyStartRequest,
)
from SocialScienceResearch.services.content_homophily_service import (
    ContentHomophilyService,
)
from SocialScienceResearch.services.pagination import Paginated, page_sorted

router = APIRouter()

DEFAULT_PAGE_SIZE = 50


def _service(request: Request) -> ContentHomophilyService:
    return get_service(
        request,
        "content_homophily",
        lambda: ContentHomophilyService(
            request.app.state.services["recommendations"]._provider,
            request.app.state.services["repos"],
            settings=request.app.state.settings,
            jobs=request.app.state.services["jobs"],
        ),
    )


@router.post(
    "/network/content-homophily",
    tags=["content_homophily"],
    response_model=ContentHomophilyStartPayload,
)
def start_analysis(request: Request, body: ContentHomophilyStartRequest):
    """Start an opt-in Content Homophily analysis job.

    Targeted transcript collection + embeddings + seeded pair sampling +
    community-label permutation null. Runs in the background; poll
    ``GET /network/content-homophily/{analysis_id}`` for stage progress and
    results. Nothing about this endpoint runs automatically.
    """
    service = _service(request)
    try:
        return service.start(
            run_id=body.run_id,
            video_ids=body.video_ids,
            sampling_fraction=body.sampling_fraction,
            max_pair_cap=body.max_pair_cap,
            random_seed=body.random_seed,
            num_permutations=body.num_permutations,
            max_videos_per_community=body.max_videos_per_community,
            include_edge_similarity=body.include_edge_similarity,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/network/content-homophily",
    tags=["content_homophily"],
    response_model=Paginated[dict],
)
def list_analyses(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Persisted Content Homophily analyses, newest first."""
    records = _service(request).list()
    key = lambda r: (r.get("created_at") or "", r.get("analysis_id") or "")
    full = sorted(records, key=key)
    page = page_sorted(full, cursor=cursor, page_size=page_size,
                       key_func=key, total=len(full))
    return Paginated(items=page.items, next_cursor=page.next_cursor,
                     has_more=page.has_more, total=page.total)


@router.get(
    "/network/content-homophily/{analysis_id}",
    tags=["content_homophily"],
)
def get_analysis(request: Request, analysis_id: str):
    """Full analysis record: status, per-stage checklist progress (with
    embedding observability), execution log, and CONTENT EVIDENCE results."""
    record = _service(request).get(analysis_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Content homophily analysis {analysis_id} not found",
        )
    return record
