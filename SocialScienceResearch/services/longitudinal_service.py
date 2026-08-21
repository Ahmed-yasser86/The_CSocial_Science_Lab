"""B3: Longitudinal channel/video histories, run deltas and observation gaps.

Exposes the already-persisted per-run observation data (``ChannelObservation``
/ ``VideoObservation``) with per-step growth percentages delegated to
``StatisticsService.growth`` (ADR-0006), plus run-to-run snapshot diffs and
observation-gap detection. Nothing here fabricates history: every value is
read from the persisted run observations, and absent values stay ``None``.

Run deltas compare two runs of the *same* type by snapshotting which entities
were observed in each run and diffing their latest per-run metric values.
Entities present in only one run are reported as ``new`` / ``disappeared``,
never silently dropped.

Owned by the B3 module agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import CollectionRun
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.statistics_service import StatisticsService

_CHANNEL_METRICS = ("subscriber_count", "video_count", "view_count")
_VIDEO_METRICS = ("view_count", "like_count", "comment_count", "favorite_count")

_SECONDS_PER_DAY = 86400.0


class ChannelHistoryPoint(BaseModel):
    """One channel observation with per-step growth vs the previous one."""

    model_config = ConfigDict(extra="allow")

    observation_id: str
    collection_run_id: str
    observed_at: datetime
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    subscriber_growth_pct: float | None = None
    video_growth_pct: float | None = None
    view_growth_pct: float | None = None


class VideoHistoryPoint(BaseModel):
    """One video observation with per-step growth vs the previous one."""

    model_config = ConfigDict(extra="allow")

    observation_id: str
    collection_run_id: str
    observed_at: datetime
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    favorite_count: int | None = None
    view_growth_pct: float | None = None
    like_growth_pct: float | None = None
    comment_growth_pct: float | None = None
    favorite_growth_pct: float | None = None


class MetricDelta(BaseModel):
    """Absolute change and growth % for one metric between two runs."""

    model_config = ConfigDict(extra="allow")

    metric: str
    previous: float | None = None
    current: float | None = None
    absolute_change: float | None = None
    growth_pct: float | None = None


class EntityRunDelta(BaseModel):
    """Per-entity diff between two run snapshots."""

    model_config = ConfigDict(extra="allow")

    entity_id: str
    title: str | None = None
    status: str = "changed"
    metric_deltas: list[MetricDelta] = Field(default_factory=list)


class RunDeltaReport(BaseModel):
    """Snapshot diff of two runs of the same type."""

    model_config = ConfigDict(extra="allow")

    run_id_a: str
    run_id_b: str
    run_type: str
    entity_count_a: int = 0
    entity_count_b: int = 0
    changed: list[EntityRunDelta] = Field(default_factory=list)
    new: list[EntityRunDelta] = Field(default_factory=list)
    disappeared: list[EntityRunDelta] = Field(default_factory=list)


class ObservationGap(BaseModel):
    """A gap longer than the threshold between two consecutive observations."""

    model_config = ConfigDict(extra="allow")

    entity: str
    entity_id: str
    from_observed_at: datetime
    to_observed_at: datetime
    gap_days: float
    min_gap_days: float


class LongitudinalService:
    """Read-only longitudinal analytics over persisted observations."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    def channel_history(self, channel_id: str) -> list[ChannelHistoryPoint]:
        """All observations of a channel, oldest first, with step growth %."""
        observations = self._repos.channels.list_channel_observations(channel_id)
        points: list[ChannelHistoryPoint] = []
        previous = None
        for obs in observations:
            points.append(
                ChannelHistoryPoint(
                    observation_id=obs.observation_id,
                    collection_run_id=obs.collection_run_id,
                    observed_at=obs.observed_at,
                    subscriber_count=obs.subscriber_count,
                    video_count=obs.video_count,
                    view_count=obs.view_count,
                    subscriber_growth_pct=self._growth(
                        obs.subscriber_count,
                        previous.subscriber_count if previous else None,
                    ),
                    video_growth_pct=self._growth(
                        obs.video_count, previous.video_count if previous else None
                    ),
                    view_growth_pct=self._growth(
                        obs.view_count, previous.view_count if previous else None
                    ),
                )
            )
            previous = obs
        return points

    def video_history(self, video_id: str) -> list[VideoHistoryPoint]:
        """All observations of a video, oldest first, with step growth %."""
        observations = self._repos.videos.list_video_observations(video_id)
        points: list[VideoHistoryPoint] = []
        previous = None
        for obs in observations:
            points.append(
                VideoHistoryPoint(
                    observation_id=obs.observation_id,
                    collection_run_id=obs.collection_run_id,
                    observed_at=obs.observed_at,
                    view_count=obs.view_count,
                    like_count=obs.like_count,
                    comment_count=obs.comment_count,
                    favorite_count=obs.favorite_count,
                    view_growth_pct=self._growth(
                        obs.view_count, previous.view_count if previous else None
                    ),
                    like_growth_pct=self._growth(
                        obs.like_count, previous.like_count if previous else None
                    ),
                    comment_growth_pct=self._growth(
                        obs.comment_count,
                        previous.comment_count if previous else None,
                    ),
                    favorite_growth_pct=self._growth(
                        obs.favorite_count,
                        previous.favorite_count if previous else None,
                    ),
                )
            )
            previous = obs
        return points

    @staticmethod
    def _growth(current, previous) -> float | None:
        return StatisticsService.growth(current, previous).value

    # ------------------------------------------------------------------
    def run_deltas(self, run_id_a: str, run_id_b: str) -> RunDeltaReport:
        """Diff two run snapshots (same run type): per-metric change + growth.

        New / disappeared entities are those observed in exactly one of the
        two runs (by ``collection_run_id`` on the observations). Metric deltas
        compare the latest per-entity observation recorded within each run.
        """
        run_a = self._repos.runs.get_run(run_id_a)
        run_b = self._repos.runs.get_run(run_id_b)
        missing = [rid for rid, run in ((run_id_a, run_a), (run_id_b, run_b)) if run is None]
        if missing:
            raise ValueError(f"Unknown run(s): {', '.join(missing)}")
        if run_a.run_type != run_b.run_type:
            raise ValueError(
                f"Run types differ ({run_a.run_type.value} vs {run_b.run_type.value})"
            )

        snapshot_a, metrics, titles = self._snapshot(run_a)
        snapshot_b, _, _ = self._snapshot(run_b)
        ids_a, ids_b = set(snapshot_a), set(snapshot_b)

        changed = [
            EntityRunDelta(
                entity_id=eid,
                title=titles.get(eid),
                status="changed",
                metric_deltas=[
                    self._metric_delta(m, getattr(snapshot_a[eid], m), getattr(snapshot_b[eid], m))
                    for m in metrics
                ],
            )
            for eid in sorted(ids_a & ids_b)  # type: ignore[arg-type]
        ]
        fresh = [
            EntityRunDelta(entity_id=eid, title=titles.get(eid), status="new")
            for eid in sorted(ids_b - ids_a)  # type: ignore[arg-type]
        ]
        vanished = [
            EntityRunDelta(entity_id=eid, title=titles.get(eid), status="disappeared")
            for eid in sorted(ids_a - ids_b)  # type: ignore[arg-type]
        ]
        return RunDeltaReport(
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            run_type=run_a.run_type.value,
            entity_count_a=len(ids_a),
            entity_count_b=len(ids_b),
            changed=changed,
            new=fresh,
            disappeared=vanished,
        )

    def run_entity_deltas(self, run_id: str) -> RunDeltaReport:
        """Diff ``run_id`` against the previous run of the same type."""
        run = self._repos.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        previous: CollectionRun | None = None
        for other in self._repos.runs.list_runs(run_type=run.run_type):
            if other.run_id == run.run_id:
                continue
            if other.started_at < run.started_at and (
                previous is None or other.started_at > previous.started_at
            ):
                previous = other
        if previous is None:
            raise ValueError(f"No earlier {run.run_type.value} run to diff against")
        return self.run_deltas(previous.run_id, run.run_id)

    def _snapshot(
        self, run: CollectionRun
    ) -> tuple[dict[str, Any], tuple[str, ...], dict[str, Any]]:
        run_id = run.run_id
        if run.run_type == RunType.CHANNEL:
            return self._entity_snapshot(
                list_entities=self._repos.channels.list_channels,
                list_observations=lambda cid: self._by_run(
                    self._repos.channels.list_channel_observations(cid), run_id
                ),
                id_field="channel_id",
                metrics=_CHANNEL_METRICS,
            )
        if run.run_type == RunType.VIDEO:
            return self._entity_snapshot(
                list_entities=self._repos.videos.list_videos,
                list_observations=lambda vid: self._by_run(
                    self._repos.videos.list_video_observations(vid), run_id
                ),
                id_field="video_id",
                metrics=_VIDEO_METRICS,
            )
        raise ValueError(f"run deltas do not support {run.run_type.value} runs")

    @staticmethod
    def _by_run(observations: list[Any], run_id: str) -> list[Any]:
        return [obs for obs in observations if obs.collection_run_id == run_id]

    @classmethod
    def _entity_snapshot(
        cls,
        *,
        list_entities: Callable[[], list[Any]],
        list_observations: Callable[[str], list[Any]],
        id_field: str,
        metrics: tuple[str, ...],
    ) -> tuple[dict[str, Any], tuple[str, ...], dict[str, Any]]:
        """Latest observation of each entity in a single run's snapshot.

        ``list_observations`` must already be narrowed to the run under diff
        (see :meth:`_by_run`); for each entity the most recent observation is
        kept so repeated per-run records collapse to one value per metric.
        """
        snapshot: dict[str, Any] = {}
        titles: dict[str, Any] = {}
        for entity in list_entities():
            entity_id = str(getattr(entity, id_field))
            for obs in list_observations(entity_id):
                current = snapshot.get(entity_id)
                if current is None or obs.observed_at >= current.observed_at:
                    snapshot[entity_id] = obs
                    titles[entity_id] = getattr(entity, "title", None)
        return snapshot, metrics, titles

    # ------------------------------------------------------------------
    def observation_gaps(
        self, entity: str, entity_id: str, min_gap_days: float = 7.0
    ) -> list[ObservationGap]:
        """Gaps strictly longer than ``min_gap_days`` between observations."""
        entity = entity.lower()
        if entity == "channel":
            observations = self._repos.channels.list_channel_observations(entity_id)
        elif entity == "video":
            observations = self._repos.videos.list_video_observations(entity_id)
        else:
            raise ValueError("entity must be 'channel' or 'video'")
        gaps: list[ObservationGap] = []
        for previous, current in zip(observations, observations[1:]):
            gap_days = (
                current.observed_at - previous.observed_at
            ).total_seconds() / _SECONDS_PER_DAY
            if gap_days > min_gap_days:
                gaps.append(
                    ObservationGap(
                        entity=entity,
                        entity_id=entity_id,
                        from_observed_at=previous.observed_at,
                        to_observed_at=current.observed_at,
                        gap_days=gap_days,
                        min_gap_days=min_gap_days,
                    )
                )
        return gaps

    # ------------------------------------------------------------------
    @staticmethod
    def _metric_delta(metric: str, previous, current) -> MetricDelta:
        change = (
            None
            if previous is None or current is None
            else float(current) - float(previous)
        )
        return MetricDelta(
            metric=metric,
            previous=previous,
            current=current,
            absolute_change=change,
            growth_pct=StatisticsService.growth(current, previous).value,
        )