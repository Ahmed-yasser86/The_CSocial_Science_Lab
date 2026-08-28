"""Excel implementation of the repository interfaces.

All Excel-specific concerns live in ``excel_workbook`` and
``serialization``; this module only maps domain models to and from rows.
Swapping the persistence backend to SQL means implementing the interfaces in
``persistence.base`` against a relational engine - no business logic changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from SocialScienceResearch.config.settings import RepositorySettings
from SocialScienceResearch.domain.enums import EntityType, RunType
from SocialScienceResearch.domain.models import (
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
from SocialScienceResearch.domain.sample_models import Sample

from .base import (
    ChannelRepository,
    CollectionRunRepository,
    CommentRepository,
    RecommendationRepository,
    Repositories,
    TranscriptRepository,
    UpsertResult,
    VideoRepository,
)
from .author_repository import ExcelAuthorRepository
from .dataset_repository import DatasetRepository
from .echo_repository import ExcelEchoDetectionRepository
from .job_repository import ExcelJobRepository
from .layer_repository import LayerRunRepository
from .excel_workbook import WorkbookStore
from .project_item_repository import ProjectItemRepository
from .project_repository import ProjectRepository
from .sample_repository import SampleRepository
from .serialization import headers_for, model_to_row, row_to_model

M = TypeVar("M", bound=BaseModel)


class _ExcelEntityRepository:
    """Shared behaviour for Excel-backed repositories."""

    _SHEET = ""
    _MODEL: type[BaseModel] | None = None
    _KEY = ""
    _OBS_SHEET = ""
    _OBS_MODEL: type[BaseModel] | None = None

    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        if self._MODEL is not None:
            self._store.ensure_sheet(self._SHEET, headers_for(self._MODEL))
        if self._OBS_MODEL is not None and self._OBS_SHEET:
            self._store.ensure_sheet(self._OBS_SHEET, headers_for(self._OBS_MODEL))

    def _upsert(self, model: BaseModel, entity_type: EntityType) -> UpsertResult:
        assert self._MODEL is not None
        row = model_to_row(model)
        key = str(getattr(model, self._KEY))
        created = self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(self._MODEL), row
        )
        return UpsertResult(entity_type=entity_type, entity_id=key, created=created)

    def _get(self, key: str) -> BaseModel | None:
        assert self._MODEL is not None
        row = self._store.find_row(self._SHEET, self._KEY, key)
        return row_to_model(self._MODEL, row) if row else None

    def _list(self) -> list[BaseModel]:
        assert self._MODEL is not None
        return [
            row_to_model(self._MODEL, r)
            for r in self._store.read_rows(self._SHEET, key_field=self._KEY)
        ]

    def _save_observation(self, model: BaseModel) -> None:
        assert self._OBS_MODEL is not None and self._OBS_SHEET
        self._store.upsert_row(
            self._OBS_SHEET,
            "observation_id",
            headers_for(self._OBS_MODEL),
            model_to_row(model),
        )

    def _list_observations(
        self, model_cls: type[BaseModel], sheet: str
    ) -> list[BaseModel]:
        rows = self._store.read_rows(sheet, key_field="observation_id")
        return [row_to_model(model_cls, r) for r in rows]

    @staticmethod
    def _latest_obs_by_id(
        models: list[BaseModel], ids: list[str] | None, id_field: str
    ) -> dict[str, Any]:
        """Single-pass latest-resolution of observations.

        Groups the observation rows by ``id_field`` and keeps the most recent
        ``observed_at`` per id (on ties the last scanned row wins, matching
        the single-id ``<sorted list>[-1]`` behaviour). Returns a dict in
        ``ids`` order with only present ids as keys.
        """
        wanted = set(ids) if ids is not None else None
        latest: dict[str, Any] = {}
        for model in models:
            key = str(getattr(model, id_field))
            if wanted is not None and key not in wanted:
                continue
            current = latest.get(key)
            if current is None or model.observed_at >= current.observed_at:
                latest[key] = model
        if wanted is None:
            return latest
        return {key: latest[key] for key in ids if key in latest}


class ExcelChannelRepository(_ExcelEntityRepository, ChannelRepository):
    """Excel-backed channel repository."""

    _SHEET = "channels"
    _MODEL = Channel
    _KEY = "channel_id"
    _OBS_SHEET = "channel_observations"
    _OBS_MODEL = ChannelObservation

    def upsert_channel(self, channel: Channel) -> UpsertResult:
        return self._upsert(channel, EntityType.CHANNEL)

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._get(channel_id)  # type: ignore[return-value]

    def list_channels(self, channel_ids: list[str] | None = None) -> list[Channel]:
        channels = self._list()  # type: ignore[return-value]
        if channel_ids is not None:
            channels = [c for c in channels if c.channel_id in set(channel_ids)]
        return channels

    def save_channel_observation(self, observation: ChannelObservation) -> None:
        self._save_observation(observation)

    def list_channel_observations(self, channel_id: str) -> list[ChannelObservation]:
        models = self._list_observations(ChannelObservation, "channel_observations")  # type: ignore[arg-type]
        filtered = [m for m in models if m.channel_id == channel_id]
        return sorted(filtered, key=lambda m: m.observed_at)

    def get_latest_channel_observation(
        self, channel_id: str
    ) -> ChannelObservation | None:
        obs = self.list_channel_observations(channel_id)
        return obs[-1] if obs else None

    def get_latest_channel_observations(
        self, channel_ids: list[str]
    ) -> dict[str, ChannelObservation]:
        models = self._list_observations(ChannelObservation, "channel_observations")  # type: ignore[arg-type]
        return self._latest_obs_by_id(models, channel_ids, "channel_id")  # type: ignore[return-value]


class ExcelVideoRepository(_ExcelEntityRepository, VideoRepository):
    """Excel-backed video repository."""

    _SHEET = "videos"
    _MODEL = Video
    _KEY = "video_id"
    _OBS_SHEET = "video_observations"
    _OBS_MODEL = VideoObservation

    def upsert_video(self, video: Video) -> UpsertResult:
        return self._upsert(video, EntityType.VIDEO)

    def get_video(self, video_id: str) -> Video | None:
        return self._get(video_id)  # type: ignore[return-value]

    def list_videos(
        self, channel_id: str | None = None, video_ids: list[str] | None = None
    ) -> list[Video]:
        videos = self._list()  # type: ignore[return-value]
        if channel_id is not None:
            videos = [v for v in videos if v.channel_id == channel_id]
        if video_ids is not None:
            wanted = set(video_ids)
            videos = [v for v in videos if v.video_id in wanted]
        return videos

    def list_videos_by_run(self, run_id: str) -> list[Video]:
        """Return videos first discovered in the given collection run."""
        videos = self._list()  # type: ignore[return-value]
        return [v for v in videos if v.first_observed_run_id == run_id]

    def mark_recommendations_scraped(self, video_id: str) -> None:
        video = self.get_video(video_id)
        if video is None:
            return
        video.recommendations_scraped = True
        self.upsert_video(video)

    def delete_video(self, video_id: str) -> None:
        self._store.delete_row(self._SHEET, self._KEY, video_id)

    def save_video_observation(self, observation: VideoObservation) -> None:
        self._save_observation(observation)

    def list_video_observations(self, video_id: str) -> list[VideoObservation]:
        models = self._list_observations(VideoObservation, "video_observations")  # type: ignore[arg-type]
        filtered = [m for m in models if m.video_id == video_id]
        return sorted(filtered, key=lambda m: m.observed_at)

    def get_latest_video_observation(
        self, video_id: str
    ) -> VideoObservation | None:
        obs = self.list_video_observations(video_id)
        return obs[-1] if obs else None

    def get_latest_video_observations(
        self, video_ids: list[str]
    ) -> dict[str, VideoObservation]:
        models = self._list_observations(VideoObservation, "video_observations")  # type: ignore[arg-type]
        return self._latest_obs_by_id(models, video_ids, "video_id")  # type: ignore[return-value]


class ExcelCommentRepository(_ExcelEntityRepository, CommentRepository):
    """Excel-backed comment repository."""

    _SHEET = "comments"
    _MODEL = Comment
    _KEY = "comment_id"
    _OBS_SHEET = "comment_observations"
    _OBS_MODEL = CommentObservation

    def upsert_comment(self, comment: Comment) -> UpsertResult:
        return self._upsert(comment, EntityType.COMMENT)

    def get_comment(self, comment_id: str) -> Comment | None:
        return self._get(comment_id)  # type: ignore[return-value]

    def list_comments(self, video_id: str | None = None) -> list[Comment]:
        comments = self._list()  # type: ignore[return-value]
        if video_id is not None:
            comments = [c for c in comments if c.video_id == video_id]  # type: ignore[union-attr, misc]
        return comments

    def list_root_comments(self, video_id: str) -> list[Comment]:
        return [
            c
            for c in self.list_comments(video_id)
            if c.parent_comment_id is None
        ]

    def list_replies(self, parent_comment_id: str) -> list[Comment]:
        return [c for c in self._list() if c.parent_comment_id == parent_comment_id]  # type: ignore[union-attr, misc]

    def list_replies_by_ids(self, parent_comment_ids: list[str]) -> dict[str, list[Comment]]:
        """Return direct replies for multiple parent comments in one scan."""
        all_comments = self._list()  # type: ignore[return-value]
        wanted = set(parent_comment_ids)
        result: dict[str, list[Comment]] = {pid: [] for pid in parent_comment_ids}
        for comment in all_comments:
            if comment.parent_comment_id in wanted:
                result[comment.parent_comment_id].append(comment)
        return result

    def save_comment_observation(self, observation: CommentObservation) -> None:
        self._save_observation(observation)

    def list_comment_observations(
        self, video_id: str | None = None, comment_id: str | None = None
    ) -> list[CommentObservation]:
        models = self._list_observations(CommentObservation, "comment_observations")  # type: ignore[arg-type]
        if video_id is not None:
            video_comments = {c.comment_id for c in self.list_comments(video_id)}
            models = [m for m in models if m.comment_id in video_comments]
        if comment_id is not None:
            models = [m for m in models if m.comment_id == comment_id]
        return sorted(models, key=lambda m: m.observed_at)

    def get_latest_comment_observation(
        self, comment_id: str
    ) -> CommentObservation | None:
        obs = self.list_comment_observations(comment_id=comment_id)
        return obs[-1] if obs else None

    def get_latest_comment_observations(
        self, comment_ids: list[str]
    ) -> dict[str, CommentObservation]:
        models = self._list_observations(CommentObservation, "comment_observations")  # type: ignore[arg-type]
        return self._latest_obs_by_id(models, comment_ids, "comment_id")  # type: ignore[return-value]


class ExcelCollectionRunRepository(_ExcelEntityRepository, CollectionRunRepository):
    """Excel-backed collection run repository."""

    _SHEET = "collection_runs"
    _MODEL = CollectionRun
    _KEY = "run_id"

    def create_run(self, run: CollectionRun) -> None:
        self._save_run(run)

    def update_run(self, run: CollectionRun) -> None:
        self._save_run(run)

    def _save_run(self, run: CollectionRun) -> None:
        self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(CollectionRun), model_to_row(run)
        )

    def get_run(self, run_id: str) -> CollectionRun | None:
        return self._get(run_id)  # type: ignore[return-value]

    def list_runs(self, run_type: RunType | None = None) -> list[CollectionRun]:
        runs = self._list()  # type: ignore[return-value]
        if run_type is not None:
            runs = [r for r in runs if r.run_type == run_type]
        return sorted(runs, key=lambda r: r.started_at)

    def list_sub_runs(self, parent_run_id: str) -> list[CollectionRun]:
        return [
            r
            for r in self._list()  # type: ignore[return-value]
            if r.parent_run_id == parent_run_id
        ]

    def record_error(self, error: CollectionError) -> None:
        row = model_to_row(error)
        self._store.upsert_row(
            "collection_errors", "error_id", headers_for(CollectionError), row
        )

    def list_errors(self, run_id: str) -> list[CollectionError]:
        rows = self._store.read_rows("collection_errors")
        return [
            row_to_model(CollectionError, r)
            for r in rows
            if r.get("run_id") == run_id
        ]


class ExcelRecommendationRepository(_ExcelEntityRepository, RecommendationRepository):
    """Excel-backed recommendation (observed relationship) repository.

    Each persisted row is a directed edge ``source_video_id ->
    recommended_video_id`` observed in a single run, ready for NetworkX.
    """

    _SHEET = "recommendations"
    _MODEL = RecommendationObservation
    _KEY = "observation_id"

    def save_recommendation(
        self, observation: RecommendationObservation
    ) -> UpsertResult:
        # Idempotent by observation id (uniquely generated per run, source
        # video and target video), so repeated collection never duplicates an
        # observed relationship.
        created = self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(self._MODEL), model_to_row(observation)
        )
        return UpsertResult(
            entity_type=EntityType.RECOMMENDATION,
            entity_id=observation.observation_id,
            created=created,
        )

    def list_recommendations_for_source(
        self, source_video_id: str, run_id: str | None = None
    ) -> list[RecommendationObservation]:
        edges = self.list_recommendation_edges(source_video_id=source_video_id)
        if run_id is not None:
            edges = [e for e in edges if e.collection_run_id == run_id]
        return edges

    def list_recommendation_edges(
        self,
        source_video_id: str | None = None,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        exclude_run_ids: list[str] | None = None,
    ) -> list[RecommendationObservation]:
        rows = self._store.read_rows(self._SHEET)
        edges = [row_to_model(RecommendationObservation, r) for r in rows]
        if source_video_id is not None:
            edges = [e for e in edges if e.source_video_id == source_video_id]
        if run_id is not None:
            edges = [e for e in edges if e.collection_run_id == run_id]
        if run_ids is not None:
            allowed = set(run_ids)
            edges = [e for e in edges if e.collection_run_id in allowed]
        if exclude_run_ids is not None:
            excluded = set(exclude_run_ids)
            edges = [e for e in edges if e.collection_run_id not in excluded]
        return edges

    def list_source_video_ids(self) -> list[str]:
        return sorted({e.source_video_id for e in self.list_recommendation_edges()})


class ExcelTranscriptRepository(_ExcelEntityRepository, TranscriptRepository):
    """Excel-backed transcript metadata + external ``.txt`` artifacts.

    The transcript *content* is written to ``{transcripts_dir}/{video_id}.txt``
    (never inside Excel); the sheet row stores the stable reference, path,
    provenance and explicit status.
    """

    _SHEET = "transcripts"
    _MODEL = TranscriptRecord
    _KEY = "transcript_id"

    def __init__(self, store: WorkbookStore, transcripts_dir: str | Path) -> None:
        super().__init__(store)
        self._transcripts_dir = Path(transcripts_dir)

    def _artifact_path(self, video_id: str) -> Path:
        return self._transcripts_dir / f"{video_id}.txt"

    def write_artifact(self, video_id: str, content: str) -> Path:
        """Write transcript content to an external file and return the path."""
        path = self._artifact_path(video_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_artifact(self, video_id: str) -> str | None:
        """Read transcript content back from the external file, if present."""
        path = self._artifact_path(video_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_transcript(self, record: TranscriptRecord) -> None:
        self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(TranscriptRecord), model_to_row(record)
        )

    def get_transcript(self, video_id: str) -> TranscriptRecord | None:
        records = self.list_transcripts(video_id)
        return records[-1] if records else None

    def list_transcripts(
        self, video_id: str | None = None
    ) -> list[TranscriptRecord]:
        records = [
            row_to_model(TranscriptRecord, r)
            for r in self._store.read_rows(self._SHEET, key_field=self._KEY)
        ]
        if video_id is not None:
            records = [r for r in records if r.video_id == video_id]
        # ``observed_at`` is optional (legacy workbooks lack the column), so
        # sort with None rows last instead of comparing against datetimes.
        return sorted(
            records,
            key=lambda r: (
                r.observed_at is None,
                r.observed_at.isoformat() if r.observed_at else "",
            ),
        )


class ExcelProjectItemRepository(ProjectItemRepository):
    """Excel-backed project item repository."""

    _SHEET = "project_items"
    _MODEL = ProjectItem
    _KEY = "item_id"

    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(self._SHEET, headers_for(ProjectItem))

    def save_item(self, item: ProjectItem) -> None:
        self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(ProjectItem), model_to_row(item)
        )

    def get_item(self, item_id: str) -> ProjectItem | None:
        row = self._store.find_row(self._SHEET, self._KEY, item_id)
        if row is None or row.get("item_id") != item_id:
            return None
        return row_to_model(ProjectItem, row)  # type: ignore[return-value]

    def list_items(self, project_id: str | None = None) -> list[ProjectItem]:
        items = [
            row_to_model(ProjectItem, r)  # type: ignore[return-value]
            for r in self._store.read_rows(self._SHEET, key_field=self._KEY)
        ]
        if project_id:
            items = [i for i in items if i.project_id == project_id]
        return items

    def list_items_by_project(self, project_id: str) -> list[ProjectItem]:
        return self.list_items(project_id=project_id)

    def update_item(self, item: ProjectItem) -> None:
        self.save_item(item)

    def delete_item(self, item_id: str) -> None:
        from .dataset_repository import blank_row
        blank_row(self._store, self._SHEET, self._KEY, item_id)


@dataclass
class ExcelRepositories(Repositories):
    """Container of all concrete Excel repositories sharing one store."""

    store: WorkbookStore
    datasets: DatasetRepository
    samples: SampleRepository
    projects: ProjectRepository
    project_items: ProjectItemRepository
    layers: LayerRunRepository
    jobs: ExcelJobRepository
    echo_detections: ExcelEchoDetectionRepository


def build_excel_repositories(
    settings: RepositorySettings | None = None,
) -> ExcelRepositories:
    """Build all Excel repositories against a single workbook store.

    The returned object owns the store; callers should ``.store.close()`` (or
    use it as a context manager) after a collection run to flush data.
    """
    repo_settings = settings or RepositorySettings()
    store = WorkbookStore(
        repo_settings.workbook_path,
        max_rows_per_sheet=repo_settings.max_rows_per_sheet,
        flush_every=repo_settings.flush_every,
    )
    channels = ExcelChannelRepository(store)
    videos = ExcelVideoRepository(store)
    comments = ExcelCommentRepository(store)
    runs = ExcelCollectionRunRepository(store)
    recommendations = ExcelRecommendationRepository(store)
    transcripts = ExcelTranscriptRepository(store, repo_settings.transcripts_dir)
    authors = ExcelAuthorRepository(store)
    datasets = DatasetRepository(store)
    samples = SampleRepository(store)
    projects = ProjectRepository(store)
    project_items = ExcelProjectItemRepository(store)
    layers = LayerRunRepository(store)
    jobs = ExcelJobRepository(store)
    echo_detections = ExcelEchoDetectionRepository(store)
    # Ensure observation/error sheets exist up-front for a stable file layout.
    for sheet, model in (
        ("channel_observations", ChannelObservation),
        ("video_observations", VideoObservation),
        ("comment_observations", CommentObservation),
        ("collection_errors", CollectionError),
        ("project_items", ProjectItem),
    ):
        store.ensure_sheet(sheet, headers_for(model))
    return ExcelRepositories(
        channels=channels,
        videos=videos,
        comments=comments,
        runs=runs,
        recommendations=recommendations,
        transcripts=transcripts,
        authors=authors,
        datasets=datasets,
        samples=samples,
        projects=projects,
        project_items=project_items,
        layers=layers,
        jobs=jobs,
        echo_detections=echo_detections,
        store=store,
    )
