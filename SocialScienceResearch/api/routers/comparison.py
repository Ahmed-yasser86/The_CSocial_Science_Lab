"""B4: Comparison engine router.

Endpoints for comparing videos / channels / upload-date periods / cohorts /
runs with an explicit normalization (``none`` | ``per_1k`` | ``z_score``,
ADR-0008). Backed by ``ComparisonService`` on top of ``StatisticsService``;
z-scores and percentile ranks are computed over the **compared set only**
and outliers are flagged, never silently dropped.

Every response model is declared; empty id lists are rejected via
``ValueError`` (the app's handler maps it to a ``400``).

Owned by the B4 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.domain.query import PeriodSpec, VideoFilter
from SocialScienceResearch.services.comparison_service import (
    Cohort,
    CohortComparison,
    ComparisonService,
    EntityComparison,
    JobComparison,
    Normalization,
    PeriodComparison,
    RunComparison,
)

router = APIRouter()


class VideoComparisonRequest(BaseModel):
    """Body of ``POST /comparison/videos``."""

    model_config = ConfigDict(extra="forbid")

    video_ids: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    normalization: Normalization = Normalization.NONE


class ChannelComparisonRequest(BaseModel):
    """Body of ``POST /comparison/channels``."""

    model_config = ConfigDict(extra="forbid")

    channel_ids: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    normalization: Normalization = Normalization.NONE


class PeriodBody(BaseModel):
    """One upload-date (video) or joined-date (channel) window."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    start: date
    end: date


class PeriodComparisonRequest(BaseModel):
    """Body of ``POST /comparison/periods``."""

    model_config = ConfigDict(extra="forbid")

    period_a: PeriodBody
    period_b: PeriodBody
    entity: Literal["video", "channel"] = "video"
    metrics: list[str] = Field(default_factory=list)


class CohortBody(BaseModel):
    """A named cohort: optional channel scope plus an optional VideoFilter."""

    model_config = ConfigDict(extra="forbid")

    name: str
    channel_id: str | None = None
    filter: VideoFilter | None = None


class CohortComparisonRequest(BaseModel):
    """Body of ``POST /comparison/cohorts``."""

    model_config = ConfigDict(extra="forbid")

    cohorts: list[CohortBody] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class RunComparisonRequest(BaseModel):
    """Body of ``POST /comparison/runs``."""

    model_config = ConfigDict(extra="forbid")

    run_ids: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class JobsComparisonRequest(BaseModel):
    """Body of ``POST /comparison/jobs``."""

    model_config = ConfigDict(extra="forbid")

    job_ids: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


def _service(request: Request) -> ComparisonService:
    """Lazily build/cache the shared ComparisonService on ``app.state``."""
    return get_service(
        request,
        "comparison",
        lambda: ComparisonService(
            request.app.state.services["repos"], request.app.state.settings
        ),
    )


@router.post("/comparison/videos", response_model=EntityComparison)
def compare_videos(body: VideoComparisonRequest, request: Request) -> EntityComparison:
    """Compare videos on their latest observed metrics."""
    return _service(request).compare_videos(
        body.video_ids, body.metrics, body.normalization
    )


@router.post("/comparison/channels", response_model=EntityComparison)
def compare_channels(body: ChannelComparisonRequest, request: Request) -> EntityComparison:
    """Compare channels on their latest observed statistics."""
    return _service(request).compare_channels(
        body.channel_ids, body.metrics, body.normalization
    )


@router.post("/comparison/periods", response_model=PeriodComparison)
def compare_periods(body: PeriodComparisonRequest, request: Request) -> PeriodComparison:
    """Compare two upload-date windows per metric with growth deltas."""
    period_a = PeriodSpec(
        name=body.period_a.name, start=body.period_a.start, end=body.period_a.end
    )
    period_b = PeriodSpec(
        name=body.period_b.name, start=body.period_b.start, end=body.period_b.end
    )
    return _service(request).compare_periods(
        period_a, period_b, entity=body.entity, metrics=body.metrics
    )


@router.post("/comparison/cohorts", response_model=CohortComparison)
def compare_cohorts(body: CohortComparisonRequest, request: Request) -> CohortComparison:
    """Compare named video cohorts by count and metric means."""
    cohorts = [
        Cohort(name=c.name, channel_id=c.channel_id, filter=c.filter)
        for c in body.cohorts
    ]
    return _service(request).compare_cohorts(cohorts, metrics=body.metrics)


@router.post("/comparison/runs", response_model=RunComparison)
def compare_runs(body: RunComparisonRequest, request: Request) -> RunComparison:
    """Compare collection-run snapshots with entity churn between runs."""
    return _service(request).compare_runs(body.run_ids, body.metrics)


@router.post("/comparison/jobs", response_model=JobComparison)
def compare_jobs(body: JobsComparisonRequest, request: Request) -> JobComparison:
    """Compare two jobs via their aggregated child-run metrics.

    Mirrors ``POST /comparison/runs`` but takes ``job_ids``: each job's
    child runs (plan-J1 linkage) are resolved and pooled into one snapshot
    per job, with entity churn between consecutive jobs.
    """
    return _service(request).compare_jobs(body.job_ids, body.metrics)