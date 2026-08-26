"""Comparison engine service (B4, ADR-0008).

Compares videos / channels / upload-date periods / cohorts / runs with an
explicit normalization chosen up front:

* ``none`` - the raw latest-observed value, untouched;
* ``per_1k`` - rate per 1000 subscribers via ``StatisticsService.rate``;
* ``z_score`` - z-score ``(x - mean) / std`` computed over the **compared
  set only** (never over a hidden global population), with population
  standard deviation so the flags match ``StatisticsService.outliers``.

Design rules follow the module's "observed, never estimated" ethos:

* Every metric is resolved to its **latest observation** - never fabricated;
* ``None`` values never participate in statistics but always count toward
  ``population_size`` (and rows are annotated ``availability="missing"``),
  so absence is visible, never silently dropped;
* Outliers are **flagged** (``|z| > 3`` via ``StatisticsService.outliers``
  method ``"z"``), never dropped;
* ``percentile_rank`` is the share of the compared set strictly below a
  value on a 0-100 scale with a ``(n - 1)`` denominator, so the maximum of a
  compared set always ranks 100 (and the minimum 0). Ties share the same
  rank. Empty/single-element sets rank a value 100 (nothing above it).
* Every result carries provenance: ``population_size``, ``n`` and ``method``.

``per_1k`` requires a known positive subscriber denominator; when the owning
channel has no subscriber observation the normalized value is ``None``
(availability ``"missing"``) rather than a fabricated ``0.0``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.models import VideoObservation
from SocialScienceResearch.domain.query import PeriodSpec, VideoFilter
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.query_service import QueryService
from SocialScienceResearch.services.statistics_service import StatisticsService

# ----------------------------------------------------------------------
# Normalization control vocabulary
# ----------------------------------------------------------------------


class Normalization(str, Enum):
    """Explicit normalization applied to every compared metric."""

    NONE = "none"
    PER_1K = "per_1k"
    Z_SCORE = "z_score"


#: Video metric name -> ``VideoObservation`` field that supplies the value.
_VIDEO_METRICS: dict[str, str] = {
    "views": "view_count",
    "view_count": "view_count",
    "likes": "like_count",
    "like_count": "like_count",
    "comments": "comment_count",
    "comment_count": "comment_count",
    "favorites": "favorite_count",
    "favorite_count": "favorite_count",
}

#: Channel metric name -> ``ChannelObservation`` field that supplies the value.
_CHANNEL_METRICS: dict[str, str] = {
    "subscribers": "subscriber_count",
    "subscriber_count": "subscriber_count",
    "videos": "video_count",
    "video_count": "video_count",
    "views": "view_count",
    "view_count": "view_count",
}

#: Metrics allowed for upload-date period comparison (entity-aware).
_PERIOD_METRICS: dict[str, dict[str, str]] = {
    "video": _VIDEO_METRICS,
    "channel": _CHANNEL_METRICS,
}

# ----------------------------------------------------------------------
# Result models (framework-agnostic pydantic, ``extra`` allowed so nothing
# is silently stripped by serialization)
# ----------------------------------------------------------------------


class ComparisonMetricRow(BaseModel):
    """One (entity, metric) cell of a comparison table.

    ``value`` is the raw latest-observed value; ``normalized`` is the value
    after the chosen normalization; ``percentile_rank`` ranks the normalized
    value within the compared set; ``is_outlier`` flags ``|z| > 3``.
    """

    model_config = ConfigDict(extra="allow")

    entity_id: str
    title: str | None = None
    metric: str
    value: float | int | None = None
    normalized: float | int | None = None
    percentile_rank: float | None = None
    is_outlier: bool = False
    availability: str = "available"
    observed_at: datetime | None = None


class OutlierSummary(BaseModel):
    """Per-metric outlier report (flag, never drop)."""

    model_config = ConfigDict(extra="allow")

    metric: str
    method: str = "z"
    threshold: float = 3.0
    outlier_count: int = 0
    outlier_values: list[float] = []
    n: int = 0
    population_size: int = 0


class EntityComparison(BaseModel):
    """Comparison table for a set of videos or channels.

    ``population_size`` is the number of table cells requested (entities x
    metrics); ``n`` is the number of cells with an observed (non-``None``)
    value. Absence therefore counts toward the population, never hidden.
    """

    model_config = ConfigDict(extra="allow")

    entity_type: str
    entity_ids: list[str]
    metrics: list[str]
    normalization: str
    population_size: int
    n: int
    method: str
    rows: list[ComparisonMetricRow] = []
    outliers: list[OutlierSummary] = []


class MetricStat(BaseModel):
    """Mean/median of one metric over an entity set with provenance."""

    model_config = ConfigDict(extra="allow")

    metric: str
    mean: float | None = None
    median: float | None = None
    n: int = 0
    population_size: int = 0
    method: str = "mean=arithmetic_mean,median=linear_50th_percentile"


class PeriodSummary(BaseModel):
    """One upload-date (or joined-date) window and its metric stats."""

    model_config = ConfigDict(extra="allow")

    name: str
    start: date
    end: date
    entity_count: int
    n: int
    metrics: list[MetricStat] = []


class PeriodChange(BaseModel):
    """Between-period percent change of a metric mean (previous -> current)."""

    model_config = ConfigDict(extra="allow")

    metric: str
    growth_percent: float | None = None
    method: str = "percent_change"
    n: int = 2


class PeriodComparison(BaseModel):
    """Two upload-date periods compared per metric with growth deltas."""

    model_config = ConfigDict(extra="allow")

    entity: str
    period_a: PeriodSummary
    period_b: PeriodSummary
    changes: list[PeriodChange] = []
    population_size: int
    n: int
    method: str


class Cohort(BaseModel):
    """A named cohort: optional channel scope plus an optional VideoFilter."""

    model_config = ConfigDict(extra="forbid")

    name: str
    channel_id: str | None = None
    filter: VideoFilter | None = None


class CohortSummary(BaseModel):
    """One cohort: video count and per-metric mean/median."""

    model_config = ConfigDict(extra="allow")

    name: str
    count: int
    n: int
    metrics: list[MetricStat] = []


class CohortChange(BaseModel):
    """Between-cohort percent change of a metric mean (previous -> current)."""

    model_config = ConfigDict(extra="allow")

    from_cohort: str
    to_cohort: str
    metric: str
    growth_percent: float | None = None
    method: str = "percent_change"


class CohortComparison(BaseModel):
    """Named cohorts compared by video count and metric means."""

    model_config = ConfigDict(extra="allow")

    cohorts: list[CohortSummary] = []
    changes: list[CohortChange] = []
    population_size: int
    n: int
    method: str


class RunSnapshot(BaseModel):
    """Observation-count snapshot of one collection run."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    started_at: datetime | None = None
    entity_counts: dict[str, int] = {}
    metrics: dict[str, float | None] = {}
    n: int = 0
    population_size: int = 0
    method: str = "run_snapshot_observation_counts"


class RunTransition(BaseModel):
    """New / disappeared entities between two consecutive runs."""

    model_config = ConfigDict(extra="allow")

    from_run: str
    to_run: str
    entity_type: str = "video"
    new_entities: list[str] = []
    disappeared_entities: list[str] = []


class RunComparison(BaseModel):
    """Run-snapshot comparison with entity churn between runs."""

    model_config = ConfigDict(extra="allow")

    run_ids: list[str]
    metrics: list[str]
    snapshots: list[RunSnapshot] = []
    transitions: list[RunTransition] = []
    population_size: int
    n: int
    method: str = "run_snapshot_observation_counts"


class JobSnapshot(BaseModel):
    """Aggregated snapshot of one collection job's child runs.

    ``entity_counts`` sum the distinct entities observed across the job's
    child runs (a video seen in two child runs counts once); ``metrics``
    pool every child-run observation into one mean (never an average of
    averages).
    """

    model_config = ConfigDict(extra="allow")

    job_id: str
    kind: str | None = None
    status: str | None = None
    run_count: int = 0
    run_ids: list[str] = []
    started_at: datetime | None = None
    finished_at: datetime | None = None
    entity_counts: dict[str, int] = {}
    metrics: dict[str, float | None] = {}
    n: int = 0
    population_size: int = 0
    method: str = "job_aggregated_child_run_observation_counts"


class JobComparison(BaseModel):
    """Two jobs compared via their aggregated child-run metrics."""

    model_config = ConfigDict(extra="allow")

    job_ids: list[str]
    metrics: list[str]
    snapshots: list[JobSnapshot] = []
    transitions: list[RunTransition] = []
    population_size: int
    n: int
    method: str = "job_aggregated_child_run_observation_counts"


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------


class ComparisonService:
    """Compares entities / periods / cohorts / runs with explicit normalization.

    Statistics (ratio, rate, growth, mean, median, outliers) are delegated to
    :class:`SocialScienceResearch.services.statistics_service.StatisticsService`
    (ADR-0006) so ratio math has a single home.
    """

    def __init__(
        self, repos: Repositories, settings: SocialScienceSettings | None = None
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()

    # ------------------------------------------------------------------
    # Entity comparisons (videos / channels)
    # ------------------------------------------------------------------
    def compare_videos(
        self,
        video_ids: list[str],
        metrics: list[str],
        normalization: str | Normalization = Normalization.NONE,
    ) -> EntityComparison:
        """Compare videos on their latest observed metrics.

        ``z_score`` normalization is computed over the compared set only.
        """
        if not video_ids:
            raise ValueError("video_ids must not be empty")
        if not metrics:
            raise ValueError("metrics must not be empty")
        norm = Normalization(normalization)
        fields = self._metric_fields("video", metrics)
        ids = list(dict.fromkeys(video_ids))
        latest = self._repos.videos.get_latest_video_observations(ids)
        meta = {vid: self._repos.videos.get_video(vid) for vid in ids}
        channel_ids = sorted(
            {v.channel_id for v in meta.values() if v is not None and v.channel_id}
        )
        subs = (
            self._repos.channels.get_latest_channel_observations(channel_ids)
            if channel_ids
            else {}
        )
        denominators = {
            vid: subs[meta[vid].channel_id].subscriber_count  # type: ignore[union-attr]
            for vid in ids
            if meta[vid] is not None
            and meta[vid].channel_id
            and meta[vid].channel_id in subs
        }
        return self._entity_table("video", ids, fields, latest, meta, denominators, norm)

    def compare_channels(
        self,
        channel_ids: list[str],
        metrics: list[str],
        normalization: str | Normalization = Normalization.NONE,
    ) -> EntityComparison:
        """Compare channels on their latest observed statistics.

        ``per_1k`` uses each channel's own subscriber count as the population.
        """
        if not channel_ids:
            raise ValueError("channel_ids must not be empty")
        if not metrics:
            raise ValueError("metrics must not be empty")
        norm = Normalization(normalization)
        fields = self._metric_fields("channel", metrics)
        ids = list(dict.fromkeys(channel_ids))
        latest = self._repos.channels.get_latest_channel_observations(ids)
        meta = {cid: self._repos.channels.get_channel(cid) for cid in ids}
        denominators = {
            cid: latest[cid].subscriber_count
            for cid in ids
            if cid in latest and latest[cid].subscriber_count is not None
        }
        return self._entity_table("channel", ids, fields, latest, meta, denominators, norm)

    # ------------------------------------------------------------------
    # Period / cohort / run comparisons
    # ------------------------------------------------------------------
    def compare_periods(
        self,
        period_a: PeriodSpec,
        period_b: PeriodSpec,
        entity: str = "video",
        metrics: list[str] | None = None,
    ) -> PeriodComparison:
        """Compare two upload-date windows (videos) or joined-date windows
        (channels) per metric, plus between-period growth of the means."""
        entity = entity.lower()
        if entity not in _PERIOD_METRICS:
            raise ValueError(f"entity must be 'video' or 'channel', got {entity!r}")
        if period_a.end < period_a.start:
            raise ValueError("period_a.end must be >= period_a.start")
        if period_b.end < period_b.start:
            raise ValueError("period_b.end must be >= period_b.start")
        if not metrics:
            raise ValueError("metrics must not be empty")
        fields = self._metric_fields(entity, metrics)

        a_summary = self._period_summary(
            period_a, entity, fields, default_name="period_a"
        )
        b_summary = self._period_summary(
            period_b, entity, fields, default_name="period_b"
        )
        changes: list[PeriodChange] = []
        for metric in fields:
            mean_a = next(
                (s.mean for s in a_summary.metrics if s.metric == metric), None
            )
            mean_b = next(
                (s.mean for s in b_summary.metrics if s.metric == metric), None
            )
            g = StatisticsService.growth(mean_b, mean_a)
            changes.append(
                PeriodChange(metric=metric, growth_percent=g.value, n=g.n, method=g.method)
            )
        method = (
            "upload_date_windows+latest_observation"
            if entity == "video"
            else "joined_date_windows+latest_observation"
        )
        return PeriodComparison(
            entity=entity,
            period_a=a_summary,
            period_b=b_summary,
            changes=changes,
            population_size=a_summary.entity_count + b_summary.entity_count,
            n=a_summary.n + b_summary.n,
            method=method,
        )

    def compare_cohorts(
        self,
        cohorts: list[Cohort],
        metrics: list[str] | None = None,
    ) -> CohortComparison:
        """Compare named video cohorts (channel scope + VideoFilter).

        Between-cohort changes are computed for consecutive cohorts in the
        order given, using ``StatisticsService.growth`` of the cohort means.
        """
        if not cohorts:
            raise ValueError("cohorts must not be empty")
        if not metrics:
            raise ValueError("metrics must not be empty")
        fields = self._metric_fields("video", metrics)
        query = QueryService(self._repos, self._settings)

        summaries: list[CohortSummary] = []
        for cohort in cohorts:
            rows = query.resolve_latest_rows("video", filter=cohort.filter)
            if cohort.channel_id is not None:
                rows = [r for r in rows if r.get("channel_id") == cohort.channel_id]
            stats: list[MetricStat] = []
            n_total = 0
            for metric, field in fields.items():
                values = [r.get(field) for r in rows]
                m = StatisticsService.mean(values)
                med = StatisticsService.median(values)
                stats.append(
                    MetricStat(
                        metric=metric,
                        mean=m.value,
                        median=med.value,
                        n=m.n,
                        population_size=m.population_size,
                    )
                )
                n_total += m.n
            summaries.append(
                CohortSummary(name=cohort.name, count=len(rows), n=n_total, metrics=stats)
            )

        changes: list[CohortChange] = []
        for prev, cur in zip(summaries, summaries[1:]):
            for metric in fields:
                mean_prev = next(s.mean for s in prev.metrics if s.metric == metric)
                mean_cur = next(s.mean for s in cur.metrics if s.metric == metric)
                g = StatisticsService.growth(mean_cur, mean_prev)
                changes.append(
                    CohortChange(
                        from_cohort=prev.name,
                        to_cohort=cur.name,
                        metric=metric,
                        growth_percent=g.value,
                        method=g.method,
                    )
                )
        return CohortComparison(
            cohorts=summaries,
            changes=changes,
            population_size=sum(s.count for s in summaries),
            n=sum(s.n for s in summaries),
            method="video_filter_cohorts+latest_observation",
        )

    def compare_runs(
        self,
        run_ids: list[str],
        metrics: list[str] | None = None,
    ) -> RunComparison:
        """Compare collection-run snapshots by observation counts.

        Each snapshot counts the distinct videos / channels / comments
        observed in the run and the per-metric mean over that run's video
        observations. Transitions between consecutive runs report which video
        ids appeared / disappeared (observed entities only, never inferred).
        """
        if not run_ids:
            raise ValueError("run_ids must not be empty")
        if not metrics:
            raise ValueError("metrics must not be empty")
        runs = {}
        for rid in run_ids:
            run = self._repos.runs.get_run(rid)
            if run is None:
                raise ValueError(f"Unknown run id {rid!r}")
            runs[rid] = run
        fields = self._metric_fields("video", metrics)

        video_obs_by_run: dict[str, list[VideoObservation]] = defaultdict(list)
        videos_by_run: dict[str, set[str]] = defaultdict(set)
        for video in self._repos.videos.list_videos():
            for obs in self._repos.videos.list_video_observations(video.video_id):
                video_obs_by_run[obs.collection_run_id].append(obs)
                videos_by_run[obs.collection_run_id].add(video.video_id)

        channels_by_run: dict[str, set[str]] = defaultdict(set)
        for channel in self._repos.channels.list_channels():
            for obs in self._repos.channels.list_channel_observations(channel.channel_id):
                channels_by_run[obs.collection_run_id].add(channel.channel_id)

        comments_by_run: dict[str, set[str]] = defaultdict(set)
        for comment in self._repos.comments.list_comments():
            for obs in self._repos.comments.list_comment_observations(comment.comment_id):
                comments_by_run[obs.collection_run_id].add(comment.comment_id)

        snapshots: list[RunSnapshot] = []
        for rid in run_ids:
            obs_list = video_obs_by_run.get(rid, [])
            metric_means: dict[str, float | None] = {}
            n_total = 0
            for metric, field in fields.items():
                values = [getattr(o, field, None) for o in obs_list]
                m = StatisticsService.mean(values)
                metric_means[metric] = m.value
                n_total += m.n
            snapshots.append(
                RunSnapshot(
                    run_id=rid,
                    started_at=runs[rid].started_at,
                    entity_counts={
                        "videos": len(videos_by_run.get(rid, ())),
                        "channels": len(channels_by_run.get(rid, ())),
                        "comments": len(comments_by_run.get(rid, ())),
                    },
                    metrics=metric_means,
                    n=n_total,
                    population_size=len(obs_list),
                    method="run_snapshot_observation_counts",
                )
            )

        transitions: list[RunTransition] = []
        for a, b in zip(run_ids, run_ids[1:]):
            from_ids = videos_by_run.get(a, set())
            to_ids = videos_by_run.get(b, set())
            transitions.append(
                RunTransition(
                    from_run=a,
                    to_run=b,
                    entity_type="video",
                    new_entities=sorted(to_ids - from_ids),
                    disappeared_entities=sorted(from_ids - to_ids),
                )
            )

        return RunComparison(
            run_ids=run_ids,
            metrics=list(fields.keys()),
            snapshots=snapshots,
            transitions=transitions,
            population_size=len(run_ids),
            n=len(run_ids),
            method="run_snapshot_observation_counts",
        )

    def compare_jobs(
        self,
        job_ids: list[str],
        metrics: list[str] | None = None,
    ) -> JobComparison:
        """Compare two jobs by their AGGREGATED child-run observations.

        Each job's child runs (``CollectionRun.job_id`` linkage, plan J1) are
        resolved and pooled: entity counts are distinct across the job's runs
        and metric means are computed over ALL of the job's video
        observations together (never an average of per-run averages).
        Transitions report which video ids appeared / disappeared between
        consecutive jobs' entity sets. Reuses the same observed-only scan as
        :meth:`compare_runs`.
        """
        job_ids = list(dict.fromkeys(job_ids))
        if len(job_ids) < 2:
            raise ValueError("compare_jobs requires at least two distinct job_ids")
        fields = self._metric_fields("video", metrics or ["views", "likes", "comments"])

        runs_by_job: dict[str, list[Any]] = defaultdict(list)
        for run in self._repos.runs.list_runs():
            if run.job_id in job_ids:
                runs_by_job[run.job_id].append(run)
        for job_id in job_ids:
            if not runs_by_job.get(job_id):
                raise ValueError(f"Job {job_id!r} has no child runs")

        video_obs_by_run: dict[str, list[VideoObservation]] = defaultdict(list)
        videos_by_run: dict[str, set[str]] = defaultdict(set)
        for video in self._repos.videos.list_videos():
            for obs in self._repos.videos.list_video_observations(video.video_id):
                video_obs_by_run[obs.collection_run_id].append(obs)
                videos_by_run[obs.collection_run_id].add(video.video_id)

        channels_by_run: dict[str, set[str]] = defaultdict(set)
        for channel in self._repos.channels.list_channels():
            for obs in self._repos.channels.list_channel_observations(channel.channel_id):
                channels_by_run[obs.collection_run_id].add(channel.channel_id)

        comments_by_run: dict[str, set[str]] = defaultdict(set)
        for comment in self._repos.comments.list_comments():
            for obs in self._repos.comments.list_comment_observations(comment.comment_id):
                comments_by_run[obs.collection_run_id].add(comment.comment_id)

        job_rows = (
            {j.job_id: j for j in (self._repos.jobs.list_jobs() or [])}
            if getattr(self._repos, "jobs", None) is not None
            else {}
        )

        snapshots: list[JobSnapshot] = []
        videos_by_job: dict[str, set[str]] = {}
        for job_id in job_ids:
            child_runs = sorted(runs_by_job[job_id], key=lambda r: r.started_at)
            run_ids = [r.run_id for r in child_runs]
            all_obs = [
                obs for rid in run_ids for obs in video_obs_by_run.get(rid, [])
            ]
            metric_means: dict[str, float | None] = {}
            n_total = 0
            for metric, field in fields.items():
                values = [getattr(o, field, None) for o in all_obs]
                m = StatisticsService.mean(values)
                metric_means[metric] = m.value
                n_total += m.n
            job_row = job_rows.get(job_id)
            started = min((r.started_at for r in child_runs), default=None)
            finished = max(
                (r.finished_at for r in child_runs if r.finished_at), default=None
            )
            videos_by_job[job_id] = {
                vid for rid in run_ids for vid in videos_by_run.get(rid, ())
            }
            snapshots.append(
                JobSnapshot(
                    job_id=job_id,
                    kind=getattr(job_row, "kind", None),
                    status=getattr(job_row, "status", None),
                    run_count=len(run_ids),
                    run_ids=run_ids,
                    started_at=started,
                    finished_at=finished,
                    entity_counts={
                        "videos": len(videos_by_job[job_id]),
                        "channels": len(
                            {c for rid in run_ids for c in channels_by_run.get(rid, ())}
                        ),
                        "comments": len(
                            {c for rid in run_ids for c in comments_by_run.get(rid, ())}
                        ),
                    },
                    metrics=metric_means,
                    n=n_total,
                    population_size=len(all_obs),
                    method="job_aggregated_child_run_observation_counts",
                )
            )

        transitions: list[RunTransition] = []
        for a, b in zip(job_ids, job_ids[1:]):
            from_ids = videos_by_job.get(a, set())
            to_ids = videos_by_job.get(b, set())
            transitions.append(
                RunTransition(
                    from_run=a,
                    to_run=b,
                    entity_type="video",
                    new_entities=sorted(to_ids - from_ids),
                    disappeared_entities=sorted(from_ids - to_ids),
                )
            )

        return JobComparison(
            job_ids=job_ids,
            metrics=list(fields.keys()),
            snapshots=snapshots,
            transitions=transitions,
            population_size=len(job_ids),
            n=sum(s.n for s in snapshots),
            method="job_aggregated_child_run_observation_counts",
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _entity_table(
        self,
        entity_type: str,
        ids: list[str],
        fields: dict[str, str],
        latest: dict[str, Any],
        meta: dict[str, Any],
        denominators: dict[str, int | None],
        norm: Normalization,
    ) -> EntityComparison:
        rows: list[ComparisonMetricRow] = []
        outlier_summaries: list[OutlierSummary] = []
        for metric, field in fields.items():
            values = [
                getattr(latest.get(i), field, None) if latest.get(i) is not None else None
                for i in ids
            ]
            denom = [denominators.get(i) for i in ids]
            normalized = self._normalize(values, denominators=denom, norm=norm)
            ranks = self._percentile_ranks(normalized)
            usable = [v for v in normalized if v is not None]
            out = StatisticsService.outliers(usable, method="z", threshold=3.0)
            flagged = set(out.outlier_values)
            for idx, i in enumerate(ids):
                rows.append(
                    ComparisonMetricRow(
                        entity_id=i,
                        title=meta[i].title if meta.get(i) is not None else None,
                        metric=metric,
                        value=values[idx],
                        normalized=normalized[idx],
                        percentile_rank=ranks[idx],
                        is_outlier=normalized[idx] is not None
                        and normalized[idx] in flagged,
                        availability="available" if values[idx] is not None else "missing",
                        observed_at=latest[i].observed_at if latest.get(i) is not None else None,
                    )
                )
            outlier_summaries.append(
                OutlierSummary(
                    metric=metric,
                    method=out.method,
                    threshold=out.threshold,
                    outlier_count=len(out.outlier_values),
                    outlier_values=out.outlier_values,
                    n=out.n,
                    population_size=out.population_size,
                )
            )
        n = sum(1 for r in rows if r.value is not None)
        return EntityComparison(
            entity_type=entity_type,
            entity_ids=list(ids),
            metrics=list(fields.keys()),
            normalization=norm.value,
            population_size=len(rows),
            n=n,
            method=f"latest_observation+{norm.value}",
            rows=rows,
            outliers=outlier_summaries,
        )

    def _period_summary(
        self,
        period: PeriodSpec,
        entity: str,
        fields: dict[str, str],
        default_name: str,
    ) -> PeriodSummary:
        name = period.name or default_name
        stats: list[MetricStat] = []
        n_total = 0
        if entity == "video":
            selected = [
                v
                for v in self._repos.videos.list_videos()
                if v.upload_date is not None and period.start <= v.upload_date <= period.end
            ]
            latest = self._repos.videos.get_latest_video_observations(
                [v.video_id for v in selected]
            )
            for metric, field in fields.items():
                values = [
                    getattr(latest[v.video_id], field, None) if v.video_id in latest else None
                    for v in selected
                ]
                m = StatisticsService.mean(values)
                med = StatisticsService.median(values)
                stats.append(
                    MetricStat(
                        metric=metric, mean=m.value, median=med.value,
                        n=m.n, population_size=m.population_size,
                    )
                )
                n_total += m.n
        else:
            selected = [
                c
                for c in self._repos.channels.list_channels()
                if c.joined_date is not None
                and period.start <= c.joined_date <= period.end
            ]
            latest = self._repos.channels.get_latest_channel_observations(
                [c.channel_id for c in selected]
            )
            for metric, field in fields.items():
                values = [
                    getattr(latest[c.channel_id], field, None) if c.channel_id in latest else None
                    for c in selected
                ]
                m = StatisticsService.mean(values)
                med = StatisticsService.median(values)
                stats.append(
                    MetricStat(
                        metric=metric, mean=m.value, median=med.value,
                        n=m.n, population_size=m.population_size,
                    )
                )
                n_total += m.n
        return PeriodSummary(
            name=name,
            start=period.start,
            end=period.end,
            entity_count=len(selected),
            n=n_total,
            metrics=stats,
        )

    @staticmethod
    def _metric_fields(entity: str, metrics: list[str]) -> dict[str, str]:
        registry = _PERIOD_METRICS.get(entity, _VIDEO_METRICS)
        fields: dict[str, str] = {}
        for m in metrics:
            key = m.lower()
            if key not in registry:
                raise ValueError(
                    f"Unknown {entity} metric {m!r}; expected one of "
                    f"{sorted(set(registry))}"
                )
            fields[key] = registry[key]
        return fields

    @staticmethod
    def _normalize(
        values: list[float | int | None],
        *,
        denominators: list[int | None],
        norm: Normalization,
    ) -> list[float | int | None]:
        if norm is Normalization.NONE:
            return list(values)
        if norm is Normalization.PER_1K:
            out: list[float | int | None] = []
            for value, pop in zip(values, denominators):
                if value is None or not pop:
                    out.append(None)
                else:
                    out.append(StatisticsService.rate(value, pop).value)
            return out
        if norm is Normalization.Z_SCORE:
            # z-score over the compared set only (population std, matching
            # StatisticsService.outliers(method="z")).
            usable = [float(v) for v in values if v is not None]
            n = len(usable)
            if n == 0:
                return list(values)
            mean = sum(usable) / n
            if n == 1:
                return [0.0 if v is not None else None for v in values]
            var = sum((x - mean) ** 2 for x in usable) / n
            std = var ** 0.5
            if std == 0:
                return [0.0 if v is not None else None for v in values]
            return [
                None if v is None else (float(v) - mean) / std for v in values
            ]
        raise ValueError(f"unsupported normalization {norm!r}")

    @staticmethod
    def _percentile_ranks(
        values: list[float | int | None],
    ) -> list[float | None]:
        """Share of the compared set strictly below each value, 0-100.

        Uses a ``(n - 1)`` denominator so the maximum of a compared set always
        ranks 100 and the minimum 0; ties share a rank. ``None`` values rank
        ``None`` and single-element sets rank 100 (nothing above them).
        """
        usable = [v for v in values if v is not None]
        n = len(usable)
        if n == 0:
            return [None] * len(values)
        if n == 1:
            return [100.0 if v is not None else None for v in values]
        out: list[float | None] = []
        for v in values:
            if v is None:
                out.append(None)
                continue
            below = sum(1 for x in usable if x < v)
            out.append(below / (n - 1) * 100.0)
        return out
