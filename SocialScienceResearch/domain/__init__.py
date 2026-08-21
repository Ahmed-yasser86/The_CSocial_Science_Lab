"""Domain layer: enums, entity models and query specifications.

Re-exports the public API so services, analytics and API layers import from
a single place (``from SocialScienceResearch.domain import Video, ...``).
"""

from __future__ import annotations

from .enums import (
    CollectionStatus,
    DataAvailability,
    EntityType,
    ErrorType,
    PercentileBand,
    RecommendationStatus,
    RunType,
    SamplingStrategy,
    StrEnum,
)
from .models import (
    Channel,
    ChannelObservation,
    CollectionError,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from .query import (
    CommentFilter,
    Operator,
    PeriodSpec,
    QueryCondition,
    QueryContext,
    QueryGroup,
    QueryPreview,
    QueryResolve,
    ResearchQuery,
    ResearchQueryRequest,
    SamplingSpec,
    VideoFilter,
    build_variable_value,
    evaluate_query,
    preview_query,
)

__all__ = [
    "Channel",
    "ChannelObservation",
    "CollectionError",
    "CollectionRun",
    "CollectionStatus",
    "Comment",
    "CommentFilter",
    "CommentObservation",
    "DataAvailability",
    "EntityType",
    "ErrorType",
    "Operator",
    "PercentileBand",
    "PeriodSpec",
    "QueryCondition",
    "QueryContext",
    "QueryGroup",
    "QueryPreview",
    "QueryResolve",
    "RecommendationObservation",
    "RecommendationStatus",
    "ResearchQuery",
    "ResearchQueryRequest",
    "RunType",
    "SamplingSpec",
    "SamplingStrategy",
    "StrEnum",
    "Video",
    "VideoFilter",
    "VideoObservation",
    "build_variable_value",
    "evaluate_query",
    "preview_query",
]
