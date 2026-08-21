"""Tests for normalization: raw yt-dlp payloads -> domain models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from SocialScienceResearch.acquisition.normalization import (
    normalize_channel,
    normalize_channel_observation,
    normalize_comments,
    normalize_recommendations,
    normalize_video,
    normalize_video_observation,
)
from SocialScienceResearch.domain.enums import RecommendationStatus

FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "run_test_0001"


def _load(name: str):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


def test_normalize_video_basic() -> None:
    raw = _load("video_raw.json")
    video = normalize_video(raw, RUN_ID)
    assert video is not None
    assert video.video_id == "v1example0000000000000000001"
    assert video.channel_id == "UCexample00000000000000000"
    assert video.title == "An Example Research Video"
    assert video.duration == 618
    assert video.upload_date.isoformat() == "2024-01-15"
    assert video.upload_timestamp == datetime(2024, 1, 15, 10, 20, tzinfo=timezone.utc)
    assert video.tags == ["research", "demo"]
    assert video.categories == ["Science & Technology"]
    assert video.language == "en"
    assert video.live_status == "not_live"
    assert video.availability == "public"
    assert video.age_limit == 0
    assert video.is_short is False
    assert len(video.chapters_json) == 2
    assert video.first_observed_run_id == RUN_ID
    assert video.raw_json["id"] == "v1example0000000000000000001"


def test_normalize_video_no_time_varying_stats() -> None:
    raw = _load("video_raw.json")
    video = normalize_video(raw, RUN_ID)
    assert video is not None
    assert not hasattr(video, "view_count")


def test_normalize_video_observation() -> None:
    raw = _load("video_raw.json")
    obs = normalize_video_observation(raw, RUN_ID, observed_at=datetime(
        2026, 1, 1, tzinfo=timezone.utc
    ))
    assert obs is not None
    assert obs.video_id == "v1example0000000000000000001"
    assert obs.view_count == 1234567
    assert obs.like_count == 45678
    assert obs.comment_count == 987
    assert obs.observed_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert obs.collection_run_id == RUN_ID


def test_normalize_video_live_status_flows_for_upcoming() -> None:
    raw = _load("video_raw.json")
    raw["live_status"] = "is_upcoming"
    video = normalize_video(raw, RUN_ID)
    assert video is not None
    assert video.live_status == "is_upcoming"
    obs = normalize_video_observation(raw, RUN_ID)
    assert obs is not None
    # The observation preserves the live status in its provenance payload.
    assert obs.raw_json["live_status"] == "is_upcoming"


def test_normalize_video_missing_fields() -> None:
    raw = {"id": "abc", "title": "Minimal"}
    video = normalize_video(raw, RUN_ID)
    assert video is not None
    assert video.duration is None
    assert video.upload_date is None
    assert video.upload_timestamp is None
    assert video.tags == []
    assert video.channel_id is None


def test_normalize_video_url_fallback() -> None:
    raw = {"id": "abc123", "title": "No URL"}
    video = normalize_video(raw, RUN_ID)
    assert video is not None
    assert video.url == "https://www.youtube.com/watch?v=abc123"


def test_normalize_video_none_for_no_id() -> None:
    assert normalize_video({"title": "no id"}, RUN_ID) is None


def test_normalize_channel() -> None:
    raw = _load("channel_raw.json")
    channel = normalize_channel(raw, RUN_ID)
    assert channel is not None
    assert channel.channel_id == "UCexample00000000000000000"
    assert channel.title == "Example Channel"
    assert channel.handle == "@example"
    assert channel.avatar_url == "https://example.com/avatar.jpg"
    assert channel.first_observed_run_id == RUN_ID
    assert channel.url == "https://www.youtube.com/channel/UCexample00000000000000000"


def test_normalize_channel_observation() -> None:
    raw = _load("channel_raw.json")
    obs = normalize_channel_observation(raw, RUN_ID)
    assert obs is not None
    assert obs.subscriber_count == 100000
    assert obs.video_count == 500
    assert obs.view_count == 50000000
    assert obs.collection_run_id == RUN_ID


def test_normalize_comments_thread_structure() -> None:
    raw_comments = _load("comments_raw.json")
    comments, observations = normalize_comments(
        raw_comments, video_id="vid1", run_id=RUN_ID,
        observed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    assert len(comments) == 3
    assert len(observations) == 3

    by_id = {c.comment_id: c for c in comments}
    root = by_id["Ugxrootcomment0000000000001"]
    reply = by_id["Ugxreplycomment0000000000001"]
    assert root.is_reply is False
    assert root.root_comment_id == root.comment_id
    assert reply.is_reply is True
    assert reply.parent_comment_id == "Ugxrootcomment0000000000001"
    assert reply.root_comment_id == "Ugxrootcomment0000000000001"
    assert reply.is_author is True

    # observations capture collection time, not publish time
    obs = {o.comment_id: o for o in observations}
    assert obs["Ugxrootcomment0000000000001"].observed_at == datetime(
        2026, 2, 1, tzinfo=timezone.utc
    )
    assert obs["Ugxrootcomment0000000000001"].like_count == 42
    assert obs["Ugxrootcomment0000000000001"].reply_count == 2
    # published_at is preserved on the comment entity
    assert root.published_at == datetime(2024, 1, 15, 10, 20, tzinfo=timezone.utc)


def test_normalize_comments_cycle_safe() -> None:
    """A pathological parent chain must not hang normalization."""
    raw = [
        {"id": "c1", "text": "a", "parent": "c2"},
        {"id": "c2", "text": "b", "parent": "c1"},
    ]
    comments, _ = normalize_comments(raw, video_id="v", run_id="r")
    by_id = {c.comment_id: c for c in comments}
    # roots remain unresolved rather than hanging
    assert by_id["c1"].root_comment_id is None
    assert by_id["c2"].root_comment_id is None


def test_normalize_recommendations_positions() -> None:
    raw_entries = [
        {"id": "rec1", "title": "One", "channel_id": "UCx"},
        {"id": "rec2", "title": "Two"},
        {"id": "rec3"},
    ]
    edges = normalize_recommendations(
        "src_video", raw_entries, run_id="run_1",
        observed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    assert len(edges) == 3
    assert [e.position for e in edges] == [0, 1, 2]
    assert all(e.status == RecommendationStatus.OBSERVED for e in edges)
    assert edges[0].recommended_video_id == "rec1"
    assert edges[0].channel_id == "UCx"
    assert edges[0].collection_run_id == "run_1"


def test_normalize_recommendations_extracts_channel_name() -> None:
    raw_entries = [
        {"id": "r1", "channel_id": "UCa", "channel": "Channel Alpha"},
        {"id": "r2", "channel": {"id": "UCb", "name": "Channel Beta"}},
        {"id": "r3", "uploader": "Plain Uploader"},
        {"id": "r4", "channel_id": "UCd"},
        {"id": "r5"},
    ]
    edges = normalize_recommendations("src", raw_entries, run_id="run_1")
    by_id = {e.recommended_video_id: e for e in edges}
    assert by_id["r1"].channel_name == "Channel Alpha"
    assert by_id["r1"].channel_id == "UCa"
    assert by_id["r2"].channel_name == "Channel Beta"
    assert by_id["r2"].channel_id is None
    assert by_id["r3"].channel_name == "Plain Uploader"
    assert by_id["r4"].channel_id == "UCd"
    assert by_id["r4"].channel_name is None
    assert by_id["r5"].channel_name is None
