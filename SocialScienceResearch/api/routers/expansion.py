"""Network-expansion router (docs/network_expansion_scrape_all.md §4.4).

Endpoints for the one-hop recommendation expansion of the network:

* ``POST /network/expansion/scrape-video`` - expand ONE video (job-backed);
* ``POST /network/expansion/scrape-all`` - expand the current network slice
  (job-backed);
* ``GET /network/expansion`` - paginated expansion-action anchors;
* ``GET /network/expansion/{action_id}`` - one action payload;
* ``GET /network/expansion/{action_id}/stats`` - overall + per-video stats;
* ``GET /network/expansion/{action_id}/graph`` - the action's graph
  (video|channel projection).

Every action auto-creates a Project that organizes its runs + datasets, and is
stored as a :class:`LayerRun` anchor marked ``config_json["expansion"]`` (kept
separate from crawl layers). Validation errors surface as ``invalid_argument``
(the app-level ``ValueError`` handler); unknown actions are ``404``.

Owned by the graph-rag-agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.api.routers.common import get_service, paginated
from SocialScienceResearch.api.schemas import (
    ExpansionScrapeAllRequest,
    ExpansionScrapeVideoRequest,
    JobSubmitPayload,
)
from SocialScienceResearch.domain.layer_models import (
    ExpansionActionPayload,
    ExpansionStats,
    ScrapeFilters,
)
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services.network_analytics_service import (
    ChannelGraphPayload,
    NetworkAnalyticsService,
    NetworkGraph,
)
from SocialScienceResearch.services.pagination import Paginated

router = APIRouter()

DEFAULT_PAGE_SIZE = 50

_ALLOWED_PROJECTIONS = ("video", "channel")


def _service(request: Request) -> LayerScrapeService:
    return get_service(
        request,
        "layer_scrape",
        lambda: LayerScrapeService(
            request.app.state.services["recommendations"]._provider,
            request.app.state.services["repos"],
            settings=request.app.state.settings,
        ),
    )


def _analytics(request: Request) -> NetworkAnalyticsService:
    return get_service(
        request,
        "network_analytics",
        lambda: NetworkAnalyticsService(request.app.state.services["repos"]),
    )


def _require_action(
    service: LayerScrapeService, action_id: str
):
    """Return the expansion anchor or raise a 404."""
    layer = service.get_expansion(action_id)
    if layer is None:
        raise HTTPException(
            status_code=404, detail=f"Expansion action {action_id} not found"
        )
    return layer


def _require_projection(projection: str) -> None:
    if projection not in _ALLOWED_PROJECTIONS:
        raise ValueError(
            f"projection must be one of {', '.join(_ALLOWED_PROJECTIONS)}"
        )


def _action_key(action) -> tuple[str, ...]:
    """Newest action first (descending ``started_at``)."""
    return (f"{-int(action.started_at.timestamp()):020d}", action.action_id)


@router.post(
    "/network/expansion/scrape-video",
    tags=["network"],
    response_model=JobSubmitPayload,
)
def expansion_scrape_video(request: Request, body: ExpansionScrapeVideoRequest):
    """Queue a one-hop expansion of a single video (job id).

    Poll ``GET /jobs/{job_id}``; on success the action anchor appears in
    ``GET /network/expansion`` with its auto-created Project.

    The video need not be a deep-enriched ``Video`` row yet - a recommended
    target that exists only as a graph node is extracted and persisted on the
    fly by the job, mirroring the scrape-all expansion.
    """
    _require_projection(body.filters.projection)
    service = _service(request)
    jobs = request.app.state.services["jobs"]
    filters = body.filters

    def _worker(reporter):
        return service.expand_video(
            body.video_id, filters=filters, reporter=reporter
        )

    job = jobs.submit(_worker, kind="expansion")
    return {"job_id": job.job_id}


@router.post(
    "/network/expansion/scrape-all",
    tags=["network"],
    response_model=JobSubmitPayload,
)
def expansion_scrape_all(request: Request, body: ExpansionScrapeAllRequest):
    """Queue a one-hop expansion of the current network slice (job id).

    The scope is an explicit ``video_ids`` list, or a ``run_id`` whose videos/
    sources form the slice. ``ValueError`` (no scope / unknown run) maps to a
    400 by the app-level handler.
    """
    _require_projection(body.filters.projection)
    service = _service(request)
    if not body.video_ids and not body.run_id:
        raise ValueError("Expansion scope requires video_ids or run_id")
    if body.run_id and service._repos.runs.get_run(body.run_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Run {body.run_id} not found"
        )
    jobs = request.app.state.services["jobs"]
    filters = body.filters

    def _worker(reporter):
        return service.expand_all_videos(
            body.video_ids,
            filters=filters,
            parent_run_id=body.run_id,
            reporter=reporter,
        )

    job = jobs.submit(_worker, kind="expansion")
    return {"job_id": job.job_id}


@router.get(
    "/network/expansion",
    tags=["network"],
    response_model=Paginated[ExpansionActionPayload],
)
def list_expansions(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Paginated network-expansion actions, newest first."""
    service = _service(request)
    actions = service.list_expansions()
    payloads = [service.expansion_payload(action) for action in actions]
    return paginated(payloads, cursor=cursor, page_size=page_size, key=_action_key)


@router.get(
    "/network/expansion/options",
    tags=["network"],
    response_model=ScrapeFilters,
)
def expansion_options():
    """The default expansion filters (drives the UI filter dialog)."""
    return ScrapeFilters()


@router.get(
    "/network/expansion/{action_id}",
    tags=["network"],
    response_model=ExpansionActionPayload,
)
def get_expansion(request: Request, action_id: str):
    """One network-expansion action anchor (counts, filters, project id)."""
    service = _service(request)
    layer = _require_action(service, action_id)
    return service.expansion_payload(layer)


@router.get(
    "/network/expansion/{action_id}/stats",
    tags=["network"],
    response_model=ExpansionStats,
)
def expansion_stats(request: Request, action_id: str):
    """Overall + per-video statistics for one expansion action."""
    service = _service(request)
    layer = _require_action(service, action_id)
    return service.expansion_stats(layer)


@router.get(
    "/network/expansion/{action_id}/graph",
    tags=["network"],
    response_model=NetworkGraph | ChannelGraphPayload,
)
def expansion_graph(
    request: Request,
    action_id: str,
    projection: str = Query("video", description="video | channel"),
):
    """The expansion action's graph in the requested projection."""
    _require_projection(projection)
    service = _service(request)
    layer = _require_action(service, action_id)
    analytics = _analytics(request)
    if projection == "channel":
        return analytics.channel_graph(run_ids=layer.run_ids)
    return analytics.graph(run_ids=layer.run_ids)