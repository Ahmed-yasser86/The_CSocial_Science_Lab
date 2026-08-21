"""Tests for the ComparisonService (B4, ADR-0008).

Covers the normalization contract (``none`` | ``per_1k`` | ``z_score``),
percentile ranks and outlier flags over the compared set, period growth,
cohort comparisons, run snapshots/churn and one end-to-end endpoint call.

Assertions pin known values:
* ``z_score`` of a 2-element set is symmetric around 0,
* ``per_1k`` of 1000 views / 100000 subscribers == 10.0,
* the max video of a compared set ranks percentile 100,
* growth from 100 -> 150 == 50%.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.query import PeriodSpec
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.comparison_service import Cohort, ComparisonService

PREFIX = "/api/v1/social-science"


# ----------------------------------------------------------------------
# Seeding helpers (deterministic, no network)
# ----------------------------------------------------------------------
def _seed_run(repos, run_id: str, started_at: datetime) -> None:
    repos.runs.create_run(
        CollectionRun(
            run_id=run_id,
            run_type=RunType.CHANNEL,
            target_url="https://www.youtube.com/@cmp",
            started_at=started_at,
            status="success",
        )
    )


def _seed_channel(
    repos,
    channel_id: str,
    title: str,
    subscribers: int,
    *,
    views: int | None = None,
    videos: int | None = None,
    joined_date: date | None = None,
    run_id: str = "run_cmp",
    observed_at: datetime | None = None,
) -> None:
    repos.channels.upsert_channel(
        Channel(
            channel_id=channel_id,
            url=f"https://www.youtube.com/channel/{channel_id}",
            title=title,
            joined_date=joined_date,
            first_observed_run_id=run_id,
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id=f"obs_{channel_id}",
            collection_run_id=run_id,
            channel_id=channel_id,
            observed_at=observed_at,
            subscriber_count=subscribers,
            video_count=videos,
            view_count=views,
        )
    )


def _seed_video(
    repos,
    video_id: str,
    channel_id: str,
    title: str,
    upload_date: date,
    views: int,
    *,
    likes: int | None = None,
    comments: int | None = None,
    run_id: str = "run_cmp",
    observed_at: datetime | None = None,
) -> None:
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            title=title,
            duration=300,
            upload_date=upload_date,
            first_observed_run_id=run_id,
        )
    )
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id=f"obs_{video_id}",
            collection_run_id=run_id,
            video_id=video_id,
            observed_at=observed_at,
            view_count=views,
            like_count=likes,
            comment_count=comments,
        )
    )


# ----------------------------------------------------------------------
# Video comparison
# ----------------------------------------------------------------------
def test_compare_videos_z_score_two_element_set_is_symmetric(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_z", fixed_now)
    _seed_channel(excel_repos, "ch_z", "Z Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "z1", "ch_z", "Z1", date(2026, 1, 1), views=1000,
                run_id="run_z", observed_at=fixed_now)
    _seed_video(excel_repos, "z2", "ch_z", "Z2", date(2026, 1, 2), views=3000,
                run_id="run_z", observed_at=fixed_now)

    service = ComparisonService(excel_repos, None)
    result = service.compare_videos(["z1", "z2"], ["views"], normalization="z_score")

    by_id = {r.entity_id: r for r in result.rows}
    assert by_id["z1"].normalized == pytest.approx(-1.0)
    assert by_id["z2"].normalized == pytest.approx(1.0)
    assert result.normalization == "z_score"
    assert result.population_size == 2
    assert result.n == 2


def test_compare_videos_per_1k_rate(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_p", fixed_now)
    _seed_channel(excel_repos, "ch_p", "P Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "p1", "ch_p", "P1", date(2026, 1, 1), views=1000,
                run_id="run_p", observed_at=fixed_now)

    service = ComparisonService(excel_repos, None)
    result = service.compare_videos(["p1"], ["views"], normalization="per_1k")

    assert result.rows[0].normalized == pytest.approx(10.0)
    assert result.rows[0].value == 1000


def test_compare_videos_percentile_rank_max_is_100(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_q", fixed_now)
    _seed_channel(excel_repos, "ch_q", "Q Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "q1", "ch_q", "Q1", date(2026, 1, 1), views=100,
                run_id="run_q", observed_at=fixed_now)
    _seed_video(excel_repos, "q2", "ch_q", "Q2", date(2026, 1, 2), views=200,
                run_id="run_q", observed_at=fixed_now)
    _seed_video(excel_repos, "q3", "ch_q", "Q3", date(2026, 1, 3), views=300,
                run_id="run_q", observed_at=fixed_now)

    service = ComparisonService(excel_repos, None)
    result = service.compare_videos(
        ["q1", "q2", "q3"], ["views"], normalization="none"
    )

    by_id = {r.entity_id: r for r in result.rows}
    assert by_id["q3"].percentile_rank == pytest.approx(100.0)
    assert by_id["q1"].percentile_rank == pytest.approx(0.0)
    assert result.outliers[0].outlier_count == 0


def test_compare_videos_missing_observation_is_flagged_not_dropped(
    excel_repos, fixed_now
) -> None:
    _seed_run(excel_repos, "run_m", fixed_now)
    _seed_channel(excel_repos, "ch_m", "M Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "m1", "ch_m", "M1", date(2026, 1, 1), views=100,
                run_id="run_m", observed_at=fixed_now)
    _seed_video(excel_repos, "m2", "ch_m", "M2", date(2026, 1, 2), views=200,
                run_id="run_m", observed_at=fixed_now)
    excel_repos.videos.upsert_video(
        Video(
            video_id="m3",
            url="https://www.youtube.com/watch?v=m3",
            channel_id="ch_m",
            title="M3",
            duration=300,
            upload_date=date(2026, 1, 3),
            first_observed_run_id="run_m",
        )
    )

    service = ComparisonService(excel_repos, None)
    result = service.compare_videos(["m1", "m2", "m3"], ["views"])

    by_id = {r.entity_id: r for r in result.rows}
    assert by_id["m3"].value is None
    assert by_id["m3"].normalized is None
    assert by_id["m3"].availability == "missing"
    assert result.population_size == 3
    assert result.n == 2


# ----------------------------------------------------------------------
# Channel comparison
# ----------------------------------------------------------------------
def test_compare_channels_subscribers_and_views(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_c", fixed_now)
    _seed_channel(excel_repos, "c1", "C1", 1000, views=10_000, videos=50,
                  observed_at=fixed_now, run_id="run_c")
    _seed_channel(excel_repos, "c2", "C2", 3000, views=30_000, videos=150,
                  observed_at=fixed_now, run_id="run_c")

    service = ComparisonService(excel_repos, None)
    result = service.compare_channels(["c1", "c2"], ["subscribers", "views"])

    by_id = {(r.entity_id, r.metric): r for r in result.rows}
    assert result.entity_type == "channel"
    assert by_id[("c1", "subscribers")].value == 1000
    assert by_id[("c2", "views")].value == 30_000
    assert result.n == 4


# ----------------------------------------------------------------------
# Period comparison
# ----------------------------------------------------------------------
def test_compare_periods_growth_100_to_150(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_g", fixed_now)
    _seed_channel(excel_repos, "ch_g", "G Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "g1", "ch_g", "G1", date(2026, 1, 10), views=100,
                run_id="run_g", observed_at=fixed_now)
    _seed_video(excel_repos, "g2", "ch_g", "G2", date(2026, 3, 10), views=150,
                run_id="run_g", observed_at=fixed_now)

    period_a = PeriodSpec(name="jan", start=date(2026, 1, 1), end=date(2026, 1, 31))
    period_b = PeriodSpec(name="mar", start=date(2026, 3, 1), end=date(2026, 3, 31))

    service = ComparisonService(excel_repos, None)
    result = service.compare_periods(period_a, period_b, entity="video", metrics=["views"])

    assert result.period_a.entity_count == 1
    assert result.period_b.entity_count == 1
    assert result.period_a.metrics[0].mean == pytest.approx(100.0)
    assert result.period_b.metrics[0].mean == pytest.approx(150.0)
    assert result.changes[0].growth_percent == pytest.approx(50.0)


def test_compare_periods_empty_window_has_zero_count(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_e", fixed_now)
    _seed_channel(excel_repos, "ch_e", "E Channel", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "e1", "ch_e", "E1", date(2026, 1, 10), views=100,
                run_id="run_e", observed_at=fixed_now)

    period_a = PeriodSpec(name="jan", start=date(2026, 1, 1), end=date(2026, 1, 31))
    period_b = PeriodSpec(name="apr", start=date(2026, 4, 1), end=date(2026, 4, 30))

    service = ComparisonService(excel_repos, None)
    result = service.compare_periods(period_a, period_b, entity="video", metrics=["views"])

    assert result.period_a.entity_count == 1
    assert result.period_b.entity_count == 0
    assert result.changes[0].growth_percent is None  # undefined, never inf


# ----------------------------------------------------------------------
# Cohort comparison
# ----------------------------------------------------------------------
def test_compare_cohorts_by_channel(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_co", fixed_now)
    _seed_channel(excel_repos, "ch_a", "A", 100_000, observed_at=fixed_now)
    _seed_channel(excel_repos, "ch_b", "B", 100_000, observed_at=fixed_now)
    _seed_video(excel_repos, "a1", "ch_a", "A1", date(2026, 1, 1), views=100,
                run_id="run_co", observed_at=fixed_now)
    _seed_video(excel_repos, "b1", "ch_b", "B1", date(2026, 1, 2), views=200,
                run_id="run_co", observed_at=fixed_now)

    cohorts = [
        Cohort(name="channel_a", channel_id="ch_a"),
        Cohort(name="channel_b", channel_id="ch_b"),
    ]

    service = ComparisonService(excel_repos, None)
    result = service.compare_cohorts(cohorts, metrics=["views"])

    assert result.cohorts[0].count == 1
    assert result.cohorts[0].metrics[0].mean == pytest.approx(100.0)
    assert result.cohorts[1].metrics[0].mean == pytest.approx(200.0)
    assert result.changes[0].growth_percent == pytest.approx(100.0)
    assert result.changes[0].from_cohort == "channel_a"
    assert result.changes[0].to_cohort == "channel_b"


# ----------------------------------------------------------------------
# Run comparison
# ----------------------------------------------------------------------
def test_compare_runs_new_and_disappeared(excel_repos) -> None:
    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    _seed_run(excel_repos, "run_1", t1)
    _seed_run(excel_repos, "run_2", t2)
    _seed_channel(excel_repos, "ch_r", "R", 100_000, observed_at=t2, run_id="run_1")
    _seed_video(excel_repos, "r_only1", "ch_r", "Only1", date(2026, 1, 1), views=10,
                run_id="run_1", observed_at=t1)
    _seed_video(excel_repos, "r_only2", "ch_r", "Only2", date(2026, 1, 2), views=20,
                run_id="run_2", observed_at=t2)
    _seed_video(excel_repos, "r_both", "ch_r", "Both", date(2026, 1, 1), views=5,
                run_id="run_1", observed_at=t1)
    excel_repos.videos.save_video_observation(
        VideoObservation(
            observation_id="obs_both_2",
            collection_run_id="run_2",
            video_id="r_both",
            observed_at=t2,
            view_count=8,
        )
    )

    service = ComparisonService(excel_repos, None)
    result = service.compare_runs(["run_1", "run_2"], ["views"])

    assert result.snapshots[0].entity_counts["videos"] == 2  # r_only1, r_both
    assert result.snapshots[1].entity_counts["videos"] == 2  # r_only2, r_both
    assert result.snapshots[1].metrics["views"] == pytest.approx(14.0)  # mean(20, 8)
    assert result.transitions[0].new_entities == ["r_only2"]
    assert result.transitions[0].disappeared_entities == ["r_only1"]


def test_compare_runs_unknown_run_raises_value_error(excel_repos, fixed_now) -> None:
    _seed_run(excel_repos, "run_ok", fixed_now)
    service = ComparisonService(excel_repos, None)
    with pytest.raises(ValueError):
        service.compare_runs(["run_ok", "run_missing"], ["views"])


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def test_compare_videos_empty_ids_raise_value_error(excel_repos, fixed_now) -> None:
    service = ComparisonService(excel_repos, None)
    with pytest.raises(ValueError):
        service.compare_videos([], ["views"])


def test_compare_videos_unknown_metric_raises_value_error(
    excel_repos, fixed_now
) -> None:
    _seed_run(excel_repos, "run_b", fixed_now)
    _seed_video(excel_repos, "b1", "ch_b", "B1", date(2026, 1, 1), views=1,
                run_id="run_b", observed_at=fixed_now)
    service = ComparisonService(excel_repos, None)
    with pytest.raises(ValueError):
        service.compare_videos(["b1"], ["bogus"])


# ----------------------------------------------------------------------
# End-to-end endpoint
# ----------------------------------------------------------------------
def test_comparison_videos_endpoint(tmp_path, fixed_now) -> None:
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="cmp_api")
    repos = build_excel_repositories(repo_settings)
    _seed_run(repos, "run_e2e", fixed_now)
    _seed_channel(repos, "ch_e", "E", 100_000, observed_at=fixed_now)
    _seed_video(repos, "e1", "ch_e", "E1", date(2026, 1, 1), views=100,
                run_id="run_e2e", observed_at=fixed_now)
    _seed_video(repos, "e2", "ch_e", "E2", date(2026, 1, 2), views=200,
                run_id="run_e2e", observed_at=fixed_now)
    repos.store.close()

    settings = SocialScienceSettings(
        repository=repo_settings, api=ApiSettings(prefix=PREFIX)
    )
    app = create_app(settings)
    client = TestClient(app)

    resp = client.post(
        f"{PREFIX}/comparison/videos",
        json={
            "video_ids": ["e1", "e2"],
            "metrics": ["views"],
            "normalization": "none",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "video"
    assert data["population_size"] == 2
    assert data["n"] == 2
    assert len(data["rows"]) == 2
    by_id = {r["entity_id"]: r for r in data["rows"]}
    assert by_id["e1"]["value"] == 100
    assert by_id["e2"]["value"] == 200

    empty = client.post(
        f"{PREFIX}/comparison/videos",
        json={"video_ids": [], "metrics": ["views"]},
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "invalid_argument"

    unknown_metric = client.post(
        f"{PREFIX}/comparison/videos",
        json={"video_ids": ["e1", "e2"], "metrics": ["bogus"]},
    )
    assert unknown_metric.status_code == 400