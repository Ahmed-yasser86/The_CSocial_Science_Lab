"""Tests for the analytics service."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from SocialScienceResearch.domain.enums import DataAvailability, PercentileBand
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    Comment,
    CommentObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.services import AnalyticsService
from SocialScienceResearch.utils.idgen import utcnow


def _add_video(repos, video_id, *, views, likes, comments, title=None):
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id="UCx",
            title=title or f"Video {video_id}",
            first_observed_run_id="run_1",
        )
    )
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id=f"obs_{video_id}",
            collection_run_id="run_1",
            video_id=video_id,
            observed_at=utcnow(),
            view_count=views,
            like_count=likes,
            comment_count=comments,
        )
    )


@pytest.fixture
def corpus(excel_repos):
    excel_repos.channels.upsert_channel(
        Channel(
            channel_id="UCx",
            url="https://www.youtube.com/channel/UCx",
            title="Example Channel",
            first_observed_run_id="run_1",
        )
    )
    excel_repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_ch",
            collection_run_id="run_1",
            channel_id="UCx",
            observed_at=utcnow(),
            subscriber_count=100000,
            video_count=500,
            view_count=50_000_000,
        )
    )
    _add_video(excel_repos, "v1", views=1000, likes=100, comments=10, title="First")
    _add_video(excel_repos, "v2", views=5000, likes=500, comments=50, title="Second")
    return excel_repos


def test_channel_overview_latest(corpus) -> None:
    overview = AnalyticsService(corpus).channel_overview("UCx")
    assert overview.subscriber_count.value == 100000
    assert overview.subscriber_count.availability == DataAvailability.AVAILABLE
    assert overview.video_count.value == 500
    assert overview.view_count.value == 50_000_000


def test_channel_overview_missing_when_no_observation(excel_repos) -> None:
    overview = AnalyticsService(excel_repos).channel_overview("UCghost")
    assert overview.subscriber_count.availability == DataAvailability.MISSING
    assert overview.subscriber_count.value is None


def test_top_videos_by_views(corpus) -> None:
    top = AnalyticsService(corpus).top_videos("UCx", metric="views", n=1)
    assert len(top) == 1
    assert top[0].video_id == "v2"
    assert top[0].value == 5000
    assert top[0].availability == DataAvailability.AVAILABLE


def test_top_videos_unknown_metric(corpus) -> None:
    with pytest.raises(ValueError):
        AnalyticsService(corpus).top_videos("UCx", metric="vibe_score")


def test_top_videos_missing_observation_ranked_last(corpus) -> None:
    corpus.videos.upsert_video(
        Video(
            video_id="vghost",
            url="https://www.youtube.com/watch?v=vghost",
            channel_id="UCx",
            title="Ghost",
            first_observed_run_id="run_1",
        )
    )
    top = AnalyticsService(corpus).top_videos("UCx", metric="views", n=3)
    last = top[-1]
    assert last.video_id == "vghost"
    assert last.value is None
    assert last.availability == DataAvailability.MISSING


def test_video_engagement_rates(corpus) -> None:
    eng = AnalyticsService(corpus).video_engagement("v1")
    assert eng.views.value == 1000
    # (100 likes + 10 comments) / 1000 views
    assert eng.engagement_rate.value == pytest.approx(0.11)
    assert eng.like_rate.value == pytest.approx(0.10)
    assert eng.comment_rate.value == pytest.approx(0.01)


def test_video_engagement_missing_observation(excel_repos) -> None:
    eng = AnalyticsService(excel_repos).video_engagement("vghost")
    assert eng.views.availability == DataAvailability.MISSING
    assert eng.engagement_rate.availability == DataAvailability.MISSING


def test_video_engagement_division_by_zero_is_unsupported(corpus) -> None:
    corpus.videos.save_video_observation(
        VideoObservation(
            observation_id="obs_zero",
            collection_run_id="run_1",
            video_id="v1",
            observed_at=utcnow(),
            view_count=0,
            like_count=1,
            comment_count=0,
        )
    )
    eng = AnalyticsService(corpus).video_engagement("v1")
    assert eng.engagement_rate.availability == DataAvailability.UNSUPPORTED
    assert eng.engagement_rate.value is None


def _add_comment(repos, comment_id, *, likes, published=None):
    repos.comments.upsert_comment(
        Comment(
            comment_id=comment_id,
            video_id="vid",
            author_name="A",
            comment_text="text",
            published_at=published,
            first_observed_run_id="run_1",
        )
    )
    repos.comments.save_comment_observation(
        CommentObservation(
            observation_id=f"obs_{comment_id}",
            collection_run_id="run_1",
            comment_id=comment_id,
            observed_at=utcnow(),
            like_count=likes,
        )
    )


@pytest.fixture
def comment_corpus(excel_repos):
    for i, likes in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], start=1):
        _add_comment(excel_repos, f"c{i}", likes=likes)
    return excel_repos


def test_comment_percentiles_bands(comment_corpus) -> None:
    result = AnalyticsService(comment_corpus).comment_like_percentiles("vid")
    assert result.availability == DataAvailability.AVAILABLE
    # 10 values 10..100: P90 = 91, P95 = 95.5, P99 = 99.1 (linear interpolation).
    assert result.bands["90"] == pytest.approx(91.0)
    assert result.bands["95"] == pytest.approx(95.5)
    assert result.bands["99"] == pytest.approx(99.1)
    assert result.bands["75"] == pytest.approx(77.5)


def test_comment_percentiles_empty_is_missing(excel_repos) -> None:
    result = AnalyticsService(excel_repos).comment_like_percentiles("vid")
    assert result.availability == DataAvailability.MISSING
    assert result.like_counts == []


def test_comment_velocity_groups_and_counts_missing(excel_repos) -> None:
    _add_comment(
        excel_repos,
        "c1",
        likes=1,
        published=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
    )
    _add_comment(
        excel_repos,
        "c2",
        likes=1,
        published=datetime(2026, 8, 1, 22, 0, tzinfo=timezone.utc),
    )
    _add_comment(
        excel_repos,
        "c3",
        likes=1,
        published=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
    )
    _add_comment(excel_repos, "c4", likes=1, published=None)

    timeline = AnalyticsService(excel_repos).comment_velocity("vid", bucket="day")
    by_bucket = {entry["bucket"]: entry["count"] for entry in timeline}
    assert by_bucket["2026-08-01"] == 2
    assert by_bucket["2026-08-02"] == 1
    assert by_bucket["missing_published_at"] == 1


def test_comment_velocity_invalid_bucket(excel_repos) -> None:
    with pytest.raises(ValueError):
        AnalyticsService(excel_repos).comment_velocity("vid", bucket="fortnight")
