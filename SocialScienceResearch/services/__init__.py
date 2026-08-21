"""Service layer: collection workflows, sampling and analytics."""

from __future__ import annotations

from .analytics_service import AnalyticsService, ChannelOverview, VideoEngagement
from .collection_service import CollectionService
from .jobs import Job, JobManager, JobStatus
from .quality_service import CoverageReport, QualityService
from .recommendation_graph_service import (
    NetworkSummary,
    RecommendationGraphService,
    VideoNetworkContext,
)
from .recommendation_service import RecommendationService
from .results import CollectionResult
from .sampling_service import (
    SamplingError,
    SamplingResult,
    SamplingService,
    UnsupportedSamplingError,
)
from .query_service import QueryService

__all__ = [
    "AnalyticsService",
    "ChannelOverview",
    "CollectionResult",
    "CollectionService",
    "CoverageReport",
    "Job",
    "JobManager",
    "JobStatus",
    "NetworkSummary",
    "QualityService",
    "QueryService",
    "RecommendationGraphService",
    "RecommendationService",
    "SamplingError",
    "SamplingResult",
    "SamplingService",
    "UnsupportedSamplingError",
    "VideoEngagement",
    "VideoNetworkContext",
]
