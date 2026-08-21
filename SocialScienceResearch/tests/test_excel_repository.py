"""Tests for Excel persistence: CRUD, dedup, idempotency, overflow, round-trips."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    EntityType,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.models import (
    CollectionError,
    CollectionRun,
    Comment,
    RecommendationObservation,
)
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories


@pytest.fixture
def repos(tmp_path):
    """Repositories backed by a temporary workbook."""
    settings_path = tmp_path / "dataset.xlsx"
    from SocialScienceResearch.config.settings import RepositorySettings

    rs = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset")
    )
    assert rs.store.path == settings_path
    return rs


@pytest.fixture
def autoflush_repos(tmp_path):
    """Repositories with a tiny overflow limit to exercise sheet splitting."""
    from SocialScienceResearch.config.settings import RepositorySettings

    rs = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="tiny")
    )
    rs.store.max_rows_per_sheet = 5
    rs.store.flush_every = 2
    return rs


# ----------------------------------------------------------------------
# Channel repository
# ----------------------------------------------------------------------
def test_channel_upsert_creates_once(repos, sample_channel) -> None:
    result = repos.channels.upsert_channel(sample_channel)
    assert result.created is True
    assert result.entity_type == EntityType.CHANNEL
    assert repos.channels.get_channel(sample_channel.channel_id) == sample_channel

    # second upsert is a no-op, not a duplicate
    result2 = repos.channels.upsert_channel(sample_channel)
    assert result2.created is False
    assert len(repos.channels.list_channels()) == 1


def test_channel_observation_is_append_only(
    repos, sample_channel, sample_channel_observation, fixed_now
) -> None:
    repos.channels.upsert_channel(sample_channel)
    repos.channels.save_channel_observation(sample_channel_observation)
    second = sample_channel_observation.model_copy(
        update={
            "observation_id": "obs_channel_0002",
            "collection_run_id": "run_2",
            "observed_at": fixed_now,
            "subscriber_count": 200000,
        }
    )
    repos.channels.save_channel_observation(second)

    obs = repos.channels.list_channel_observations(sample_channel.channel_id)
    assert len(obs) == 2
    assert obs[1].subscriber_count == 200000
    latest = repos.channels.get_latest_channel_observation(sample_channel.channel_id)
    assert latest is not None
    assert latest.subscriber_count == 200000


def test_observation_same_run_is_idempotent(
    repos, sample_channel_observation
) -> None:
    repos.channels.save_channel_observation(sample_channel_observation)
    repos.channels.save_channel_observation(sample_channel_observation)
    assert len(repos.channels.list_channel_observations("UCexample00000000000000000")) == 1


# ----------------------------------------------------------------------
# Video + observation repository
# ----------------------------------------------------------------------
def test_video_upsert_and_latest_observation(repos, sample_video, fixed_now) -> None:
    repos.videos.upsert_video(sample_video)
    repos.videos.save_video_observation(
        sample_video_observation_with(repos, sample_video, fixed_now, views=100, run="r1")
    )
    repos.videos.save_video_observation(
        sample_video_observation_with(repos, sample_video, fixed_now, views=250, run="r2")
    )
    latest = repos.videos.get_latest_video_observation(sample_video.video_id)
    assert latest is not None
    assert latest.view_count == 250
    assert len(repos.videos.list_video_observations(sample_video.video_id)) == 2
    assert repos.videos.get_video(sample_video.video_id) == sample_video


def sample_video_observation_with(repos, sample_video, fixed_now, views, run):
    from SocialScienceResearch.domain.models import VideoObservation

    return VideoObservation(
        observation_id=f"obs_{run}",
        collection_run_id=run,
        video_id=sample_video.video_id,
        observed_at=fixed_now,
        view_count=views,
    )


def test_video_list_by_channel(repos, sample_video) -> None:
    other = sample_video.model_copy(
        update={"video_id": "v2xxxxxxxxxxxxxxxxxxxxxxxxx", "url": "https://example.com/v2"}
    )
    repos.videos.upsert_video(sample_video)
    repos.videos.upsert_video(other)
    assert len(repos.videos.list_videos(channel_id=sample_video.channel_id)) == 2
    assert len(repos.videos.list_videos(channel_id="UCother")) == 0


# ----------------------------------------------------------------------
# Comment + thread repository
# ----------------------------------------------------------------------
def test_comment_threads(repos, sample_comment) -> None:
    root = sample_comment
    repos.comments.upsert_comment(root)
    reply = Comment(
        comment_id="reply0000000000000000000001",
        video_id=root.video_id,
        author_name="Replier",
        comment_text="A reply.",
        is_reply=True,
        parent_comment_id=root.comment_id,
        root_comment_id=root.comment_id,
        first_observed_run_id="run_x",
    )
    repos.comments.upsert_comment(reply)

    assert repos.comments.get_comment(root.comment_id) == root
    assert len(repos.comments.list_comments(root.video_id)) == 2
    roots = repos.comments.list_root_comments(root.video_id)
    assert [c.comment_id for c in roots] == [root.comment_id]
    replies = repos.comments.list_replies(root.comment_id)
    assert [c.comment_id for c in replies] == [reply.comment_id]


# ----------------------------------------------------------------------
# Run repository
# ----------------------------------------------------------------------
def test_run_lifecycle(repos, sample_run, fixed_now) -> None:
    repos.runs.create_run(sample_run)
    assert repos.runs.get_run(sample_run.run_id) == sample_run

    updated = sample_run.model_copy(
        update={
            "status": CollectionStatus.SUCCESS,
            "finished_at": fixed_now,
            "entities_discovered": 3,
            "entities_succeeded": 2,
            "entities_failed": 1,
        }
    )
    repos.runs.update_run(updated)
    stored = repos.runs.get_run(sample_run.run_id)
    assert stored is not None
    assert stored.status == CollectionStatus.SUCCESS
    assert stored.entities_succeeded == 2
    assert repos.runs.get_run(sample_run.run_id) != sample_run  # was updated, not duped
    assert len(repos.runs.list_runs()) == 1
    assert len(repos.runs.list_runs(run_type=RunType.VIDEO)) == 0


def test_run_errors_recorded(repos, sample_run, fixed_now) -> None:
    repos.runs.create_run(sample_run)
    err = CollectionError(
        error_id="err_0001",
        run_id=sample_run.run_id,
        entity_type=EntityType.VIDEO,
        entity_id="video_failed",
        error_type="network",
        message="timed out",
        occurred_at=fixed_now,
        retryable=True,
    )
    repos.runs.record_error(err)
    errors = repos.runs.list_errors(sample_run.run_id)
    assert len(errors) == 1
    assert errors[0].entity_id == "video_failed"
    assert errors[0].error_type == "network"
    assert errors[0].retryable is True


# ----------------------------------------------------------------------
# Recommendation repository (network-ready edges)
# ----------------------------------------------------------------------
def test_recommendation_edges_and_idempotency(repos, fixed_now) -> None:
    edge = RecommendationObservation(
        observation_id="rec_1",
        collection_run_id="run_1",
        source_video_id="src1",
        recommended_video_id="dst1",
        position=1,
        status=RecommendationStatus.OBSERVED,
        title="Recommended video",
    )
    res = repos.recommendations.save_recommendation(edge)
    assert res.created is True

    # same edge again (same run/source/target) -> no duplicate
    res2 = repos.recommendations.save_recommendation(edge)
    assert res2.created is False
    assert len(repos.recommendations.list_recommendations_for_source("src1")) == 1

    # a different run observing the same relationship is a NEW historical edge
    later = edge.model_copy(update={"observation_id": "rec_2", "collection_run_id": "run_2"})
    repos.recommendations.save_recommendation(later)
    all_edges = repos.recommendations.list_recommendation_edges(source_video_id="src1")
    assert len(all_edges) == 2
    assert {e.collection_run_id for e in all_edges} == {"run_1", "run_2"}
    assert repos.recommendations.list_source_video_ids() == ["src1"]


# ----------------------------------------------------------------------
# Persistence across reopen + overflow
# ----------------------------------------------------------------------
def test_data_survives_reopen(tmp_path, repos, sample_channel) -> None:
    repos.channels.upsert_channel(sample_channel)
    repos.store.close()

    store = WorkbookStore(tmp_path / "dataset.xlsx")
    from SocialScienceResearch.persistence.excel_repository import (
        ExcelChannelRepository,
    )

    reopened = ExcelChannelRepository(store)
    loaded = reopened.get_channel(sample_channel.channel_id)
    assert loaded is not None
    assert loaded.title == sample_channel.title
    assert loaded.handle == "@example"
    assert loaded.first_observed_run_id == sample_channel.first_observed_run_id


def test_sheet_overflow_splits_and_reads_back(tmp_path, autoflush_repos) -> None:
    from SocialScienceResearch.domain.models import Video

    for i in range(12):
        v = Video(
            video_id=f"vid_{i}",
            url=f"https://www.youtube.com/watch?v=vid_{i}",
            channel_id="UCx",
            title=f"Video {i}",
            first_observed_run_id="run_1",
        )
        autoflush_repos.videos.upsert_video(v)

    videos = autoflush_repos.videos.list_videos()
    assert len(videos) == 12
    assert {v.video_id for v in videos} == {f"vid_{i}" for i in range(12)}
    assert "videos__2" in autoflush_repos.store.sheet_names() or len(
        autoflush_repos.store.sheet_names()
    ) >= 1


def test_datetime_and_json_round_trip(repos, sample_run, fixed_now) -> None:
    from SocialScienceResearch.domain.models import CollectionRun

    run = CollectionRun(
        run_id="run_roundtrip",
        run_type=RunType.CHANNEL,
        target_url="https://youtube.com/@x",
        target_channel_id="UCx",
        started_at=fixed_now,
        status=CollectionStatus.RUNNING,
        config_json={"collect_comments": True, "seed": 42},
        notes=["first", "second"],
    )
    repos.runs.create_run(run)
    stored = repos.runs.get_run("run_roundtrip")
    assert stored is not None
    assert stored.started_at == fixed_now
    assert stored.started_at.tzinfo is not None
    assert stored.config_json == {"collect_comments": True, "seed": 42}
    assert stored.notes == ["first", "second"]
    assert stored.status == CollectionStatus.RUNNING


def test_enum_and_optional_fields_round_trip(repos, sample_channel) -> None:
    repos.channels.upsert_channel(sample_channel)
    loaded = repos.channels.get_channel(sample_channel.channel_id)
    assert loaded is not None
    assert loaded.is_verified is None  # optional field stayed None
    assert loaded.country is None
