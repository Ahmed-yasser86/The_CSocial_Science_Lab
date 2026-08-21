"""Domain enums for the SocialScienceResearch module.

Enums encode the controlled vocabulary used throughout the module so that
statuses, error types and sampling strategies are explicit, serializable and
reproducible across runs.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum base with a friendly label accessor."""

    def __str__(self) -> str:
        return self.value


class CollectionStatus(StrEnum):
    """Lifecycle status of a collection run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class RunType(StrEnum):
    """The kind of target a collection run is executed against."""

    CHANNEL = "channel"
    VIDEO = "video"
    RECOMMENDATION = "recommendation"


class TargetKind(StrEnum):
    """The kind of target a collection experiment collects from."""

    CHANNEL = "channel"
    VIDEO = "video"
    RECOMMENDATION = "recommendation"


class EntityType(StrEnum):
    """Kinds of entities that can be collected and persisted."""

    CHANNEL = "channel"
    VIDEO = "video"
    COMMENT = "comment"
    RECOMMENDATION = "recommendation"
    OBSERVATION = "observation"


class ErrorType(StrEnum):
    """Classified error categories for collection failures.

    Classifying errors (rather than storing raw exception strings) makes
    failures observable, comparable and retryable by policy.
    """

    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    INVALID_URL = "invalid_url"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    COMMENTS = "comments"
    TRANSCRIPT_UNSUPPORTED = "transcript_unsupported"
    LIBRARY = "library"
    RECOMMENDATION_UNSUPPORTED = "recommendation_unsupported"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class RecommendationStatus(StrEnum):
    """Status of a recommendation observation for a source video.

    ``OBSERVED`` means a real relationship was captured during a run.
    ``UNSUPPORTED`` records that the collection method cannot provide
    recommendations (yt-dlp limitation) - never silently treated as zero.
    """

    OBSERVED = "observed"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class GraphProjection(StrEnum):
    """Which node type a network graph is projected onto."""

    CHANNEL = "channel"
    VIDEO = "video"


class RelationStatus(StrEnum):
    """Classification of nodes/edges/components against a pre-crawl snapshot.

    Used by the layer-crawl report to answer "what did this crawl add?":
    nodes/edges/channels are ``NEW_*`` relative to the pre-crawl graph,
    components are ``CONNECTED`` when they touch existing nodes and
    ``DISCONNECTED`` for brand-new communities. ``SKIPPED_DUPLICATE`` records
    a re-observed edge pair (reported as a dedup count, never an error).
    """

    NEW_VIDEO = "new_video"
    EXISTING_VIDEO = "existing_video"
    NEW_CHANNEL = "new_channel"
    EXISTING_CHANNEL = "existing_channel"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SKIPPED_DUPLICATE = "skipped_duplicate"


class SamplingStrategy(StrEnum):
    """Reproducible research sampling strategies."""

    TOP_VIEWS = "top_views"
    BOTTOM_VIEWS = "bottom_views"
    TOP_LIKES = "top_likes"
    BOTTOM_LIKES = "bottom_likes"
    TOP_ENGAGEMENT = "top_engagement"
    BOTTOM_ENGAGEMENT = "bottom_engagement"
    TOP_COMMENTS = "top_comments"
    TOP_REPLIES = "top_replies"
    TOP_COMMENT_RATE = "top_comment_rate"
    TOP_LIKE_RATE = "top_like_rate"
    LONGEST = "longest"
    SHORTEST = "shortest"
    RANDOM = "random"
    STRATIFIED = "stratified"
    LATEST = "latest"
    EARLIEST = "earliest"
    DATE_RANGE = "date_range"


class DataAvailability(StrEnum):
    """Explicit availability of a requested value.

    ``MISSING`` means the source did not provide the value.
    ``UNSUPPORTED`` means the collection method cannot provide it at all.
    Both are represented explicitly; nothing is fabricated or estimated.
    """

    AVAILABLE = "available"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


class PercentileBand(StrEnum):
    """Supported comment like-count percentile bands."""

    P75 = "75"
    P90 = "90"
    P95 = "95"
    P99 = "99"


class TranscriptStatus(StrEnum):
    """Availability of a video transcript/captions artifact.

    ``AVAILABLE`` means caption text was extracted and stored externally.
    ``MISSING`` means the video has no captions to extract.
    ``UNSUPPORTED`` means the collection method could not obtain captions for
    this video (consent wall, no auto-captions, extraction failure).
    Both missing/unsupported are recorded explicitly - never fabricated.
    """

    AVAILABLE = "available"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


# NOTE: there is intentionally no ``JobStatus`` here - the live definition
# lives in ``services.jobs`` (the job registry owns its lifecycle vocabulary,
# which includes a ``succeeded`` state distinct from ``CollectionStatus``).
