"""Tests for domain models: structure, provenance, raw preservation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from SocialScienceResearch.domain.models import (
    ChannelObservation,
    CollectionRun,
    Video,
    VideoObservation,
)


def test_video_has_no_time_varying_counters(sample_video: Video) -> None:
    """Counters must live on observations, never on the video entity."""
    assert not hasattr(sample_video, "view_count")
    with pytest.raises(AttributeError):
        _ = sample_video.view_count  # type: ignore[attr-defined]


def test_video_observation_carries_run_and_raw(sample_video_observation: VideoObservation) -> None:
    obs = sample_video_observation
    assert obs.collection_run_id == "run_test_20260810_000000_abc12345"
    assert obs.observed_at.tzinfo is not None
    assert obs.raw_json == {}


def test_video_observation_repeated_runs_do_not_overwrite(sample_video: Video) -> None:
    """Two runs produce two distinct observations, preserving history."""
    obs1 = VideoObservation(
        observation_id="obs_a",
        collection_run_id="run_1",
        video_id=sample_video.video_id,
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        view_count=100,
    )
    obs2 = VideoObservation(
        observation_id="obs_b",
        collection_run_id="run_2",
        video_id=sample_video.video_id,
        observed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        view_count=200,
    )
    assert obs1.observation_id != obs2.observation_id
    assert obs1.view_count == 100
    assert obs2.view_count == 200


def test_channel_observation_missing_fields_stay_none() -> None:
    obs = ChannelObservation(
        observation_id="obs_c",
        collection_run_id="run_1",
        channel_id="UCx",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert obs.subscriber_count is None
    assert obs.view_count is None


def test_collection_run_defaults(sample_run: CollectionRun) -> None:
    assert sample_run.status == "pending"
    assert sample_run.entities_discovered == 0
    assert sample_run.finished_at is None
    assert sample_run.provider == "yt-dlp"


def test_raw_json_preserved_on_entity() -> None:
    raw = {"view_count": 999, "channel": "payload"}
    obs = ChannelObservation(
        observation_id="o",
        collection_run_id="r",
        channel_id="c",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        raw_json=raw,
    )
    assert obs.raw_json == raw


def test_model_serializable_to_dict(sample_video_observation: VideoObservation) -> None:
    d = sample_video_observation.model_dump()
    assert d["video_id"] == sample_video_observation.video_id
    assert d["collection_run_id"] == sample_video_observation.collection_run_id
