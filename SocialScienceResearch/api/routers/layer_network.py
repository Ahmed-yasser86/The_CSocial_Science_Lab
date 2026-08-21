"""Layer-crawl network router (docs/analysis_next_layer_scrape.md §6).

Endpoints for bootstrapping a layer crawl, scraping the next layer (job-backed),
listing/reading the ``LayerRun`` anchors and serving the layer-scoped graph in
both projections (video / channel). Keeps ``api/routers/network_ext.py``
focused on the global network views.

Routes (all under the configured API prefix):

* ``POST /network/layer`` - bootstrap layer 0 from a seed run;
* ``POST /network/layer/scrape`` - queue the next crawl layer (job id);
* ``GET /network/layers`` - paginated ``LayerRun`` list (newest layer first);
* ``GET /network/layer/{layer_run_id}`` - one layer anchor + counts;
* ``GET /network/layer/{layer_run_id}/relations`` - NewRelationsReport;
* ``GET /network/layer/{layer_run_id}/graph`` - video|channel projection;
* ``GET /network/layer/{layer_run_id}/frontier`` - the frontier for the stepper.

Owned by the layer-scrape module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.api.routers.common import get_service, paginated
from SocialScienceResearch.api.schemas import (
    JobSubmitPayload,
    LayerBootstrapRequest,
    LayerScrapeRequest,
)
from SocialScienceResearch.domain.layer_models import (
    LayerFrontier,
    LayerRun,
    LayerRunPayload,
    NewRelationsReport,
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


def _analytics(request: Request) -> NetworkAnalyticsService:
    return get_service(
        request,
        "network_analytics",
        lambda: NetworkAnalyticsService(request.app.state.services["repos"]),
    )


def _layer_payload(layer: LayerRun) -> LayerRunPayload:
    return LayerRunPayload(**layer.model_dump(mode="json"))


def _require_layer(service: LayerScrapeService, layer_run_id: str) -> LayerRun:
    layer = service.get_layer(layer_run_id)
    if layer is None:
        raise HTTPException(
            status_code=404, detail=f"Layer run {layer_run_id} not found"
        )
    return layer


def _require_projection(projection: str) -> None:
    if projection not in _ALLOWED_PROJECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"projection must be one of {', '.join(_ALLOWED_PROJECTIONS)}",
        )


def _layer_key(layer: LayerRun) -> tuple[str, ...]:
    """Sort key: newest layer first (descending ``layer_index``)."""
    return (f"{-layer.layer_index:08d}", layer.layer_run_id)


@router.post(
    "/network/layer",
    tags=["network"],
    response_model=LayerRunPayload,
)
def bootstrap_layer(request: Request, body: LayerBootstrapRequest):
    """Create the seed ``LayerRun`` (layer 0) from an existing run.

    The frontier is the run's own videos/sources; no network work happens.
    Idempotent per seed run.
    """
    _require_projection(body.projection)
    service = _layer_service(request)
    return _layer_payload(
        service.bootstrap_layer(body.run_id, projection=body.projection)
    )


@router.post(
    "/network/layer/scrape",
    tags=["network"],
    response_model=JobSubmitPayload,
)
def layer_scrape(request: Request, body: LayerScrapeRequest):
    """Queue the next crawl layer as a background job.

    Mirrors the other ``/network/scrape/*`` endpoints: submit to the job
    manager, poll ``GET /jobs/{job_id}``, fetch the layer + relations on
    success.
    """
    _require_projection(body.projection)
    service = _layer_service(request)
    repos = request.app.state.services["repos"]
    if body.parent_layer_run_id and service.get_layer(body.parent_layer_run_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Layer run {body.parent_layer_run_id} not found"
        )
    if body.parent_run_id and repos.runs.get_run(body.parent_run_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Run {body.parent_run_id} not found"
        )
    jobs = request.app.state.services["jobs"]

    def _worker(reporter):
        return service.scrape_next_layer(
            parent_layer_run_id=body.parent_layer_run_id,
            parent_run_id=body.parent_run_id,
            projection=body.projection,
            collect_comments=body.collect_comments,
            concurrency=body.concurrency,
            reporter=reporter,
        )

    job = jobs.submit(_worker, kind="layer")
    return {"job_id": job.job_id}


@router.get(
    "/network/layers",
    tags=["network"],
    response_model=Paginated[LayerRunPayload],
)
def list_layers(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Paginated crawl layers, newest layer first (``layer_index`` desc)."""
    layers = _layer_service(request).list_layers()
    return paginated(
        layers,
        cursor=cursor,
        page_size=page_size,
        key=_layer_key,
    )


@router.get(
    "/network/layer/{layer_run_id}",
    tags=["network"],
    response_model=LayerRunPayload,
)
def get_layer(request: Request, layer_run_id: str):
    """One crawl layer anchor (frontier, discovered ids, run ids, counts)."""
    layer = _require_layer(_layer_service(request), layer_run_id)
    return _layer_payload(layer)


@router.get(
    "/network/layer/{layer_run_id}/relations",
    tags=["network"],
    response_model=NewRelationsReport,
)
def layer_relations(request: Request, layer_run_id: str):
    """The NewRelationsReport (what did this crawl add?) for a layer."""
    service = _layer_service(request)
    _require_layer(service, layer_run_id)
    report = service.relation_report(layer_run_id)
    if report is None:
        raise HTTPException(
            status_code=404, detail=f"Layer run {layer_run_id} not found"
        )
    return report


@router.get(
    "/network/layer/{layer_run_id}/graph",
    tags=["network"],
    response_model=NetworkGraph | ChannelGraphPayload,
)
def layer_graph(
    request: Request,
    layer_run_id: str,
    projection: str = Query("video", description="video | channel"),
):
    """The layer's graph in the requested projection.

    Layer 0 (a seed with no scraped edges) is served as the seed run's slice
    (``run_id`` scoping); deeper layers are scoped by ``layer_index`` so the
    researcher sees exactly what that crawl added.
    """
    _require_projection(projection)
    layer = _require_layer(_layer_service(request), layer_run_id)
    analytics = _analytics(request)
    if layer.layer_index == 0 and layer.parent_run_id:
        run_id, layer_index = layer.parent_run_id, None
    else:
        run_id, layer_index = None, layer.layer_index
    if projection == "channel":
        return analytics.channel_graph(run_id=run_id, layer_index=layer_index)
    return analytics.graph(run_id=run_id, layer_index=layer_index)


@router.get(
    "/network/layer/{layer_run_id}/frontier",
    tags=["network"],
    response_model=LayerFrontier,
)
def layer_frontier(request: Request, layer_run_id: str):
    """The frontier of a layer (drives the UI layer stepper)."""
    service = _layer_service(request)
    _require_layer(service, layer_run_id)
    frontier = service.get_layer_frontier(layer_run_id)
    if frontier is None:
        raise HTTPException(
            status_code=404, detail=f"Layer run {layer_run_id} not found"
        )
    return frontier
