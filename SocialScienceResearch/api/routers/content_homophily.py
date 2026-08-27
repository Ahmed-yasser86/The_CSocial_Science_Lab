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

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.api.schemas import (
    ContentHomophilyStartPayload,
    ContentHomophilyStartRequest,
)
from SocialScienceResearch.services.content_homophily_service import (
    ContentHomophilyService,
)
from SocialScienceResearch.services.community_export_service import (
    CommunityExportService,
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
            budget_controller=request.app.state.budget_controller,
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
            max_transcript_videos=body.max_transcript_videos,
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
    "/network/content-homophily/export-communities",
    tags=["content_homophily"],
)
def export_communities(
    request: Request,
    run_id: str | None = Query(None, description="Network scope run id"),
    analysis_id: str | None = Query(None, description="Optional content-homophily analysis to attach as reference"),
    video_ids: str | None = Query(None, description="Optional comma-separated video-id ego scope"),
):
    """Export a ZIP of per-community node/edge lists, the global edge list, and a
    DETAILED per-community-pair content-similarity analysis (reused cached
    embeddings, no new model calls)."""
    try:
        svc = CommunityExportService(
            repos=request.app.state.services["repos"],
            settings=request.app.state.settings,
        )
        scope_ids = None
        if video_ids:
            scope_ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        data = svc.export_zip(
            run_id=run_id, video_ids=scope_ids, analysis_id=analysis_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"export failed: {exc}")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                'attachment; filename="communities_export.zip"'
            )
        },
    )


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


@router.get(
    "/network/content-homophily/{analysis_id}/export-sample",
    tags=["content_homophily"],
)
def export_sample(
    request: Request,
    analysis_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
):
    """Export the selected sample as CSV/JSON with title, channel and link.

    The "selected sample" is the unique set of videos actually analysed in the
    content-homophily run (bounded by the transcript-video budget). Each row /
    object carries the video id, title, channel id + title, watch URL, and
    whether the video appeared in a within-community or between-community pair.
    """
    service = _service(request)
    record = service.get(analysis_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Content homophily analysis {analysis_id} not found",
        )
    results = record.get("results") or {}
    sample_videos = results.get("sample_videos")
    sample_roles = results.get("sample_roles") or {}
    if not sample_videos:
        raise HTTPException(
            status_code=409,
            detail=(
                "This analysis has no exportable sample (it may still be "
                "running, finished with insufficient data, or was produced "
                "before sample export was supported)."
            ),
        )

    repos = request.app.state.services["repos"]

    def _video_meta(vid: str) -> dict[str, Any]:
        title = None
        url = f"https://www.youtube.com/watch?v={vid}"
        channel_id = None
        channel_title = None
        try:
            video = repos.videos.get_video(vid)
        except Exception:  # noqa: BLE001
            video = None
        if video is not None:
            title = video.title
            if video.url:
                url = video.url
            channel_id = video.channel_id
            if channel_id:
                try:
                    channel = repos.channels.get_channel(channel_id)
                except Exception:  # noqa: BLE001
                    channel = None
                if channel is not None:
                    channel_title = channel.title
        role = sample_roles.get(vid, {}) or {}
        return {
            "video_id": vid,
            "title": title or "",
            "channel_id": channel_id or "",
            "channel_title": channel_title or "",
            "url": url,
            "appeared_in_within": bool(role.get("within", False)),
            "appeared_in_between": bool(role.get("between", False)),
        }

    rows = [_video_meta(vid) for vid in sample_videos]

    if format == "json":
        content = json.dumps(rows, indent=2, ensure_ascii=False)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="content_homophily_'
                    f'{analysis_id}_sample.json"'
                )
            },
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "video_id",
            "title",
            "channel_id",
            "channel_title",
            "url",
            "appeared_in_within",
            "appeared_in_between",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="content_homophily_'
                f'{analysis_id}_sample.csv"'
            )
        },
    )
