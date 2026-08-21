"""Commenter-overlap router (audience duplication analysis).

Endpoints:

* ``GET /network/commenters/overlap`` - pairwise commenter overlap across a
  scope of videos/channels (Jaccard, Szymkiewicz-Simpson, shared sets,
  bridge commenters, overlap-edge overlay rows).
* ``GET /network/commenters/{author_key}/profile`` - per-commenter drill-down
  with full evidence comments and reply context.

Backed by :class:`CommenterOverlapService` (lazily built on ``app.state`` via
:func:`get_service`). Validation errors surface as ``invalid_argument`` (the
app-level ``ValueError`` handler); unknown author keys are ``404``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapResult,
    CommenterOverlapService,
    CommenterProfile,
)

router = APIRouter()


def _service(request: Request) -> CommenterOverlapService:
    return get_service(
        request,
        "commenters",
        lambda: CommenterOverlapService(request.app.state.services["repos"]),
    )


def _id_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


@router.get(
    "/network/commenters/overlap",
    tags=["network"],
    response_model=CommenterOverlapResult,
)
def commenter_overlap(
    request: Request,
    video_ids: str | None = Query(
        None, description="Comma-separated video ids (at least one of video_ids/channel_ids)"
    ),
    channel_ids: str | None = Query(
        None, description="Comma-separated channel ids (at least one of video_ids/channel_ids)"
    ),
    metric: str = Query(
        "jaccard",
        description="jaccard | overlap_coefficient | intersection",
    ),
    min_entities: int = Query(2, ge=1, description="Bridge-commenter entity threshold"),
    min_shared: int = Query(
        1, ge=1, description="Overlap-edge threshold (shared commenter count)"
    ),
    top_n: int = Query(50, ge=1, le=500, description="Cap on capped lists"),
):
    """Pairwise commenter overlap for a research scope.

    Returns video and/or channel projections (whichever scope was given) with
    per-entity commenter sets, pairwise Jaccard / Szymkiewicz-Simpson metrics,
    shared-commenter lists, bridge commenters, and overlap-edge rows.
    """
    return _service(request).overlap(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        metric=metric,
        min_entities=min_entities,
        min_shared=min_shared,
        top_n=top_n,
    )


@router.get(
    "/network/commenters/{author_key}/profile",
    tags=["network"],
    response_model=CommenterProfile,
)
def commenter_profile(
    request: Request,
    author_key: str,
    video_ids: str | None = Query(
        None, description="Comma-separated video ids to scope the profile"
    ),
    channel_ids: str | None = Query(
        None, description="Comma-separated channel ids to scope the profile"
    ),
    limit: int = Query(200, ge=1, le=500, description="Comment history cap"),
):
    """Per-commenter drill-down: totals, video/channel tables, evidence comments."""
    try:
        return _service(request).profile(
            author_key,
            video_ids=_id_list(video_ids),
            channel_ids=_id_list(channel_ids),
            limit=limit,
        )
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Commenter {author_key} not found"
        ) from None
