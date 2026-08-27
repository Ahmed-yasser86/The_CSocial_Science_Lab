"""B6: Full network analytics router.

Endpoints for network-wide metrics, temporal slices, paginated edges and
graph exports (graphml/edgelist/gexf). Extends RecommendationGraphService;
backed by ``NetworkAnalyticsService`` (lazily built on ``app.state`` via
:func:`get_service`).

Routes (all under the configured API prefix):

* ``GET /network/metrics`` - aggregate network statistics;
* ``GET /network/temporal`` - per-run slices + consecutive-run growth;
* ``GET /network/edges`` - cursor-paginated edge listing;
* ``GET /network/export`` - graphml/edgelist/gexf download;
* ``POST /network/export-to-project`` - persist a scoped network export as a
  ProjectItem artifact under a Project;
* ``POST /network/merge`` - overlap + combined SNA statistics for two scopes;
* ``GET /network/merge/options`` - picker payload of runs + expansions;
* ``GET /network/channels`` - lightweight channel projection;
* ``GET /network/centralities`` - per-node centrality battery (degree/closeness/
  eigenvector/betweenness + community_id) for the rendered graph slice.
* ``GET /network/weights/options`` - catalog of legal ``edge_type × weight_mode``
  weight specs with per-scope availability (drives the weight dropdown).

Owned by the B6 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from SocialScienceResearch.api.routers.common import get_service, paginated
from SocialScienceResearch.api.schemas import (
    NetworkExportToProjectRequest,
    NetworkMergeRequest,
    NetworkScopeRequest,
)
from SocialScienceResearch.domain.dataset_models import ProjectItem
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services.network_matrix_service import NetworkMatrixService
from SocialScienceResearch.services.sampling_service import SamplingService
from SocialScienceResearch.services.network_analytics_service import (
    ChannelGraphPayload,
    ChannelProjection,
    EdgeRow,
    MergedNetworkResult,
    NetworkAnalyticsService,
    NetworkGraph,
    NetworkMergeOptions,
    NetworkMetrics,
    NetworkScope,
    TemporalResult,
)
from SocialScienceResearch.services.commenter_network_service import (
    CommenterNetworkService,
)
from SocialScienceResearch.services.weight_spec import weight_options_catalog
from SocialScienceResearch.services.pagination import Paginated
from SocialScienceResearch.services.project_item_service import ProjectItemService
from SocialScienceResearch.utils.idgen import utcnow

router = APIRouter()

DEFAULT_PAGE_SIZE = 50

EXPORT_FORMATS = {"graphml", "edgelist", "gexf", "csv", "json", "xlsx"}


def _service(request: Request) -> NetworkAnalyticsService:
    return get_service(
        request,
        "network_analytics",
        lambda: NetworkAnalyticsService(request.app.state.services["repos"]),
    )


def _layer_service(request: Request) -> LayerScrapeService:
    return get_service(
        request,
        "layer_scrape",
        lambda: LayerScrapeService(
            request.app.state.services["recommendations"]._provider,
            request.app.state.services["repos"],
            settings=request.app.state.settings,
        ),
    )


def _items_service(request: Request) -> ProjectItemService:
    return get_service(
        request,
        "project_items",
        lambda: ProjectItemService(request.app.state.services["repos"]),
    )


def _matrix_service(request: Request) -> NetworkMatrixService:
    return get_service(
        request,
        "network_matrix",
        lambda: NetworkMatrixService(request.app.state.services["repos"]),
    )


def _sampling_service(request: Request) -> SamplingService:
    return get_service(
        request,
        "sampling",
        lambda: SamplingService(request.app.state.services["repos"]),
    )


def _resolve_scope(
    request: Request, scope: NetworkScopeRequest
) -> NetworkScope:
    """Normalize a request scope: ``action_id`` -> its expansion runs."""
    if scope.action_id:
        layer = _layer_service(request).get_expansion(scope.action_id)
        if layer is None:
            raise ValueError(f"Expansion action {scope.action_id!r} not found")
        return NetworkScope(
            run_id=None,
            run_ids=list(layer.run_ids),
            video_ids=list(scope.video_ids),
        )
    return NetworkScope(
        run_id=scope.run_id,
        run_ids=[],
        video_ids=list(scope.video_ids),
    )


def _job_run_ids(request: Request, job_ids_param: str | None) -> list[str] | None:
    """Resolve a comma-separated ``job_ids`` filter to the UNION of those
    jobs' child-run ids (plan-J1 linkage; unknown job ids resolve to no runs,
    which keeps the AND semantics of the other filters intact)."""
    ids = [j.strip() for j in (job_ids_param or "").split(",") if j.strip()]
    if not ids:
        return None
    wanted = set(ids)
    repos = request.app.state.services["repos"]
    return [
        run.run_id for run in repos.runs.list_runs() if run.job_id in wanted
    ]


def _scope_request(body) -> NetworkScopeRequest:
    """Project the export/merge body's scope fields onto a scope request."""
    return NetworkScopeRequest(
        run_id=body.run_id,
        action_id=body.action_id,
        video_ids=list(body.video_ids),
    )


def _scope_label(scope: NetworkScopeRequest, action_id: str | None) -> str:
    if scope.run_id:
        return f"run {scope.run_id}"
    if action_id:
        return f"expansion {action_id}"
    if scope.video_ids:
        return f"{len(scope.video_ids)} video(s)"
    return "all edges"


def _edge_key(edge) -> tuple[str, ...]:
    """Feed-rank pagination key: source video, position, then identity.

    Positions are zero-padded so string comparison mirrors numeric order and
    ``None`` (unknown rank) sorts after ranked edges. All keys are strings so
    cursor tokens remain comparable inside ``page_sorted``.
    
    Handles both dict and EdgeRow objects.
    """
    # Handle both dict and EdgeRow objects
    if hasattr(edge, "__dict__"):
        # EdgeRow object
        position = edge.position
        position_key = f"{position:08d}" if position is not None else "~"
        return (
            edge.source_video_id,
            position_key,
            edge.run_id or "",
            edge.recommended_video_id,
        )
    else:
        # dict
        position = edge["position"]
        position_key = f"{position:08d}" if position is not None else "~"
        return (
            edge["source_video_id"],
            position_key,
            edge["run_id"] or "",
            edge["recommended_video_id"],
        )


@router.get(
    "/network/metrics",
    tags=["network"],
    response_model=NetworkMetrics,
)
def network_metrics(
    request: Request,
    run_id: str | None = Query(None),
    top_n: int = Query(10, ge=1, le=500),
):
    """Aggregate statistics for the whole recommendation network (or a run)."""
    return _service(request).metrics(run_id=run_id, top_n=top_n)


@router.get(
    "/network/graph",
    tags=["network"],
    response_model=NetworkGraph | ChannelGraphPayload,
)
def network_graph(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None, description="Filter edges by a single channel_id"),
    channel_ids: str | None = Query(None, description="Comma-separated channel_ids (multi-channel filter)"),
    video_ids: str | None = Query(None, description="Comma-separated video_ids (multi-video ego filter)"),
    channel_scope: str = Query(
        "source",
        description="Which edge endpoint a channel filter matches: source|target|either",
    ),
    projection: str = Query(
        "video",
        description="Graph projection: video | channel",
    ),
    layer_index: int | None = Query(
        None,
        ge=0,
        description="Limit the slice to a single crawl layer (None = all layers)",
    ),
    connected: str | None = Query(
        None,
        description="Node filter: 'only' shows only connected nodes, 'isolated' shows only isolated nodes (None = all)",
    ),
    scraped: str | None = Query(
        None,
        description="Node filter by recommendation-scrape state: 'scraped' | 'unscraped' | None = all",
    ),
    include_sub_runs: bool = Query(
        False,
        description="When a run_id is given, also fold in every descendant sub-run "
        "(the full run lineage) instead of just the selected run's own edges.",
    ),
    job_ids: str | None = Query(
        None,
        description="Comma-separated job ids: the run scope becomes the union of "
        "those jobs' child runs (AND-combined with any run scope).",
    ),
    weight: str | None = Query(
        None,
        description="Weight spec token, e.g. `recommendation:observation_count` "
        "(default behaviour) or `recommendation:reciprocal_position:min_max`. "
        "See GET /network/weights/options. Unknown spec -> 400.",
    ),
):
    """Enriched node/edge payload for the interactive graph UI.

    Nodes carry composite labels (``[ID] + Channel Name + Video Title +
    thumbnails/metrics``) plus degree/kind/provenance; the response includes
    run and channel facets so the filter bar never derives options from the
    rendered graph. ``projection=channel`` collapses the video network into
    a channel-level graph (channels as nodes, weighted edges between them).

    Advanced selection:
    - ``layer_index`` limits the slice to one crawl layer.
    - ``connected=only`` keeps nodes that participate in at least one edge;
      ``connected=isolated`` keeps only isolated nodes (they render detached).
    - ``scraped=scraped`` keeps only nodes whose recommendation feed has been
      scraped; ``scraped=unscraped`` keeps only nodes never scraped (the
      candidates for a next expansion).
    """
    if projection not in ("video", "channel"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="projection must be video or channel")
    if channel_scope not in ("source", "target", "either"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="channel_scope must be source, target or either")
    if connected not in (None, "only", "isolated"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="connected must be only or isolated")
    if scraped not in (None, "scraped", "unscraped"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="scraped must be scraped or unscraped")
    if weight is not None:
        from fastapi import HTTPException
        from SocialScienceResearch.services.weight_spec import (
            WeightSpecError,
            parse_weight_spec,
        )

        try:
            parse_weight_spec(weight)
        except WeightSpecError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    service = _service(request)
    parsed_channel_ids = (
        [c for c in (p.strip() for p in (channel_ids or "").split(",")) if c]
        if channel_ids
        else None
    )
    parsed_video_ids = (
        [v for v in (p.strip() for p in (video_ids or "").split(",")) if v]
        if video_ids
        else None
    )
    channel_filter_ids = parsed_channel_ids or (
        [channel_id] if channel_id else None
    )
    # "Include sub-runs" expands a selected run into its full lineage so the
    # graph shows the parent run together with every descendant it spawned.
    # We resolve the family once and pass it as run_ids (with run_id cleared so
    # the slice isn't double-filtered against only the parent).
    if include_sub_runs and run_id:
        family_ids = service.run_family(run_id)
        run_id = None
    else:
        family_ids = None
    # Optional job scope: resolve job ids to the union of their child runs.
    # AND semantics are preserved: when a run scope is also present the two
    # scopes are intersected, and every other filter still applies on top.
    # An empty intersection must stay an empty slice (never "all runs"),
    # hence the never-matching sentinel id.
    job_scope = _job_run_ids(request, job_ids)
    if job_scope is not None:
        base: set[str] | None = None
        if family_ids is not None:
            base = set(family_ids)
        elif run_id:
            base = {run_id}
        combined = sorted(base & set(job_scope)) if base else list(job_scope)
        run_id = None
        family_ids = combined or ["__no_matching_run__"]
    if projection == "channel":
        return service.channel_graph(
            run_id=run_id,
            run_ids=family_ids,
            channel_id=channel_id,
            channel_ids=channel_filter_ids,
            channel_scope=channel_scope,
            layer_index=layer_index,
        )
    return service.graph(
        run_id=run_id,
        run_ids=family_ids,
        channel_id=channel_id,
        channel_ids=channel_filter_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        connected=connected,
        scraped=scraped,
        video_ids=parsed_video_ids,
        weight_spec=weight,
    )


@router.get(
    "/network/centralities",
    tags=["network"],
)
def network_centralities(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None),
    channel_ids: str | None = Query(None),
    channel_scope: str = Query("source"),
    layer_index: int | None = Query(None, ge=0),
    video_ids: str | None = Query(None),
    projection: str = Query("video"),
    weight: str | None = Query(
        None,
        description="Weight spec token (e.g. recommendation:reciprocal_position:"
        "min_max). See GET /network/weights/options. Unknown spec -> 400.",
    ),
    weighted: bool = Query(
        False,
        description="When true and a `weight` spec is supplied, centralities use "
        "the spec's edge weights (eigenvector/betweenness/degree).",
    ),
):
    """Full research-grade centrality battery for the rendered graph slice (N0/N3).

    Returns, per node, ``degree``, ``closeness``, ``eigenvector``, ``betweenness``,
    ``pagerank``, ``harmonic``, ``constraint`` (Burt), ``effective_size`` (Burt),
    ``bridging`` (normalised betweenness) and ``clustering``, plus ``community_id``.
    The graph-level ``global`` block carries ``assortativity``. When the slice is
    larger than the approximation threshold the ``betweenness``/``bridging`` scores
    are k-sampled and the response is flagged ``approximate: true``.

    Mirrors the scope parsing of ``/network/graph`` so the centralities always
    describe exactly what is on screen.
    """
    from fastapi import HTTPException

    if projection not in ("video", "channel"):
        raise HTTPException(status_code=400, detail="projection must be video or channel")
    if channel_scope not in ("source", "target", "either"):
        raise HTTPException(
            status_code=400,
            detail="channel_scope must be source, target or either",
        )
    service = _service(request)
    if weight is not None:
        from SocialScienceResearch.services.weight_spec import (
            WeightSpecError,
            parse_weight_spec,
        )

        try:
            parse_weight_spec(weight)
        except WeightSpecError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    parsed_channel_ids = (
        [c for c in (p.strip() for p in (channel_ids or "").split(",")) if c]
        if channel_ids
        else None
    )
    parsed_video_ids = (
        [v for v in (p.strip() for p in (video_ids or "").split(",")) if v]
        if video_ids
        else None
    )
    channel_filter_ids = parsed_channel_ids or ([channel_id] if channel_id else None)
    return service.centralities(
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_filter_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        video_ids=parsed_video_ids,
        projection=projection,
        weight_spec=weight,
        weighted=weighted,
    )


def _parse_network_scope(
    *,
    run_id: str | None,
    channel_id: str | None,
    channel_ids: str | None,
    channel_scope: str,
    layer_index: int | None,
    video_ids: str | None,
    projection: str,
    weight: str | None,
    weighted: bool,
    role_model: str | None = None,
) -> dict[str, object]:
    """Validate + normalise the shared ``/network/*`` scope query params."""
    from fastapi import HTTPException

    if projection not in ("video", "channel"):
        raise HTTPException(status_code=400, detail="projection must be video or channel")
    if channel_scope not in ("source", "target", "either"):
        raise HTTPException(
            status_code=400, detail="channel_scope must be source, target or either"
        )
    if weight is not None:
        from SocialScienceResearch.services.weight_spec import (
            WeightSpecError,
            parse_weight_spec,
        )

        try:
            parse_weight_spec(weight)
        except WeightSpecError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    parsed_channel_ids = (
        [c for c in (p.strip() for p in (channel_ids or "").split(",")) if c]
        if channel_ids
        else None
    )
    parsed_video_ids = (
        [v for v in (p.strip() for p in (video_ids or "").split(",")) if v]
        if video_ids
        else None
    )
    channel_filter_ids = parsed_channel_ids or ([channel_id] if channel_id else None)
    kwargs: dict[str, object] = dict(
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_filter_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        video_ids=parsed_video_ids,
        projection=projection,
        weight_spec=weight,
        weighted=weighted,
    )
    if role_model is not None:
        kwargs["role_model"] = role_model
    return kwargs


@router.get(
    "/network/roles",
    tags=["network"],
)
def network_roles(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None),
    channel_ids: str | None = Query(None),
    channel_scope: str = Query("source"),
    layer_index: int | None = Query(None, ge=0),
    video_ids: str | None = Query(None),
    projection: str = Query("video"),
    weight: str | None = Query(None),
    weighted: bool = Query(False),
    role_model: str = Query("core_broker_periphery_bridge"),
):
    """Structural roles for the rendered slice (N3): core / broker / bridge / periphery."""
    kwargs = _parse_network_scope(
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        video_ids=video_ids,
        projection=projection,
        weight=weight,
        weighted=weighted,
        role_model=role_model,
    )
    return _service(request).roles(**kwargs)


@router.get(
    "/network/community-insights",
    tags=["network"],
)
def network_community_insights(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None),
    channel_ids: str | None = Query(None),
    channel_scope: str = Query("source"),
    layer_index: int | None = Query(None, ge=0),
    video_ids: str | None = Query(None),
    projection: str = Query("video"),
    weight: str | None = Query(None),
    weighted: bool = Query(False),
):
    """Per-community composition (dominant channels, top centralities) for the slice (N3)."""
    kwargs = _parse_network_scope(
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        video_ids=video_ids,
        projection=projection,
        weight=weight,
        weighted=weighted,
    )
    return _service(request).community_insights(**kwargs)


@router.get(
    "/network/communities",
    tags=["network"],
)
def network_communities(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None),
    channel_ids: str | None = Query(None),
    channel_scope: str = Query("source"),
    layer_index: int | None = Query(None, ge=0),
    video_ids: str | None = Query(None),
    projection: str = Query("video"),
    weight: str | None = Query(None),
    weighted: bool = Query(False),
    min_size: int = Query(1, ge=1),
):
    """Communities as graph entities: member node-ids per detected community (N4)."""
    kwargs = _parse_network_scope(
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        video_ids=video_ids,
        projection=projection,
        weight=weight,
        weighted=weighted,
    )
    kwargs["min_size"] = min_size
    return _service(request).communities(**kwargs)


class NetworkScopeInput(BaseModel):
    """One side of a ``/network/test-difference`` comparison (N4b). All fields are
    optional; only the relevant family's fields are used."""

    run_id: str | None = None
    channel_id: str | None = None
    channel_ids: list[str] | None = None
    channel_scope: str = "source"
    layer_index: int | None = None
    video_ids: list[str] | None = None
    projection: str = "video"
    weight: str | None = None
    weighted: bool | None = None
    run_ids: list[str] | None = None
    min_shared: int | None = None
    top_n: int | None = None


class TestDifferenceRequest(BaseModel):
    family: str = "recommendation"
    scope_a: NetworkScopeInput
    scope_b: NetworkScopeInput
    metric: str
    statistic: str = "difference_in_means"
    method: str = "permutation"
    n_iter: int = Field(200, ge=1, le=1000)
    seed: int = 42


@router.post(
    "/network/test-difference",
    tags=["network"],
)
def network_test_difference(request: Request, body: TestDifferenceRequest):
    """Statistical comparison between two network slices (N4b).

    Node-decomposable metrics (``centrality:<m>``, ``avg_clustering``,
    ``transitivity``, ``density``) return a seeded permutation/bootstrap p-value
    and 95% CI; global-only metrics (``modularity``, ``assortativity``) return the
    observed delta with ``p_value=None`` (no fabricated number). Supports both the
    recommendation family and the audience (commenter) family via ``family``.
    """
    a = body.scope_a
    b = body.scope_b
    if body.family == "commenter":
        svc = CommenterNetworkService(request.app.state.services["repos"])

        def commenter_scope(s: NetworkScopeInput) -> dict:
            weighted = s.weighted if s.weighted is not None else True
            projection = s.projection
            if projection == "video":
                projection = "commenter"
            return {
                "video_ids": s.video_ids,
                "channel_ids": s.channel_ids,
                "run_ids": s.run_ids,
                "projection": projection,
                "weight": s.weight,
                "weighted": weighted,
            }

        return svc.test_difference(
            scope_a=commenter_scope(a),
            scope_b=commenter_scope(b),
            metric=body.metric,
            statistic=body.statistic,
            method=body.method,
            n_iter=body.n_iter,
            seed=body.seed,
        )

    if a.projection not in ("video", "channel"):
        raise HTTPException(
            status_code=400, detail="scope_a.projection must be video or channel"
        )
    if b.projection not in ("video", "channel"):
        raise HTTPException(
            status_code=400, detail="scope_b.projection must be video or channel"
        )
    svc = _service(request)

    def rec_scope(s: NetworkScopeInput) -> dict:
        return {
            k: v
            for k, v in {
                "run_id": s.run_id,
                "channel_id": s.channel_id,
                "channel_ids": s.channel_ids,
                "channel_scope": s.channel_scope,
                "layer_index": s.layer_index,
                "video_ids": s.video_ids,
                "projection": s.projection,
                "weight_spec": s.weight,
                "weighted": s.weighted if s.weighted is not None else False,
            }.items()
            if v is not None
        }

    return svc.test_difference(
        scope_a=rec_scope(a),
        scope_b=rec_scope(b),
        metric=body.metric,
        statistic=body.statistic,
        method=body.method,
        n_iter=body.n_iter,
        seed=body.seed,
    )


@router.get(
    "/network/weights/options",
    tags=["network"],
)
def network_weight_options(
    request: Request,
    run_id: str | None = Query(None),
):
    """Catalog of legal weight specs for the active scope (N1).

    Returns every ``edge_type × weight_mode`` combination the network engine
    understands, the normalizations and params each accepts, and a coarse
    per-scope ``available`` flag with ``unavailable_signals`` when the required
    raw data is absent. The UI renders this directly into the weight dropdown
    instead of hardcoding options. The authoritative per-edge coverage is still
    surfaced at computation time via ``weight_provenance.unavailable_signals``.
    """
    repos = request.app.state.services.get("repos")
    return {"options": weight_options_catalog(repos=repos, run_id=run_id)}


@router.get(
    "/network/temporal",
    tags=["network"],
    response_model=TemporalResult,
)
def network_temporal(
    request: Request,
    runs: str = Query(
        "", description="Comma-separated run ids, e.g. runs=a,b,c"
    ),
):
    """Per-run network slices plus growth between consecutive requested runs."""
    run_ids = [r for r in (part.strip() for part in runs.split(",")) if r]
    return _service(request).temporal(run_ids)


@router.get(
    "/network/edges",
    tags=["network"],
    response_model=Paginated[EdgeRow],
)
def network_edges(
    request: Request,
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None, description="Filter edges by channel_id"),
    channel_scope: str = Query(
        "source",
        description="Which edge endpoint a channel filter matches: source|target|either",
    ),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
    job_ids: str | None = Query(
        None,
        description="Comma-separated job ids: the slice becomes the union of those "
        "jobs' child runs (AND-combined with any run_id filter).",
    ),
):
    """Cursor-paginated list of observed recommendation edges.
    
    Supports filtering by `run_id` and `channel_id` (source channel by default).
    """
    if channel_scope not in ("source", "target", "either"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="channel_scope must be source, target or either")
    run_ids_filter = _job_run_ids(request, job_ids)
    if run_ids_filter is not None:
        # AND semantics with an explicit run_id: intersect, never widen. An
        # empty intersection stays an empty slice via a never-matching id.
        if run_id:
            run_ids_filter = [r for r in run_ids_filter if r == run_id]
            run_id = None
        run_ids_filter = run_ids_filter or ["__no_matching_run__"]
    return paginated(
        _service(request).edges(
            run_id=run_id,
            channel_id=channel_id,
            channel_scope=channel_scope,
            run_ids=run_ids_filter,
        ),
        cursor=cursor,
        page_size=page_size,
        key=_edge_key,
    )


@router.get("/network/export", tags=["network"])
def network_export(
    request: Request,
    format: str = Query("graphml"),
    run_id: str | None = Query(None),
    channel_id: str | None = Query(None, description="Filter edges by a single channel_id"),
    channel_ids: str | None = Query(None, description="Comma-separated channel_ids (multi-channel filter)"),
    video_ids: str | None = Query(None, description="Comma-separated video_ids (multi-video ego filter)"),
    channel_scope: str = Query(
        "source",
        description="Which edge endpoint a channel filter matches: source|target|either",
    ),
    projection: str = Query(
        "video",
        description="Graph projection: video | channel",
    ),
    layer_index: int | None = Query(
        None,
        ge=0,
        description="Limit the slice to a single crawl layer (None = all layers)",
    ),
    connected: str | None = Query(
        None,
        description="Node filter: 'only' shows only connected nodes, 'isolated' shows only isolated nodes (None = all)",
    ),
    scraped: str | None = Query(
        None,
        description="Node filter by recommendation-scrape state: 'scraped' | 'unscraped' | None = all",
    ),
    weight: str | None = Query(
        None,
        description="Weight spec token, e.g. `recommendation:observation_count` "
        "(default behaviour) or `recommendation:reciprocal_position:min_max`. "
        "See GET /network/weights/options. Unknown spec -> 400.",
    ),
):
    """Download the *visible* recommendation network as graphml/edgelist/gexf/
    csv/json/xlsx.

    Accepts exactly the same scope/filter parameters as ``GET /network/graph``,
    so the exported file mirrors the Active Filter View: only the nodes and
    edges currently rendered (with channel scoping, layer de-duplication,
    ``connected`` and ``scraped`` pruning) are included - no leaked or orphaned
    nodes.

    Unknown formats / projections raise ``ValueError`` (mapped to a 400).
    """
    if projection not in ("video", "channel"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="projection must be video or channel")
    if channel_scope not in ("source", "target", "either"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="channel_scope must be source, target or either")
    if connected not in (None, "only", "isolated"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="connected must be only or isolated")
    if scraped not in (None, "scraped", "unscraped"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="scraped must be scraped or unscraped")
    if weight is not None:
        from fastapi import HTTPException
        from SocialScienceResearch.services.weight_spec import (
            WeightSpecError,
            parse_weight_spec,
        )

        try:
            parse_weight_spec(weight)
        except WeightSpecError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    parsed_channel_ids = (
        [c for c in (p.strip() for p in (channel_ids or "").split(",")) if c]
        if channel_ids
        else None
    )
    parsed_video_ids = (
        [v for v in (p.strip() for p in (video_ids or "").split(",")) if v]
        if video_ids
        else None
    )
    channel_filter_ids = parsed_channel_ids or ([channel_id] if channel_id else None)
    filename, content, media_type = _service(request).export_network(
        format=format,
        run_id=run_id,
        channel_id=channel_id,
        channel_ids=channel_filter_ids,
        channel_scope=channel_scope,
        layer_index=layer_index,
        connected=connected,
        scraped=scraped,
        video_ids=parsed_video_ids,
        projection=projection,
        weight_spec=weight,
    )
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/network/export-to-project",
    tags=["network"],
    response_model=ProjectItem,
)
def network_export_to_project(body: NetworkExportToProjectRequest, request: Request):
    """Persist a scoped video network export as a ProjectItem artifact.

    Serializes the network slice (``run_id`` / ``action_id`` / ``video_ids``,
    or the whole persisted network when no scope is given) via
    ``NetworkAnalyticsService.export_network`` and stores the artifact file
    under ``{data_dir}/network_exports/``, tracked by a new ProjectItem
    (``item_type="mixed"``, naming mirrors the network-expansion auto-project
    convention). Returns the created ProjectItem.
    """
    fmt = (body.format or "graphml").strip().lower()
    if fmt not in EXPORT_FORMATS:
        raise ValueError(
            f"Unsupported export format {fmt!r}; expected one of "
            f"{sorted(EXPORT_FORMATS)}"
        )
    scope = _resolve_scope(request, _scope_request(body))
    filename, content, _ = _service(request).export_network(
        fmt,
        run_id=scope.run_id,
        run_ids=scope.run_ids or None,
        video_ids=scope.video_ids or None,
        channel_id=body.channel_id,
        channel_ids=body.channel_ids or None,
        channel_scope=body.channel_scope,
        layer_index=body.layer_index,
        connected=body.connected,
        scraped=body.scraped,
        projection=body.projection,
    )

    now = utcnow()
    label = _scope_label(_scope_request(body), body.action_id)
    name = body.name or f"Network export · {label} · {now.strftime('%Y-%m-%d %H:%M')}"
    description = body.description or (
        f"Exported video network ({label}) as {fmt}. "
        f"Scope: run_id={scope.run_id or ''}, run_ids={scope.run_ids}, "
        f"video_ids={scope.video_ids}."
    )
    artifact_dir = Path(request.app.state.settings.repository.data_dir)
    item = _items_service(request).create_artifact_item(
        body.project_id,
        name=name,
        description=description,
        tags=[
            tag
            for tag in [
                "network_export",
                f"format:{fmt}",
                f"run_id:{scope.run_id}" if scope.run_id else "scope:all",
                f"action_id:{body.action_id}" if body.action_id else None,
                f"video_ids:{len(scope.video_ids)}" if scope.video_ids else None,
            ]
            if tag is not None
        ],
        artifact_filename=filename,
        artifact_content=content,
        artifact_dir=artifact_dir,
    )
    return item


@router.post(
    "/network/merge",
    tags=["network"],
    response_model=MergedNetworkResult,
)
def network_merge(body: NetworkMergeRequest, request: Request):
    """Merge two video-network scopes: overlap + combined SNA statistics.

    Reports shared/exclusive node & edge counts with Jaccard coefficients
    (``None`` when the union is empty - never fabricated as 0) and the SNA
    statistics of the union graph (density, reciprocity, degree distribution,
    components, communities/modularity, top labeled degree nodes) plus the
    enriched union nodes/edges.
    """
    scope_a = _resolve_scope(request, body.scope_a)
    scope_b = _resolve_scope(request, body.scope_b)
    if scope_a.is_empty() and scope_b.is_empty():
        raise ValueError("merge requires at least one non-empty scope")
    return _service(request).merge_networks(scope_a, scope_b, top_n=body.top_n)


@router.get(
    "/network/merge/options",
    tags=["network"],
    response_model=NetworkMergeOptions,
)
def network_merge_options(request: Request):
    """Runs + expansion actions usable as merge scopes (UI picker)."""
    return _service(request).merge_options()


@router.get(
    "/network/channels",
    tags=["network"],
    response_model=ChannelProjection,
)
def network_channels(request: Request, run_id: str | None = Query(None)):
    """Lightweight channel projection: distinct channels seen on edges."""
    return _service(request).channel_projection(run_id=run_id)


@router.get(
    "/network/matrices",
    tags=["network"],
)
def network_matrices(
    request: Request,
    channel_ids: str | None = Query(
        None, description="Comma-separated channel ids (community matrix)"
    ),
    run_ids: str | None = Query(
        None, description="Comma-separated run ids (layer matrix)"
    ),
    top_n: int = Query(50, ge=1, le=500, description="Max rows"),
):
    """Structural matrices for science reporting (US-60/61).

    * ``community_matrix`` - channel x channel shared-commenter counts.
    * ``layer_matrix`` - recommendation-edge structure per crawl layer.
    """
    svc = _matrix_service(request)
    community = svc.community_matrix(
        channel_ids=[c for c in (channel_ids or "").split(",") if c] or None,
        top_n=top_n,
    )
    layer = svc.layer_matrix(
        run_ids=[r for r in (run_ids or "").split(",") if r] or None,
        top_n=top_n,
    )
    return {"community_matrix": community, "layer_matrix": layer}


@router.get(
    "/network/sampling-feasibility",
    tags=["network"],
)
def network_sampling_feasibility(
    request: Request,
    entity_type: str = Query(..., description="'video' | 'comment'"),
    channel_id: str | None = Query(None),
    run_ids: str | None = Query(None, description="Comma-separated run ids"),
    metric: str | None = Query(
        None, description="views | likes | comments"
    ),
    requested_size: int | None = Query(None, ge=0),
):
    """Pre-sample planning (US-32/33): is the requested sample feasible?

    Reports population size, metric availability/coverage, and a recommended
    capped sample size before any sampling is performed.
    """
    svc = _sampling_service(request)
    return svc.feasibility(
        entity_type,
        channel_id=channel_id,
        run_ids=[r for r in (run_ids or "").split(",") if r] or None,
        metric=metric,
        requested_size=requested_size,
    )