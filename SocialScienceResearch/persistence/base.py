"""Repository interfaces for the SocialScienceResearch module.

These abstract base classes are the only persistence contract the services and
analytics layers depend on. The Excel implementation in
``persistence.excel_repository`` provides the concrete repositories today; a
SQL/PostgreSQL/SQLite implementation can replace it later without touching
business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator

from SocialScienceResearch.domain.enums import EntityType, RunType
from SocialScienceResearch.domain.models import (
    AuthorProfile,
    Channel,
    ChannelObservation,
    CollectionError,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    TranscriptRecord,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.dataset_models import Dataset, ProjectItem
from SocialScienceResearch.domain.echo_models import EchoDetection
from SocialScienceResearch.domain.job_models import CollectionJob
from SocialScienceResearch.domain.layer_models import LayerRun
from SocialScienceResearch.domain.sample_models import Sample


@dataclass(frozen=True)
class UpsertResult:
    """Outcome of an upsert operation: was the entity newly created?"""

    entity_type: EntityType
    entity_id: str
    created: bool


@dataclass
class Repositories:
    """Container of all repository interfaces.

    Services depend on this container (not on concrete Excel classes), so a
    SQL backend can be dropped in by constructing the same container with SQL
    repository implementations.
    """

    channels: ChannelRepository
    videos: VideoRepository
    comments: CommentRepository
    runs: CollectionRunRepository
    recommendations: RecommendationRepository
    transcripts: TranscriptRepository
    authors: AuthorRepository
    datasets: DatasetRepository
    samples: SampleRepository
    project_items: ProjectItemRepository
    projects: ProjectRepository
    layers: LayerRunRepository
    jobs: JobRepository
    echo_detections: EchoDetectionRepository


class ChannelRepository(ABC):
    """Persistence contract for channels and channel observations."""

    @abstractmethod
    def upsert_channel(self, channel: Channel) -> UpsertResult:
        """Insert a new channel or return ``created=False`` if it exists."""

    @abstractmethod
    def get_channel(self, channel_id: str) -> Channel | None:
        """Return the channel with the given stable id, if present."""

    @abstractmethod
    def list_channels(self) -> list[Channel]:
        """Return all known channels."""

    def list_channel_titles(self) -> dict[str, str]:
        """Return ``channel_id -> title`` without materializing raw payloads.

        The analytics metadata index uses this instead of ``list_channels()``
        (whose rows can carry multi-hundred-KB ``raw_json`` blobs). SQL
        overrides with a column-projected query.
        """
        return {channel.channel_id: channel.title for channel in self.list_channels()}

    def list_channel_descriptors(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Return ``channel_id -> {title, avatar_url}`` column-projected.

        Used by the channel-graph projection, which only needs the display
        name and avatar. SQL overrides with a projection query so heavy
        ``raw_json`` blobs are never fetched.
        """
        return {
            channel.channel_id: {
                "channel_id": channel.channel_id,
                "title": channel.title,
                "avatar_url": channel.avatar_url,
            }
            for channel in self.list_channels()
        }

    def latest_channel_metrics(
        self, channel_ids: list[str]
    ) -> dict[str, dict[str, int | None]]:
        """Latest scalar statistics per channel without raw payloads.

        Returns ``subscriber_count``/``video_count``/``view_count`` for the
        most recent observation of each channel. SQL overrides with a
        column-projected query.
        """
        observations = self.get_latest_channel_observations(channel_ids)
        return {
            channel_id: {
                "subscriber_count": observation.subscriber_count,
                "video_count": observation.video_count,
                "view_count": observation.view_count,
            }
            for channel_id, observation in observations.items()
        }

    def explore_channel_rows(self) -> list[dict[str, Any]]:
        """Latest-state channel rows for the explorer table, no raw payloads.

        Mirrors ``QueryService._channel_rows`` but excludes the multi-hundred-KB
        ``raw_json`` blobs (full-row scans are pathologically slow). SQL
        overrides with a column-projected query.
        """
        channels = self.list_channels()
        latest = self.latest_channel_metrics([c.channel_id for c in channels])
        return [
            {
                "channel_id": c.channel_id,
                "title": c.title,
                "description": c.description,
                "handle": c.handle,
                "is_verified": c.is_verified,
                "avatar_url": c.avatar_url,
                "banner_url": c.banner_url,
                "country": c.country,
                "joined_date": c.joined_date,
                "subscriber_count": latest.get(c.channel_id, {}).get("subscriber_count"),
                "video_count": latest.get(c.channel_id, {}).get("video_count"),
                "view_count": latest.get(c.channel_id, {}).get("view_count"),
            }
            for c in channels
        ]

    @abstractmethod
    def save_channel_observation(self, observation: ChannelObservation) -> None:
        """Persist one run-scoped observation (idempotent by observation id)."""

    @abstractmethod
    def list_channel_observations(self, channel_id: str) -> list[ChannelObservation]:
        """Return all observations of a channel, oldest first."""

    @abstractmethod
    def get_latest_channel_observation(
        self, channel_id: str
    ) -> ChannelObservation | None:
        """Return the most recent observation of a channel, if any."""

    @abstractmethod
    def get_latest_channel_observations(
        self, channel_ids: list[str]
    ) -> dict[str, ChannelObservation]:
        """Return the most recent observation of each channel in one scan.

        The result dict is keyed by channel id (preserving the input order)
        and contains an entry only for ids that have at least one observation.
        This batch method replaces the N+1 ``get_latest_channel_observation``
        loop with a single pass over the observation sheet.
        """


class VideoRepository(ABC):
    """Persistence contract for videos and video observations."""

    @abstractmethod
    def upsert_video(self, video: Video) -> UpsertResult:
        """Insert a new video or return ``created=False`` if it exists."""

    @abstractmethod
    def get_video(self, video_id: str) -> Video | None:
        """Return the video with the given stable id, if present."""

    @abstractmethod
    def list_videos(self, channel_id: str | None = None) -> list[Video]:
        """Return all videos, optionally filtered by channel."""

    @abstractmethod
    def list_videos_by_run(self, run_id: str) -> list[Video]:
        """Return videos first discovered in the given collection run."""

    @abstractmethod
    def mark_recommendations_scraped(self, video_id: str) -> None:
        """Record that this video's recommendation feed has been scraped.

        The flag is set whenever a recommendation run persists edges FOR this
        source video, so the graph can tell already-scraped nodes (including
        target-only nodes that later get expanded) from never-scraped ones.
        """

    @abstractmethod
    def delete_video(self, video_id: str) -> None:
        """Remove a video row (used to clean up recommendation stubs whose
        deep-enrichment later failed, so a failed target reverts to being a
        graph-node-only entity)."""

    @abstractmethod
    def save_video_observation(self, observation: VideoObservation) -> None:
        """Persist one run-scoped observation (idempotent by observation id)."""

    @abstractmethod
    def list_video_observations(self, video_id: str) -> list[VideoObservation]:
        """Return all observations of a video, oldest first."""

    @abstractmethod
    def get_latest_video_observation(self, video_id: str) -> VideoObservation | None:
        """Return the most recent observation of a video, if any."""

    @abstractmethod
    def get_latest_video_observations(
        self, video_ids: list[str]
    ) -> dict[str, VideoObservation]:
        """Return the most recent observation of each video in one scan.

        Keyed by video id (input order preserved); ids without an observation
        are simply absent. Replaces the N+1 ``get_latest_video_observation``
        loop with a single pass over the observation sheet.
        """

    def list_video_metadata(
        self, video_ids: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Column-projected video metadata for the analytics hot path.

        Returns the fields the network analytics and export paths consume
        without materializing heavy ``raw_json`` payloads (which can exceed
        200KB per row and make full-row scans pathologically slow). The SQL
        backend overrides this with a projection query; backends without
        column projection fall back to the full-row read.
        """
        videos = self.list_videos()
        if video_ids is not None:
            wanted = set(video_ids)
            videos = [v for v in videos if v.video_id in wanted]
        return {
            v.video_id: {
                "video_id": v.video_id,
                "channel_id": v.channel_id,
                "title": v.title,
                "thumbnail_url": v.thumbnail_url,
                "duration": v.duration,
                "recommendations_scraped": bool(v.recommendations_scraped),
            }
            for v in videos
        }

    def latest_observation_metrics(
        self, video_ids: list[str]
    ) -> dict[str, dict[str, int | None]]:
        """Latest scalar metric counts per video, without raw payloads.

        ``view_count``/``like_count``/``comment_count``/``favorite_count`` for
        the most recent observation of each video. SQL overrides this with a
        column-projected query so large ``raw_json`` blobs are never fetched.
        """
        observations = self.get_latest_video_observations(video_ids)
        return {
            video_id: {
                "view_count": observation.view_count,
                "like_count": observation.like_count,
                "comment_count": observation.comment_count,
                "favorite_count": observation.favorite_count,
            }
            for video_id, observation in observations.items()
        }

    def explore_video_rows(self) -> list[dict[str, Any]]:
        """Latest-state video rows for the explorer table, no raw payloads.

        Mirrors ``QueryService._video_rows`` (same registered-variable keys so
        search/filter/sort semantics are unchanged) but excludes the heavy
        ``raw_json`` payload, which can exceed 200KB per row and dominate full
        table scans. SQL overrides with a column-projected query.
        """
        videos = self.list_videos()
        latest = self.latest_observation_metrics([v.video_id for v in videos])
        return [
            {
                "video_id": v.video_id,
                "channel_id": v.channel_id,
                "title": v.title,
                "description": v.description,
                "duration": v.duration,
                "upload_date": v.upload_date,
                "upload_timestamp": v.upload_timestamp,
                "tags": v.tags,
                "categories": v.categories,
                "language": v.language,
                "live_status": v.live_status,
                "availability": v.availability,
                "age_limit": v.age_limit,
                "is_short": v.is_short,
                "thumbnail_url": v.thumbnail_url,
                "transcript_status": v.transcript_status,
                "transcript_lang": v.transcript_lang,
                "transcript_length_chars": None,
                "view_count": latest.get(v.video_id, {}).get("view_count"),
                "like_count": latest.get(v.video_id, {}).get("like_count"),
                "comment_count": latest.get(v.video_id, {}).get("comment_count"),
                "favorite_count": latest.get(v.video_id, {}).get("favorite_count"),
            }
            for v in videos
        ]


class CommentRepository(ABC):
    """Persistence contract for comments and comment observations."""

    @abstractmethod
    def upsert_comment(self, comment: Comment) -> UpsertResult:
        """Insert a new comment or return ``created=False`` if it exists."""

    @abstractmethod
    def get_comment(self, comment_id: str) -> Comment | None:
        """Return the comment with the given stable id, if present."""

    @abstractmethod
    def list_comments(self, video_id: str | None = None) -> list[Comment]:
        """Return comments (roots and replies), optionally for a video."""

    def iter_comments(
        self,
        chunk_size: int = 5000,
        columns: list[str] | None = None,
    ) -> Iterator[list[Comment]]:
        """Yield comments in bounded chunks for full-corpus scans.

        The default materializes ``list_comments()`` and slices it; SQL
        backends override with a keyset-paginated, column-projected query so
        analytics over millions of rows never load every row (and never the
        heavy ``raw_json`` blobs) into memory at once. ``columns`` names the
        fields the caller actually consumes; unsupported backends ignore it.
        """
        comments = self.list_comments()
        for start in range(0, len(comments), max(1, chunk_size)):
            yield comments[start : start + chunk_size]

    @abstractmethod
    def list_root_comments(self, video_id: str) -> list[Comment]:
        """Return only root comments (parents of threads) for a video."""

    @abstractmethod
    def list_replies(self, parent_comment_id: str) -> list[Comment]:
        """Return the direct replies of a comment."""

    @abstractmethod
    def list_replies_by_ids(self, parent_comment_ids: list[str]) -> dict[str, list[Comment]]:
        """Return direct replies for multiple parent comments in one scan.

        Returns a dict keyed by parent_comment_id with lists of reply comments.
        """

    @abstractmethod
    def save_comment_observation(self, observation: CommentObservation) -> None:
        """Persist one run-scoped observation (idempotent by observation id)."""

    @abstractmethod
    def list_comment_observations(
        self, video_id: str | None = None, comment_id: str | None = None
    ) -> list[CommentObservation]:
        """Return comment observations, optionally filtered."""

    @abstractmethod
    def get_latest_comment_observation(
        self, comment_id: str
    ) -> CommentObservation | None:
        """Return the most recent observation of a comment, if any."""

    @abstractmethod
    def get_latest_comment_observations(
        self, comment_ids: list[str]
    ) -> dict[str, CommentObservation]:
        """Return the most recent observation of each comment in one scan.

        Keyed by comment id (input order preserved); ids without an
        observation are simply absent. Replaces the N+1
        ``get_latest_comment_observation`` loop with a single pass over the
        observation sheet.
        """

    def latest_comment_metrics(
        self, comment_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Latest scalar metric counts per comment, without raw payloads.

        ``like_count``/``reply_count``/``is_removed`` for the most recent
        observation of each comment. SQL overrides with a column-projected
        query so large ``raw_json`` blobs are never fetched.
        """
        observations = self.get_latest_comment_observations(comment_ids)
        return {
            comment_id: {
                "like_count": observation.like_count,
                "reply_count": observation.reply_count,
                "is_removed": observation.is_removed,
            }
            for comment_id, observation in observations.items()
        }

    def explore_comment_rows(self) -> list[dict[str, Any]]:
        """Latest-state comment rows for the explorer table, no raw payloads.

        Mirrors ``QueryService._comment_rows`` (same registered-variable keys)
        but excludes the heavy ``raw_json`` payloads that dominate full-table
        scans on comment corpora. SQL overrides with a column-projected query.
        """
        comments = self.list_comments()
        latest = self.latest_comment_metrics([c.comment_id for c in comments])
        return [
            {
                "comment_id": c.comment_id,
                "video_id": c.video_id,
                "author_name": c.author_name,
                "author_id": c.author_id,
                "comment_text": c.comment_text,
                "published_at": c.published_at,
                "is_reply": c.is_reply,
                "parent_comment_id": c.parent_comment_id,
                "root_comment_id": c.root_comment_id,
                "is_author": c.is_author,
                "like_count": latest.get(c.comment_id, {}).get("like_count"),
                "reply_count": latest.get(c.comment_id, {}).get("reply_count"),
                "is_removed": latest.get(c.comment_id, {}).get("is_removed"),
            }
            for c in comments
        ]


class CollectionRunRepository(ABC):
    """Persistence contract for collection runs and their failures."""

    @abstractmethod
    def create_run(self, run: CollectionRun) -> None:
        """Persist a new run record."""

    @abstractmethod
    def update_run(self, run: CollectionRun) -> None:
        """Update an existing run record (by ``run_id``)."""

    @abstractmethod
    def get_run(self, run_id: str) -> CollectionRun | None:
        """Return the run with the given id, if present."""

    @abstractmethod
    def list_runs(self, run_type: RunType | None = None) -> list[CollectionRun]:
        """Return runs, optionally filtered by type, oldest first."""

    @abstractmethod
    def list_sub_runs(self, parent_run_id: str) -> list[CollectionRun]:
        """Return the runs recorded as children of ``parent_run_id``."""

    @abstractmethod
    def record_error(self, error: CollectionError) -> None:
        """Persist a per-entity failure so failures are never silently dropped."""

    @abstractmethod
    def list_errors(self, run_id: str) -> list[CollectionError]:
        """Return all recorded errors for a run."""


class RecommendationRepository(ABC):
    """Persistence contract for observed recommendation relationships.

    The stored data is *network-ready*: each row is a directed edge
    ``source_video_id -> recommended_video_id`` observed during a run, which a
    future module can load into NetworkX.
    """

    @abstractmethod
    def save_recommendation(self, observation: RecommendationObservation) -> UpsertResult:
        """Persist one observed relationship (idempotent by run + source + target)."""

    @abstractmethod
    def list_recommendations_for_source(
        self, source_video_id: str, run_id: str | None = None
    ) -> list[RecommendationObservation]:
        """Return observed recommendations for a source video, optionally per run."""

    @abstractmethod
    def list_recommendation_edges(
        self,
        source_video_id: str | None = None,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        exclude_run_ids: list[str] | None = None,
    ) -> list[RecommendationObservation]:
        """Return recommendation edges for network construction.

        ``run_id`` filters by a single ``collection_run_id``; ``run_ids`` filters
        by an explicit allow-list; ``exclude_run_ids`` drops edges whose
        ``collection_run_id`` is in the given list. The filters are combined
        with AND semantics (an edge must satisfy every supplied constraint).
        """

    def list_recommendation_edges_graph(
        self, run_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Column-projected edges for graph construction (no ``raw_json``).

        Subclasses override with a projection query. The default walks the
        full-row read and filters in memory so backends without column
        projection still work.
        """
        edges = self.list_recommendation_edges()
        if run_ids:
            wanted = set(run_ids)
            edges = [e for e in edges if e.collection_run_id in wanted]
        return [
            {
                "source_video_id": e.source_video_id,
                "recommended_video_id": e.recommended_video_id,
                "position": e.position,
                "collection_run_id": e.collection_run_id,
                "title": e.title,
                "channel_id": e.channel_id,
                "channel_name": e.channel_name,
            }
            for e in edges
        ]

    @abstractmethod
    def list_source_video_ids(self) -> list[str]:
        """Return distinct source videos that have recommendation observations."""

    def explore_recommendation_rows(self) -> list[dict[str, Any]]:
        """Latest-state recommendation rows for the explorer table, no raw payloads.

        Mirrors ``QueryService._recommendation_rows`` plus the ``observation_id``
        primary key the explorer needs for stable pagination, while excluding the
        heavy ``raw_json`` payloads. SQL overrides with a column-projected query.
        """
        edges = self.list_recommendation_edges()
        return [
            {
                "observation_id": edge.observation_id,
                "source_video_id": edge.source_video_id,
                "recommended_video_id": edge.recommended_video_id,
                "position": edge.position,
                "status": edge.status.value,
                "channel_id": edge.channel_id,
                "title": edge.title,
                "observed_at": edge.observed_at,
            }
            for edge in edges
        ]


class TranscriptRepository(ABC):
    """Persistence contract for video transcript artifacts.

    Transcript *content* is stored as external files (never inside the Excel
    workbook); this repository persists the metadata reference, provenance and
    explicit status (available/missing/unsupported) so transcript coverage is
    auditable and a future SQL provider can keep files + metadata separately.
    """

    @abstractmethod
    def save_transcript(self, record: TranscriptRecord) -> None:
        """Persist one transcript record (idempotent by transcript id)."""

    @abstractmethod
    def get_transcript(self, video_id: str) -> TranscriptRecord | None:
        """Return the most recent transcript record for a video, if any."""

    @abstractmethod
    def list_transcripts(
        self, video_id: str | None = None
    ) -> list[TranscriptRecord]:
        """Return transcript records, optionally filtered by video."""


class AuthorRepository(ABC):
    """Persistence contract for aggregated author participation profiles (D4).

    Author profiles are *derived* from the persisted comments corpus: each
    profile aggregates one ``author_id`` (falling back to ``author_name``),
    so this repository is a read-side projection over comments rather than an
    independently collected entity. The abstraction exists so a future SQL
    backend can materialize the same projection without changing services.
    """

    @abstractmethod
    def list_authors(self) -> list[AuthorProfile]:
        """Return one aggregated profile per comment author, id-ordered."""

    @abstractmethod
    def get_author(self, author_id: str) -> AuthorProfile | None:
        """Return the aggregated profile of one author, if any comments exist."""

    def explore_author_rows(self) -> list[dict[str, Any]]:
        """Author rows for the explorer table.

        Same registered-variable keys as ``QueryService._author_rows``. The
        explorer never displays the profile ``raw_json`` (it is surfaced on
        demand by the raw-record endpoint), so SQL overrides this to aggregate
        from column-projected comments instead of pulling every comment's
        multi-KB raw payload.
        """
        profiles = self.list_authors()
        return [
            {
                "author_id": profile.author_id,
                "author_name": profile.author_name,
                "comment_count": profile.comment_count,
                "video_ids": profile.video_ids,
                "first_seen_at": profile.first_seen_at,
                "last_seen_at": profile.last_seen_at,
                "is_author": profile.is_author,
                "first_seen_run_id": profile.first_seen_run_id,
            }
            for profile in profiles
        ]


class ProjectItemRepository(ABC):
    """Persistence contract for ProjectItems (sub-items within a research project)."""

    @abstractmethod
    def save_item(self, item: ProjectItem) -> None:
        """Persist a project item (upsert by item_id)."""

    @abstractmethod
    def get_item(self, item_id: str) -> ProjectItem | None:
        """Return the project item with the given id, if present."""

    @abstractmethod
    def list_items(self, project_id: str | None = None) -> list[ProjectItem]:
        """Return all project items, optionally filtered by project_id."""

    @abstractmethod
    def list_items_by_project(self, project_id: str) -> list[ProjectItem]:
        """Return all items belonging to a specific project."""

    @abstractmethod
    def update_item(self, item: ProjectItem) -> None:
        """Update an existing project item."""

    @abstractmethod
    def delete_item(self, item_id: str) -> None:
        """Delete a project item."""


class LayerRunRepository(ABC):
    """Persistence contract for crawl-layer anchor records.

    ``LayerRun`` is the crawl anchor written *after* a crawl step completes
    (like datasets), so frontier resolution and layer summaries are cheap
    reads instead of O(edges) scans over raw rows.
    """

    @abstractmethod
    def save_layer_run(self, layer_run: LayerRun) -> None:
        """Upsert a layer-run record (by ``layer_run_id``)."""

    @abstractmethod
    def get_layer_run(self, layer_run_id: str) -> LayerRun | None:
        """Return the layer-run record with the given id, if present."""

    @abstractmethod
    def list_layer_runs(self) -> list[LayerRun]:
        """Return all layer-run records, oldest (layer 0) first."""


class JobRepository(ABC):
    """Persistence contract for collection jobs (plan J1 write-through).

    The :class:`~services.jobs.JobManager` keeps live state in memory and
    mirrors milestones + terminal states into this repository so the job
    list survives restarts and runs can be grouped by ``job_id``.
    """

    @abstractmethod
    def save_job(self, job: CollectionJob) -> None:
        """Upsert a job row (by ``job_id``)."""

    @abstractmethod
    def get_job(self, job_id: str) -> CollectionJob | None:
        """Return the persisted job with the given id, if present."""

    @abstractmethod
    def list_jobs(
        self,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[CollectionJob]:
        """Return persisted jobs (newest first), optionally filtered."""

    def reconcile_stale_running(self, message: str) -> int:
        """Mark orphaned pending/running rows as interrupted (crash honesty).

        Called once at startup: a job that was pending/running when the
        process died can never finish. Default is a no-op for backends
        without a bulk update; SQL overrides with a single statement.
        """
        return 0


class EchoDetectionRepository(ABC):
    """Persistence contract for echo-chamber detections (echo plan §4)."""

    @abstractmethod
    def save_detection(self, detection: EchoDetection) -> None:
        """Upsert a detection row (by ``detection_id``)."""

    @abstractmethod
    def get_detection(self, detection_id: str) -> EchoDetection | None:
        """Return the detection with the given id, if present."""

    @abstractmethod
    def list_detections(self) -> list[EchoDetection]:
        """Return all detections, newest first."""
