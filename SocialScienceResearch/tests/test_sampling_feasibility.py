"""Tests for ``SamplingService.feasibility`` (US-32/33 pre-sample planning)."""

from __future__ import annotations

import pytest

from SocialScienceResearch.domain.models import (
    Channel,
    Comment,
    Video,
    VideoObservation,
)
from SocialScienceResearch.services import SamplingService
from SocialScienceResearch.utils.idgen import utcnow


def _add_video(repos, video_id, *, channel_id, views=None, likes=0, comments=0):
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            title=f"Video {video_id}",
            first_observed_run_id="run_feas",
        )
    )
    if views is not None:
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_{video_id}",
                collection_run_id="run_feas",
                video_id=video_id,
                observed_at=utcnow(),
                view_count=views,
                like_count=likes,
                comment_count=comments,
            )
        )


def _add_comment(repos, comment_id, video_id, *, channel_id, run_id, likes=None):
    repos.channels.upsert_channel(
        Channel(
            channel_id=channel_id,
            url=f"https://www.youtube.com/channel/{channel_id}",
            title=f"Channel {channel_id}",
            first_observed_run_id=run_id,
        )
    )
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            title=f"Video {video_id}",
            first_observed_run_id=run_id,
        )
    )
    repos.comments.upsert_comment(
        Comment(
            comment_id=comment_id,
            video_id=video_id,
            author_name=f"user_{comment_id}",
            first_observed_run_id=run_id,
        )
    )
    if likes is not None:
        from SocialScienceResearch.domain.models import CommentObservation

        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"cob_{comment_id}",
                collection_run_id=run_id,
                comment_id=comment_id,
                observed_at=utcnow(),
                like_count=likes,
            )
        )


def test_video_feasibility_counts_metric_availability(excel_repos) -> None:
    # v1, v2 have views; v3 has no observation (missing metric).
    _add_video(excel_repos, "v1", channel_id="UCx", views=1000)
    _add_video(excel_repos, "v2", channel_id="UCx", views=5000)
    _add_video(excel_repos, "v3", channel_id="UCx", views=None)
    svc = SamplingService(excel_repos)
    result = svc.feasibility("video", channel_id="UCx", metric="views", requested_size=2)
    assert result["population_size"] == 3
    assert result["available_metric"] == 2
    assert result["missing_metric"] == 1
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["max_sample_size"] == 3
    assert result["recommended_sample_size"] == 2


def test_video_feasibility_caps_to_population(excel_repos) -> None:
    _add_video(excel_repos, "v1", channel_id="UCx", views=1000)
    svc = SamplingService(excel_repos)
    result = svc.feasibility("video", channel_id="UCx", requested_size=10)
    # requested exceeds population -> recommended capped to population.
    assert result["recommended_sample_size"] == 1
    assert result["max_sample_size"] == 1


def test_comment_feasibility_scoped_by_run(excel_repos) -> None:
    _add_comment(excel_repos, "c1", "v1", channel_id="UCx", run_id="r1", likes=5)
    _add_comment(excel_repos, "c2", "v1", channel_id="UCx", run_id="r1")
    # c3 belongs to a different run and must be excluded from the scope.
    _add_comment(excel_repos, "c3", "v2", channel_id="UCy", run_id="r2", likes=9)
    svc = SamplingService(excel_repos)
    result = svc.feasibility(
        "comment", channel_id="UCx", run_ids=["r1"], metric="likes"
    )
    assert result["population_size"] == 2
    assert result["available_metric"] == 1
    assert result["missing_metric"] == 1


def test_invalid_entity_type_raises(excel_repos) -> None:
    svc = SamplingService(excel_repos)
    with pytest.raises(ValueError):
        svc.feasibility("channel")
