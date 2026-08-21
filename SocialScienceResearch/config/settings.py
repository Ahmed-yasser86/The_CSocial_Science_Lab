"""Configuration for the SocialScienceResearch module.

Follows the project convention (``Ingestion_Pipline/config/settings.py``):
module-level ``DEFAULT_*`` constants plus frozen dataclasses that read
environment variables via ``field(default_factory=...)``.

No secrets are required by this module; YouTube metadata is collected via
yt-dlp without API credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = str(DEFAULT_PROJECT_ROOT / "data" / "social_science")
DEFAULT_DATASET_NAME = "youtube_research"

# Acquisition defaults
DEFAULT_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_SOCKET_TIMEOUT = 30.0
DEFAULT_REQUEST_DELAY_SECONDS = 0.5
DEFAULT_ENRICHMENT_CONCURRENCY = 4
#: Single documented comment cap per video (reconciled from the former
#: 5000/10000 divergence); a research video cannot legitimately yield more.
DEFAULT_MAX_COMMENTS_PER_VIDEO = 10000
DEFAULT_COLLECT_COMMENTS = True
DEFAULT_MAX_VIDEOS_PER_CHANNEL = 100000  # safety ceiling; channel pagination is incremental anyway
#: Deep per-video enrichment (full stats + comments) for channel runs is on by
#: default so likes/comments are collected. Bound it with ``max_videos_to_enrich``.
DEFAULT_ENRICH_VIDEO_STATS = True
#: Default cap on deep-enriched videos per channel run. Bounds the cost of a
#: default channel scrape; researchers can raise it (or set 0 = unlimited) via
#: ``SOCIAL_MAX_VIDEOS_TO_ENRICH`` or the per-run spec.
DEFAULT_MAX_VIDEOS_TO_ENRICH = 50
DEFAULT_TRANSCRIPT_LANG = "en"  # best-effort transcript language preference

# Persistence defaults
DEFAULT_MAX_ROWS_PER_SHEET = 1048570  # Excel hard limit is 1048576; leave headroom
DEFAULT_FLUSH_EVERY = 1000  # write-through rows before auto-saving the workbook

# Sampling defaults
DEFAULT_SAMPLING_SEED = 42

# Query defaults
DEFAULT_LONG_VIDEO_THRESHOLD_SECONDS = 300  # a video >= this duration counts as "long"

# Analytics defaults
DEFAULT_TOP_N = 10  # single canonical default for list/top-N endpoints

# Job defaults
DEFAULT_JOB_MAX_WORKERS = 2  # concurrent collection jobs

# API defaults
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_API_PREFIX = "/api/v1/social-science"
DEFAULT_API_TITLE = "SocialScienceResearch API"
DEFAULT_API_VERSION = "0.1.0"
DEFAULT_API_DESCRIPTION = (
    "Research API for the SocialScienceResearch module: reproducible YouTube "
    "collection, sampling, analytics and recommendation-network analysis."
)
#: Local development origins (Next.js dev server) - override via
#: ``SOCIAL_CORS_ORIGINS`` (comma-separated) for production deployments.
DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class ScraperSettings:
    """Settings for the yt-dlp acquisition layer."""

    retries: int = field(
        default_factory=lambda: _env_int("SOCIAL_RETRIES", DEFAULT_RETRIES)
    )
    retry_backoff: float = field(
        default_factory=lambda: _env_float("SOCIAL_RETRY_BACKOFF", DEFAULT_RETRY_BACKOFF)
    )
    socket_timeout: float = field(
        default_factory=lambda: _env_float(
            "SOCIAL_SOCKET_TIMEOUT", DEFAULT_SOCKET_TIMEOUT
        )
    )
    request_delay_seconds: float = field(
        default_factory=lambda: _env_float(
            "SOCIAL_REQUEST_DELAY_SECONDS", DEFAULT_REQUEST_DELAY_SECONDS
        )
    )
    enrichment_concurrency: int = field(
        default_factory=lambda: _env_int(
            "SOCIAL_ENRICHMENT_CONCURRENCY", DEFAULT_ENRICHMENT_CONCURRENCY
        )
    )
    """Number of parallel per-video deep-enrichment workers in a channel run.

    Tune ``enrichment_concurrency`` and ``request_delay_seconds`` together:
    raise the concurrency to overlap independent network requests (metadata,
    comments, transcripts of *different* videos), and keep/raise the delay to
    bound the aggregate request rate (the delay paces the shared limiter, so
    more workers does not mean more requests per second - only more overlap).
    A delay of ``0`` disables pacing entirely (use only against tolerant
    sources or via a proxy).
    """
    impersonate: str | None = field(
        default_factory=lambda: _env_str("SOCIAL_IMPERSONATE", "") or None
    )
    proxy: str | None = field(
        default_factory=lambda: _env_str("SOCIAL_PROXY", "") or None
    )
    ignore_errors: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_IGNORE_ERRORS", False)
    )
    transcript_lang: str = field(
        default_factory=lambda: _env_str("SOCIAL_TRANSCRIPT_LANG", DEFAULT_TRANSCRIPT_LANG)
    )


@dataclass(frozen=True)
class CollectionSettings:
    """Settings controlling what gets collected per workflow."""

    collect_comments: bool = field(
        default_factory=lambda: _env_bool(
            "SOCIAL_COLLECT_COMMENTS", DEFAULT_COLLECT_COMMENTS
        )
    )
    max_comments_per_video: int = field(
        default_factory=lambda: _env_int(
            "SOCIAL_MAX_COMMENTS_PER_VIDEO", DEFAULT_MAX_COMMENTS_PER_VIDEO
        )
    )
    max_videos_per_channel: int = field(
        default_factory=lambda: _env_int(
            "SOCIAL_MAX_VIDEOS_PER_CHANNEL", DEFAULT_MAX_VIDEOS_PER_CHANNEL
        )
    )
    enrich_video_stats: bool = field(
        default_factory=lambda: _env_bool(
            "SOCIAL_ENRICH_VIDEO_STATS", DEFAULT_ENRICH_VIDEO_STATS
        )
    )
    """When True (default), the channel workflow deep-extracts each discovered
    video to capture full statistics (views/likes/comments) and optionally
    comments. Bounded by ``max_videos_to_enrich``."""
    max_videos_to_enrich: int | None = field(
        default_factory=lambda: _env_int(
            "SOCIAL_MAX_VIDEOS_TO_ENRICH", DEFAULT_MAX_VIDEOS_TO_ENRICH
        )
        or None
    )
    """Cap on deep-enriched videos per channel run. ``None`` (env ``0``) means
    no cap; the default bounds per-run cost while still capturing likes and
    comments for the first ``DEFAULT_MAX_VIDEOS_TO_ENRICH`` videos."""
    extract_flat: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_EXTRACT_FLAT", True)
    )
    """When True, channel discovery uses flat playlist entries (fast, but only
    stable metadata); full per-video extraction happens incrementally."""
    include_live_videos: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_INCLUDE_LIVE_VIDEOS", False)
    )
    """When True, channel discovery includes live videos (streams) in addition
    to regular uploaded videos. Live videos are extracted from the channel's
    live tab in addition to the regular videos tab."""
    video_tabs: list[str] | None = field(
        default_factory=lambda: _env_list("SOCIAL_VIDEO_TABS", []) or None
    )
    """Which YouTube tabs to scrape for videos. Options: 'videos', 'shorts', 'streams', 'podcasts', 'stacks', 'new', 'top'.
    Defaults to ['videos', 'shorts'] if not specified."""
    scrape_live_only: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_SCRAPE_LIVE_ONLY", False)
    )
    """When True, only scrape the 'streams' tab (live videos). Overrides video_tabs."""
    scrape_recommendations: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_SCRAPE_RECOMMENDATIONS", False)
    )
    """When True, automatically scrape recommendations for each video discovered
    during channel collection. Creates 1->N recommendation tree per video."""


@dataclass(frozen=True)
class RepositorySettings:
    """Settings for the persistence layer.

    ``backend`` selects the repository implementation: ``"sql"`` (default,
    PostgreSQL) or ``"excel"`` (legacy workbook + overflow sidecars). The SQL
    backend reads its connection string from ``database_url`` and shares the
    ``data_dir``/``transcripts_dir`` convention with Excel (transcript
    artifacts and dataset raw sidecars stay on disk in both backends).
    """

    data_dir: str = field(
        default_factory=lambda: _env_str("SOCIAL_DATA_DIR", DEFAULT_DATA_DIR)
    )
    dataset_name: str = field(
        default_factory=lambda: _env_str("SOCIAL_DATASET_NAME", DEFAULT_DATASET_NAME)
    )
    max_rows_per_sheet: int = field(
        default_factory=lambda: _env_int(
            "SOCIAL_MAX_ROWS_PER_SHEET", DEFAULT_MAX_ROWS_PER_SHEET
        )
    )
    flush_every: int = field(
        default_factory=lambda: _env_int("SOCIAL_FLUSH_EVERY", DEFAULT_FLUSH_EVERY)
    )
    """Number of write-through rows before the workbook auto-flushes to disk."""
    backend: str = field(
        default_factory=lambda: _env_str("SOCIAL_REPOSITORY_BACKEND", "sql")
    )
    """Persistence backend: ``"sql"`` (default, PostgreSQL) or ``"excel"``."""
    database_url: str = field(
        default_factory=lambda: _env_str(
            "SOCIAL_DATABASE_URL", "postgresql://postgres:123456@localhost:5432/social_science"
        )
    )
    """PostgreSQL connection string used when ``backend == "sql"``."""

    @property
    def workbook_path(self) -> Path:
        return Path(self.data_dir) / f"{self.dataset_name}.xlsx"

    @property
    def transcripts_dir(self) -> Path:
        """Directory where transcript artifacts are stored as external files."""
        return Path(self.data_dir) / "transcripts"


@dataclass(frozen=True)
class SamplingSettings:
    """Settings controlling reproducible research sampling."""

    default_seed: int = field(
        default_factory=lambda: _env_int("SOCIAL_SAMPLING_SEED", DEFAULT_SAMPLING_SEED)
    )


@dataclass(frozen=True)
class QuerySettings:
    """Settings for read-side corpus queries."""

    long_video_threshold_seconds: int = field(
        default_factory=lambda: _env_int(
            "SOCIAL_LONG_VIDEO_THRESHOLD_SECONDS",
            DEFAULT_LONG_VIDEO_THRESHOLD_SECONDS,
        )
    )
    """A video with ``duration`` >= this threshold is classified as 'long'."""


@dataclass(frozen=True)
class AnalyticsSettings:
    """Settings for analytics behaviour."""

    top_n: int = field(
        default_factory=lambda: _env_int("SOCIAL_TOP_N", DEFAULT_TOP_N)
    )
    velocity_bucket: str = field(default_factory=lambda: _env_str("SOCIAL_VELOCITY_BUCKET", "hour"))
    """Temporal bucket granularity for comment velocity ('hour', 'day')."""


@dataclass(frozen=True)
class JobSettings:
    """Settings for the in-process collection job manager."""

    max_workers: int = field(
        default_factory=lambda: _env_int("SOCIAL_JOB_MAX_WORKERS", DEFAULT_JOB_MAX_WORKERS)
    )
    """Number of concurrent background collection jobs."""

    max_run_seconds: int = field(
        default_factory=lambda: _env_int("SOCIAL_JOB_MAX_RUN_SECONDS", 3600)
    )
    """Hard cap on how long a job may run before it is force-failed.

    Guards against yt-dlp/network calls that stall indefinitely: a job that
    never returns from its worker would otherwise stay ``running`` forever.
    """


@dataclass(frozen=True)
class ApiSettings:
    """Settings for the FastAPI layer."""

    host: str = field(default_factory=lambda: _env_str("SOCIAL_API_HOST", DEFAULT_API_HOST))
    port: int = field(default_factory=lambda: _env_int("SOCIAL_API_PORT", DEFAULT_API_PORT))
    prefix: str = field(default_factory=lambda: _env_str("SOCIAL_API_PREFIX", DEFAULT_API_PREFIX))
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list("SOCIAL_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    )
    docs_enabled: bool = field(
        default_factory=lambda: _env_bool("SOCIAL_API_DOCS_ENABLED", True)
    )
    title: str = field(default_factory=lambda: _env_str("SOCIAL_API_TITLE", DEFAULT_API_TITLE))
    version: str = field(default_factory=lambda: _env_str("SOCIAL_API_VERSION", DEFAULT_API_VERSION))
    description: str = field(
        default_factory=lambda: _env_str("SOCIAL_API_DESCRIPTION", DEFAULT_API_DESCRIPTION)
    )


@dataclass(frozen=True)
class SocialScienceSettings:
    """Aggregate settings for the whole module."""

    scraper: ScraperSettings = field(default_factory=ScraperSettings)
    collection: CollectionSettings = field(default_factory=CollectionSettings)
    repository: RepositorySettings = field(default_factory=RepositorySettings)
    sampling: SamplingSettings = field(default_factory=SamplingSettings)
    query: QuerySettings = field(default_factory=QuerySettings)
    analytics: AnalyticsSettings = field(default_factory=AnalyticsSettings)
    jobs: JobSettings = field(default_factory=JobSettings)
    api: ApiSettings = field(default_factory=ApiSettings)
