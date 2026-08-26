"""Echo-chamber detector router (echo_chamber_detector_plan.md §4).

Endpoints (all under the configured API prefix):

* ``POST /echo-chamber/detect``       - start a detection job;
* ``GET  /echo-chamber``              - paginated detection list;
* ``GET  /echo-chamber/{id}``         - status + per-layer timeline + score;
* ``POST /echo-chamber/{id}/continue``- append more layers (cap 10);
* ``POST /echo-chamber/{id}/stop``    - cooperative stop between layers.

Owned by the echo-detector module agent. Do NOT edit ``api/app.py`` from
here; the router is included by ``create_app`` like the other phase routers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.api.schemas import (
    EchoContinueRequest,
    EchoDetectRequest,
    EchoDetectionStartPayload,
    JobSubmitPayload,
)
from SocialScienceResearch.domain.echo_models import EchoDetection
from SocialScienceResearch.services.echo_chamber_service import EchoChamberService
from SocialScienceResearch.services.pagination import Paginated, page_sorted

router = APIRouter()

DEFAULT_PAGE_SIZE = 50


def _echo_service(request: Request) -> EchoChamberService:
    return get_service(
        request,
        "echo",
        lambda: EchoChamberService(
            request.app.state.services["recommendations"]._provider,
            request.app.state.services["repos"],
            settings=request.app.state.settings,
            jobs=request.app.state.services["jobs"],
        ),
    )


def _detection_payload(detection: EchoDetection) -> dict:
    return detection.model_dump(mode="json")


@router.post(
    "/echo-chamber/detect",
    tags=["echo_chamber"],
    response_model=EchoDetectionStartPayload,
)
def detect(request: Request, body: EchoDetectRequest):
    """Start an echo-chamber detection: one async job chains up to N frontier
    layers around the seed and snapshots observed signals after each layer."""
    if not (body.video_url or body.video_id or body.seed_run_id):
        raise HTTPException(
            status_code=400,
            detail="One of video_url, video_id or seed_run_id is required",
        )
    service = _echo_service(request)
    try:
        detection = service.start(
            video_url=body.video_url,
            video_id=body.video_id,
            seed_run_id=body.seed_run_id,
            max_layers=body.max_layers,
            collect_comments=body.collect_comments,
            projection=body.projection,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "detection_id": detection.detection_id,
        "job_id": detection.job_id,
        "status": detection.status,
    }


@router.get(
    "/echo-chamber",
    tags=["echo_chamber"],
    response_model=Paginated[EchoDetection],
)
def list_detections(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Paginated detections, newest first."""
    detections = _echo_service(request).list_detections()
    payloads = [_detection_payload(d) for d in detections]
    full = sorted(payloads, key=lambda d: (d.get("created_at") or "", d["detection_id"]))
    page = page_sorted(
        full,
        cursor=cursor,
        page_size=page_size,
        key_func=lambda d: (d.get("created_at") or "", d["detection_id"]),
        total=len(full),
        reverse=True,
    )
    return Paginated(
        items=page.items,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
        total=page.total,
    )


@router.get(
    "/echo-chamber/{detection_id}",
    tags=["echo_chamber"],
    response_model=EchoDetection,
)
def get_detection(request: Request, detection_id: str):
    """Status + append-only per-layer timeline + latest composite score."""
    detection = _echo_service(request).get_detection(detection_id)
    if detection is None:
        raise HTTPException(
            status_code=404, detail=f"Echo detection {detection_id} not found"
        )
    return _detection_payload(detection)


@router.get(
    "/echo-chamber/{detection_id}/lens",
    tags=["echo_chamber"],
)
def get_detection_lens(
    request: Request,
    detection_id: str,
    projection: str = Query("video", description="Lens projection: video | channel"),
):
    """Recompute a lens on demand from the STORED crawl edges only.

    ``projection=video`` is the stored-timeline signal math; ``channel``
    aggregates the same edges at channel level (S2 seed-channel
    reinforcement share, S3 top-channel share, S1/S4 on channel pairs,
    S5 unavailable unless comments exist). Includes the top-10 videos /
    channels by weighted in-degree within the crawl and the seed card.
    """
    if projection not in ("video", "channel"):
        raise HTTPException(
            status_code=400, detail="projection must be 'video' or 'channel'"
        )
    service = _echo_service(request)
    try:
        return service.lens(detection_id, projection)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0]))


@router.get(
    "/echo-chamber/{detection_id}/structure",
    tags=["echo_chamber"],
)
def get_detection_structure(request: Request, detection_id: str):
    """Full structural analysis of the stored crawl (spec §37 sections).

    VIDEO LENS: network statistics, community structure (modularity,
    conductance, internal/external ratio), reinforcement (WCR + seeded
    degree-preserving null model with z-score/percentile, community
    persistence), centrality (PageRank/HITS). CHANNEL LENS: channel
    projection network + concentration (HHI/top share). Every metric
    carries the §36 metadata envelope; unavailable metrics are explicit,
    never silent zeros. Includes verbatim research disclaimers (§38).
    """
    service = _echo_service(request)
    try:
        return service.structure(detection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0]))


@router.get(
    "/echo-chamber/{detection_id}/audience",
    tags=["echo_chamber"],
)
def get_detection_audience(request: Request, detection_id: str):
    """Audience/commenter lens (§22): mean Jaccard commenter overlap within
    vs between detected communities. Unavailable when no comment identities
    were collected - missing data is never converted to zero."""
    service = _echo_service(request)
    try:
        return service.audience(detection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0]))


@router.post(
    "/echo-chamber/{detection_id}/continue",
    tags=["echo_chamber"],
    response_model=JobSubmitPayload,
)
def continue_detection(
    request: Request, detection_id: str, body: EchoContinueRequest
):
    """Append more layers to a finished detection (lifetime cap 10)."""
    service = _echo_service(request)
    try:
        detection = service.continue_detection(detection_id, body.extra_layers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0]))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"job_id": detection.job_id}


@router.post(
    "/echo-chamber/{detection_id}/stop",
    tags=["echo_chamber"],
    response_model=EchoDetectionStartPayload,
)
def stop_detection(request: Request, detection_id: str):
    """Cooperatively stop the active crawl between layers."""
    service = _echo_service(request)
    try:
        detection = service.stop(detection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0]))
    return {
        "detection_id": detection.detection_id,
        "job_id": detection.job_id,
        "status": detection.status,
    }
