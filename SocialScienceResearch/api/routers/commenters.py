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
from fastapi.responses import StreamingResponse

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.services.commenter_network_service import (
    CommenterNetworkGraph,
    CommenterNetworkMetrics,
    CommenterNetworkService,
)
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapResult,
    CommenterOverlapService,
    CommenterProfile,
)
from SocialScienceResearch.services.weight_spec import WeightSpecError, parse_weight_spec

router = APIRouter()


def _service(request: Request) -> CommenterOverlapService:
    return get_service(
        request,
        "commenters",
        lambda: CommenterOverlapService(request.app.state.services["repos"]),
    )


def _network_service(request: Request) -> CommenterNetworkService:
    return get_service(
        request,
        "commenter_network",
        lambda: CommenterNetworkService(request.app.state.services["repos"]),
    )


def _id_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


_COMMENTER_PROJECTIONS = ("commenter", "co_comment_video", "co_comment_channel", "heterogeneous")


def _resolve_weight(weight: str | None, min_shared: int | None, top_n: int | None) -> str:
    """Validate + merge top-level min_shared/top_n into the weight-spec token."""
    if weight is None:
        weight = "co_comment:jaccard"
    try:
        ws = parse_weight_spec(weight)
    except WeightSpecError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if min_shared is not None:
        ws.params["min_shared"] = min_shared
    if top_n is not None:
        ws.params["top_n"] = top_n
    return ws.to_token()


def _job_run_ids(request: Request, job_ids_param: str | None) -> list[str] | None:
    """Resolve a comma-separated ``job_ids`` filter to the union of those jobs'
    child-run ids (plan-J1 linkage). Unknown job ids resolve to no runs, which
    keeps the AND semantics with any explicit ``run_ids`` intact."""
    ids = [j.strip() for j in (job_ids_param or "").split(",") if j.strip()]
    if not ids:
        return None
    wanted = set(ids)
    repos = request.app.state.services["repos"]
    return [
        run.run_id for run in repos.runs.list_runs() if getattr(run, "job_id", None) in wanted
    ]


def _resolve_run_scope(
    request: Request, run_ids_param: str | None, job_ids_param: str | None
) -> list[str] | None:
    """Combine ``run_ids`` and ``job_ids`` into a single run scope (AND when both
    are given: the intersection of explicit runs with the job's runs)."""
    run_ids = _id_list(run_ids_param)
    job_runs = _job_run_ids(request, job_ids_param)
    if job_runs is None:
        return run_ids or None
    if run_ids:
        return sorted(set(run_ids) & set(job_runs)) or None
    return job_runs or None


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
    "/network/commenters/graph",
    tags=["network"],
    response_model=CommenterNetworkGraph,
)
def commenter_network_graph(
    request: Request,
    video_ids: str | None = Query(
        None, description="Comma-separated video ids (at least one of video_ids/channel_ids/run_ids)"
    ),
    channel_ids: str | None = Query(None, description="Comma-separated channel ids"),
    run_ids: str | None = Query(None, description="Comma-separated collection run ids"),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; the scope becomes the union "
        "of those jobs' child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query(
        "commenter",
        description="commenter | co_comment_video | co_comment_channel | heterogeneous",
    ),
    weight: str | None = Query(
        None,
        description="co_comment weight spec, e.g. co_comment:jaccard:min_shared=2:norm=min_max. "
        "See GET /network/weights/options. Unknown spec -> 400.",
    ),
    min_shared: int | None = Query(None, ge=1, description="Override weight spec min_shared"),
    top_n: int | None = Query(None, ge=1, le=1000, description="Override weight spec top_n fan-out cap"),
    weighted: bool = Query(True, description="Use the spec's weights for community/centrality math"),
):
    """Audience (commenter) network graph for the chosen projection + scope (N2/WS7).

    Returns enriched nodes (kind = commenter|video|channel, community_id,
    degree) and weighted edges carrying the active ``weight_spec``. The same
    scan drives every audience endpoint so the graph, metrics and export always
    agree.
    """
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).graph(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
    )


@router.get(
    "/network/commenters/metrics",
    tags=["network"],
    response_model=CommenterNetworkMetrics,
)
def commenter_network_metrics(
    request: Request,
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
):
    """Audience-network aggregate statistics + bridge / core / prolific ranks (N2/WS7).

    modularity (louvain seed=42), community count, density, clustering and the
    top bridge audiences (betweenness), core audiences (eigenvector) and most
    prolific commenters -- the WS7 audience-duplication readout.
    """
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).metrics(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
    )


@router.get(
    "/network/commenters/roles",
    tags=["network"],
)
def commenter_network_roles(
    request: Request,
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
    role_model: str = Query("core_broker_periphery_bridge"),
):
    """Structural roles for the audience graph (N3): core / broker / bridge / periphery."""
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).roles(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
        role_model=role_model,
    )


@router.get(
    "/network/commenters/community-insights",
    tags=["network"],
)
def commenter_network_community_insights(
    request: Request,
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
):
    """Per-community composition for the audience graph (N3)."""
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).community_insights(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
    )


@router.get(
    "/network/commenters/communities",
    tags=["network"],
)
def commenter_network_communities(
    request: Request,
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
    min_size: int = Query(1, ge=1),
):
    """Communities as graph entities for the audience network: member node-ids (N4)."""
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).communities(
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
        min_size=min_size,
    )


@router.get(
    "/network/commenters/export",
    tags=["network"],
)
def commenter_network_export(
    request: Request,
    format: str = Query("graphml"),
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
):
    """Download the audience network (graphml/edgelist/gexf/csv/json/xlsx).

    Mirrors ``GET /network/commenters/graph`` for the same filters and reuses the
    recommendation serializers (``relationship_type`` carries ``co_comment``).
    Unknown formats -> 400.
    """
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    if format not in ("graphml", "edgelist", "gexf", "csv", "json", "xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    try:
        filename, content, media_type = _network_service(request).export_network(
            format=format,
            video_ids=_id_list(video_ids),
            channel_ids=_id_list(channel_ids),
            run_ids=_resolve_run_scope(request, run_ids, job_ids),
            projection=projection,
            weight=spec,
            weighted=weighted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/network/commenters/{handle}/detail",
    tags=["network"],
)
def commenter_network_detail(
    request: Request,
    handle: str,
    video_ids: str | None = Query(None),
    channel_ids: str | None = Query(None),
    run_ids: str | None = Query(None),
    job_ids: str | None = Query(
        None,
        description="Comma-separated collection-job ids; scope = union of those jobs' "
        "child runs (AND-combined with run_ids when both given).",
    ),
    projection: str = Query("commenter"),
    weight: str | None = Query(None),
    min_shared: int | None = Query(None, ge=1),
    top_n: int | None = Query(None, ge=1, le=1000),
    weighted: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
):
    """Identify a commenter and read their comments within the audience scope (N-fix).

    Returns the resolved label/kind, total comment count, the videos/channels
    they commented on (with titles), and up to ``limit`` sampled comment texts
    (each with its publishing video + channel) so clicking a node shows real
    evidence, not the video-style drawer.
    """
    if projection not in _COMMENTER_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {_COMMENTER_PROJECTIONS}",
        )
    spec = _resolve_weight(weight, min_shared, top_n)
    return _network_service(request).commenter_detail(
        handle,
        video_ids=_id_list(video_ids),
        channel_ids=_id_list(channel_ids),
        run_ids=_resolve_run_scope(request, run_ids, job_ids),
        projection=projection,
        weight=spec,
        weighted=weighted,
        limit=limit,
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
