"""Service-layer tests: channel, video and recommendation workflows.

The acquisition provider is a deterministic in-memory fake; persistence is the
real Excel backend on a temp directory. No network access.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from SocialScienceResearch.acquisition.base import AcquisitionProvider, ChannelExtract
from SocialScienceResearch.acquisition.errors import (
    InvalidURLError,
    LiveEventSkipError,
    RecommendationUnsupportedError,
    VideoUnavailableError,
)
from SocialScienceResearch.config.settings import (
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
)
from SocialScienceResearch.domain.collection import CollectionSpec, CollectionTarget
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    EntityType,
    ErrorType,
    RunType,
    TargetKind,
)
from SocialScienceResearch.domain.query import Operator, QueryCondition, QueryGroup
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services import CollectionService, RecommendationService

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


class FakeAcquisitionProvider(AcquisitionProvider):
    """In-memory provider: returns fixture payloads, never hits the network."""

    def __init__(
        self,
        channel_raw: dict[str, Any] | None = None,
        videos: dict[str, dict[str, Any]] | None = None,
        recommendations: list[dict[str, Any]] | None = None,
        *,
        fail_videos: set[str] | None = None,
        rec_unsupported: bool = False,
        live_videos: set[str] | None = None,
    ) -> None:
        self.channel_raw = channel_raw
        self.videos = videos or {}
        self.recommendations = recommendations
        self.fail_videos = fail_videos or set()
        self.rec_unsupported = rec_unsupported
        self.live_videos = live_videos or set()
        self.video_calls: list[str] = []

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        if self.channel_raw is None:
            raise InvalidURLError(f"No channel for {channel_url}")
        return ChannelExtract(
            channel={k: v for k, v in self.channel_raw.items() if k != "entries"},
            videos=list(self.channel_raw.get("entries", [])),
        )

    def extract_video(self, video_url: str) -> dict[str, Any]:
        self.video_calls.append(video_url)
        video_id = video_url.rsplit("v=", 1)[-1]
        if video_id in self.fail_videos:
            raise VideoUnavailableError(f"Video unavailable: {video_id}")
        if video_id in self.live_videos:
            raise LiveEventSkipError(
                "This live event will begin in a few moments."
            )
        if video_id in self.videos:
            return self.videos[video_id]
        raise InvalidURLError(f"No video for {video_url}")

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        if self.rec_unsupported or self.recommendations is None:
            raise RecommendationUnsupportedError(
                "yt-dlp cannot provide recommendations"
            )
        return self.recommendations


def _build_service(
    tmp_path, provider, *, collection=None, collect_comments=True, enrich_video_stats=False,
    scraper=None,
):
    from SocialScienceResearch.config.settings import SocialScienceSettings

    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="svc"),
        scraper=scraper
        or ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=collection
        or CollectionSettings(
            collect_comments=collect_comments,
            enrich_video_stats=enrich_video_stats,
        ),
    )
    repos = build_excel_repositories(settings.repository)
    return CollectionService(provider, repos, settings=settings)


def _channel_spec(**overrides) -> CollectionSpec:
    defaults = {
        "targets": [
            CollectionTarget(
                kind=TargetKind.CHANNEL,
                url="https://www.youtube.com/@example",
            )
        ],
        "collect_comments": False,
        "collect_transcripts": False,
    }
    defaults.update(overrides)
    return CollectionSpec(**defaults)


# ----------------------------------------------------------------------
# Channel workflow
# ----------------------------------------------------------------------
def test_collect_channel_flat_success(tmp_path) -> None:
    channel_raw = _load("channel_raw.json")
    provider = FakeAcquisitionProvider(channel_raw=channel_raw)
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    assert result.run_type == RunType.CHANNEL
    assert result.entities_created == 2
    assert result.entities_existing == 0
    assert result.entities_failed == 0
    assert result.errors == []

    channels = service._repos.channels.list_channels()
    assert len(channels) == 1
    assert channels[0].channel_id == "UCexample00000000000000000"

    videos = service._repos.videos.list_videos(channel_id="UCexample00000000000000000")
    assert {v.video_id for v in videos} == {
        "v1example0000000000000000001",
        "v2example0000000000000000002",
    }

    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.status == CollectionStatus.SUCCESS
    assert run.entities_discovered == 2
    assert run.entities_succeeded == 2
    assert run.provider == "yt-dlp"
    assert run.target_channel_id == "UCexample00000000000000000"
    assert run.config_json["collect_comments"] is False


def test_collect_channel_re_run_is_idempotent(tmp_path) -> None:
    provider = FakeAcquisitionProvider(channel_raw=_load("channel_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)

    first = service.collect_channel("https://www.youtube.com/@example")
    second = service.collect_channel("https://www.youtube.com/@example")

    assert first.entities_created == 2
    assert second.entities_created == 0
    assert second.entities_existing == 2
    assert len(service._repos.videos.list_videos()) == 2  # no duplicates
    assert len(service._repos.runs.list_runs()) == 2  # one run per collection


def test_video_criteria_filters_discovered_videos(tmp_path) -> None:
    provider = FakeAcquisitionProvider(channel_raw=_load("channel_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)
    spec = _channel_spec(
        video_criteria=QueryGroup(
            operator="AND",
            conditions=[
                QueryCondition(
                    variable="title", operator=Operator.CONTAINS, value="Research"
                )
            ],
        ),
    )

    result = service.collect_channel(
        "https://www.youtube.com/@example", spec=spec
    )

    assert result.status == CollectionStatus.SUCCESS
    assert result.entities_discovered == 2
    assert result.entities_created == 1
    videos = service._repos.videos.list_videos(
        channel_id="UCexample00000000000000000"
    )
    assert {v.video_id for v in videos} == {
        "v1example0000000000000000001"
    }
    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.config_json["video_criteria"] is not None


def test_video_criteria_unknown_variable_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown variable 'nope'"):
        _channel_spec(
            video_criteria=QueryGroup(
                operator="AND",
                conditions=[
                    QueryCondition(variable="nope", operator=Operator.EQ, value=1)
                ],
            ),
        )


def test_max_videos_per_channel_caps_discovered(tmp_path) -> None:
    provider = FakeAcquisitionProvider(channel_raw=_load("channel_raw.json"))
    service = _build_service(
        tmp_path,
        provider,
        collect_comments=False,
        collection=CollectionSettings(
            max_videos_per_channel=1, enrich_video_stats=False
        ),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    assert result.entities_created == 1
    videos = service._repos.videos.list_videos(
        channel_id="UCexample00000000000000000"
    )
    assert len(videos) == 1


def test_collect_channel_deep_enrichment(tmp_path) -> None:
    channel_raw = _load("channel_raw.json")
    video_raw = _load("video_raw.json")
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        videos={"v1example0000000000000000001": video_raw},
    )
    service = _build_service(
        tmp_path,
        provider,
        collection=CollectionSettings(
            enrich_video_stats=True, collect_comments=False, max_videos_to_enrich=1
        ),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    # Only the first video was deep-enriched (bounded by max_videos_to_enrich).
    assert provider.video_calls == [
        "https://www.youtube.com/watch?v=v1example0000000000000000001"
    ]
    latest = service._repos.videos.get_latest_video_observation(
        "v1example0000000000000000001"
    )
    assert latest is not None
    assert latest.like_count == 45678  # captured from the deep payload


def test_collect_channel_default_settings_deep_enriches_and_persists_stats(
    tmp_path,
) -> None:
    """Channel runs use the module defaults: deep enrichment ON by default so
    likes/comments are captured, bounded by the default per-run cap."""
    channel_raw = _load("channel_raw.json")
    v1 = _load("video_raw.json")
    v1 = {**v1, "comments": _load("comments_raw.json")}
    v2 = {
        "id": "v2example0000000000000000002",
        "webpage_url": (
            "https://www.youtube.com/watch?v=v2example0000000000000000002"
        ),
        "title": "Second Video",
        "channel_id": "UCexample00000000000000000",
        "view_count": 5000,
        "like_count": 321,
        "comment_count": 12,
    }
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        videos={
            "v1example0000000000000000001": v1,
            "v2example0000000000000000002": v2,
        },
    )
    service = _build_service(tmp_path, provider, collection=CollectionSettings())

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    assert result.entities_created == 2
    # Both discovered videos were deep-enriched by default (concurrently, so
    # call order is not deterministic - only the set of enriched videos is).
    assert sorted(provider.video_calls) == [
        "https://www.youtube.com/watch?v=v1example0000000000000000001",
        "https://www.youtube.com/watch?v=v2example0000000000000000002",
    ]
    latest_v1 = service._repos.videos.get_latest_video_observation(
        "v1example0000000000000000001"
    )
    assert latest_v1 is not None
    assert latest_v1.like_count == 45678
    assert latest_v1.comment_count == 987
    latest_v2 = service._repos.videos.get_latest_video_observation(
        "v2example0000000000000000002"
    )
    assert latest_v2 is not None
    assert latest_v2.like_count == 321

    # Comments from the deep payload are persisted.
    comments = service._repos.comments.list_comments(
        "v1example0000000000000000001"
    )
    assert len(comments) == 3
    assert result.comments_collected == 3

    # The resolved config recorded on the run reflects the new defaults.
    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.config_json["enrich_video_stats"] is True
    assert run.config_json["max_videos_to_enrich"] == 50
    assert run.config_json["collect_comments"] is True


def test_collect_channel_no_enrich_persists_flat_observation_not_observed(
    tmp_path,
) -> None:
    """Without deep enrichment only the flat entry is persisted: view_count is
    observed but likes/comments stay None (not-observed) - never fabricated 0."""
    channel_raw = _load("channel_raw.json")
    provider = FakeAcquisitionProvider(channel_raw=channel_raw)  # no deep payloads
    service = _build_service(
        tmp_path, provider, collect_comments=False, enrich_video_stats=False
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []
    assert provider.video_calls == []  # no deep extraction requested
    latest = service._repos.videos.get_latest_video_observation(
        "v1example0000000000000000001"
    )
    assert latest is not None
    assert latest.view_count == 1234567  # stable metadata observed
    assert latest.like_count is None  # not observed, not fabricated
    assert latest.comment_count is None  # not observed, not fabricated


def test_can_enrich_boundaries(tmp_path) -> None:
    service = _build_service(tmp_path, FakeAcquisitionProvider(channel_raw={}))

    # Unbounded cap: every video may be enriched.
    allowed, reason = service._can_enrich(9, 100, {"max_videos_to_enrich": None})
    assert allowed is True
    assert reason is None

    # Cap reached exactly at ``cap`` collected videos (1-based count).
    allowed, reason = service._can_enrich(1, 2, {"max_videos_to_enrich": 2})
    assert allowed is True
    assert reason is None

    # Strictly beyond the cap the video is skipped and the reason is observable.
    allowed, reason = service._can_enrich(2, 3, {"max_videos_to_enrich": 2})
    assert allowed is False
    assert reason is not None
    assert "enrichment quota" in reason


def test_can_enrich_cap_slots_when_skipping(tmp_path) -> None:
    """A channel run with a per-run enrichment cap deep-enriches exactly the
    first ``max_videos_to_enrich`` videos and records the rest as skipped."""
    channel_raw = {
        **_load("channel_raw.json"),
        "entries": [
            {
                "id": f"v3example000000000000000003{i}",
                "url": (
                    f"https://www.youtube.com/watch?v=v3example000000000000000003{i}"
                ),
                "title": f"Video {i}",
                "view_count": 1000 + i,
            }
            for i in range(1, 4)
        ],
    }
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        videos={
            f"v3example000000000000000003{i}": {
                "id": f"v3example000000000000000003{i}",
                "url": (
                    f"https://www.youtube.com/watch?v=v3example000000000000000003{i}"
                ),
                "title": f"Video {i}",
                "channel_id": "UCexample00000000000000000",
                "view_count": 1000 + i,
                "like_count": 10 * i,
                "comment_count": i,
            }
            for i in range(1, 4)
        },
    )
    service = _build_service(
        tmp_path,
        provider,
        collection=CollectionSettings(
            enrich_video_stats=True, collect_comments=False, max_videos_to_enrich=2
        ),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    # Exactly the first two videos deep-enriched; the third is skipped.
    assert len(provider.video_calls) == 2
    assert sorted(provider.video_calls) == [
        "https://www.youtube.com/watch?v=v3example0000000000000000031",
        "https://www.youtube.com/watch?v=v3example0000000000000000032",
    ]
    assert len(result.skipped) == 1
    assert result.skipped[0]["video_id"] == "v3example0000000000000000033"
    assert "enrichment quota" in result.skipped[0]["reason"]
    # Skipped / un-enriched videos still record a flat observation (not dropped).
    latest = service._repos.videos.get_latest_video_observation(
        "v3example0000000000000000033"
    )
    assert latest is not None
    assert latest.like_count is None


# ----------------------------------------------------------------------
# Live / upcoming video handling
# ----------------------------------------------------------------------
def _channel_with_live_entry() -> dict[str, Any]:
    channel_raw = _load("channel_raw.json")
    channel_raw = {
        **channel_raw,
        "entries": [
            *channel_raw["entries"],
            {
                "id": _LIVE_ID,
                "channel_id": "UCexample00000000000000000",
                "title": "Upcoming Live Stream",
                "live_status": "is_upcoming",
                "view_count": 120,
            },
        ],
    }
    return channel_raw


_LIVE_ID = "livexample0000000000000000001"


def test_collect_channel_live_video_skipped_not_error(tmp_path) -> None:
    channel_raw = _channel_with_live_entry()
    live_info = {
        "id": _LIVE_ID,
        "webpage_url": f"https://www.youtube.com/watch?v={_LIVE_ID}",
        "title": "Upcoming Live Stream",
        "channel_id": "UCexample00000000000000000",
        "live_status": "is_upcoming",
        "view_count": 120,
    }
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        videos={
            "v1example0000000000000000001": _load("video_raw.json"),
            "v2example0000000000000000002": {
                "id": "v2example0000000000000000002",
                "webpage_url": (
                    "https://www.youtube.com/watch?v=v2example0000000000000000002"
                ),
                "title": "Second Video",
                "channel_id": "UCexample00000000000000000",
                "view_count": 5000,
                "like_count": 321,
            },
            _LIVE_ID: live_info,
        },
    )
    service = _build_service(
        tmp_path,
        provider,
        collection=CollectionSettings(enrich_video_stats=True, collect_comments=False),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    # The upcoming stream is deep-enrichment-skipped, never an error.
    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []
    assert result.entities_failed == 0
    assert len(result.skipped) == 1
    assert result.skipped[0]["video_id"] == _LIVE_ID
    assert (
        result.skipped[0]["reason"]
        == "live/upcoming video - no comments available"
    )
    # The live video itself is still persisted with its flat metadata.
    video = service._repos.videos.get_video(_LIVE_ID)
    assert video is not None
    assert video.live_status == "is_upcoming"
    latest = service._repos.videos.get_latest_video_observation(_LIVE_ID)
    assert latest is not None
    assert latest.view_count == 120


def test_collect_channel_live_event_error_skipped_not_error(tmp_path) -> None:
    channel_raw = _channel_with_live_entry()
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        videos={
            "v1example0000000000000000001": _load("video_raw.json"),
            "v2example0000000000000000002": {
                "id": "v2example0000000000000000002",
                "webpage_url": (
                    "https://www.youtube.com/watch?v=v2example0000000000000000002"
                ),
                "title": "Second Video",
                "channel_id": "UCexample00000000000000000",
                "view_count": 5000,
                "like_count": 321,
            },
        },
        live_videos={_LIVE_ID},
    )
    service = _build_service(
        tmp_path,
        provider,
        collection=CollectionSettings(enrich_video_stats=True, collect_comments=False),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    # A LiveEventSkipError surfaces as a skip, never as an error.
    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []
    assert result.entities_failed == 0
    assert len(result.skipped) == 1
    assert result.skipped[0]["video_id"] == _LIVE_ID
    assert (
        result.skipped[0]["reason"]
        == "live/upcoming video - no comments available"
    )
    # The video row persisted with whatever flat metadata existed.
    assert service._repos.videos.get_video(_LIVE_ID) is not None


# ----------------------------------------------------------------------
# Enrichment concurrency
# ----------------------------------------------------------------------
class _ConcurrencyProvider(FakeAcquisitionProvider):
    """Fake provider that tracks how many deep extractions overlap."""

    def __init__(self, channel_raw, videos, *, delay: float = 0.05):
        super().__init__(channel_raw=channel_raw, videos=videos)
        self.delay = delay
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def extract_video(self, video_url: str) -> dict[str, Any]:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            return super().extract_video(video_url)
        finally:
            with self._lock:
                self.active -= 1


def test_enrichment_concurrency_parallelizes_and_counts(tmp_path) -> None:
    channel_raw = {
        **_load("channel_raw.json"),
        "entries": [
            {
                "id": f"v4example00000000000000000{i}",
                "channel_id": "UCexample00000000000000000",
                "title": f"Video {i}",
                "view_count": 1000 + i,
            }
            for i in range(1, 4)
        ],
    }
    videos = {
        f"v4example00000000000000000{i}": {
            "id": f"v4example00000000000000000{i}",
            "webpage_url": (
                f"https://www.youtube.com/watch?v=v4example00000000000000000{i}"
            ),
            "title": f"Video {i}",
            "channel_id": "UCexample00000000000000000",
            "view_count": 1000 + i,
            "like_count": 10 * i,
            "comment_count": 1,
            "comments": [
                {"id": f"c{i}", "text": f"comment {i}", "like_count": 1}
            ],
        }
        for i in range(1, 4)
    }
    provider = _ConcurrencyProvider(channel_raw=channel_raw, videos=videos)
    service = _build_service(
        tmp_path,
        provider,
        scraper=ScraperSettings(
            retries=1,
            retry_backoff=0.0,
            request_delay_seconds=0,
            enrichment_concurrency=3,
        ),
        collection=CollectionSettings(enrich_video_stats=True, collect_comments=True),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []
    assert result.entities_created == 3
    assert result.comments_collected == 3
    assert len(provider.video_calls) == 3
    assert provider.max_active >= 2  # at least two deep extractions overlapped


# ----------------------------------------------------------------------
# Channel workflow
# ----------------------------------------------------------------------
def test_collect_channel_partial_failure_records_error(tmp_path) -> None:
    channel_raw = _load("channel_raw.json")
    provider = FakeAcquisitionProvider(
        channel_raw=channel_raw,
        fail_videos={"v1example0000000000000000001"},
    )
    service = _build_service(
        tmp_path,
        provider,
        collection=CollectionSettings(
            enrich_video_stats=True, collect_comments=False, max_videos_to_enrich=1
        ),
    )

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.PARTIAL
    assert result.entities_failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == ErrorType.UNAVAILABLE
    assert result.errors[0].entity_id == "v1example0000000000000000001"
    assert result.errors[0].entity_type == EntityType.VIDEO

    # Error persisted on the run, and the failing video is still not dropped
    # from the run record: it is reported, not silently swallowed.
    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.entities_failed == 1
    assert run.notes == [
        "1 error(s) recorded",
        "1 video(s) skipped deep enrichment",
    ]
    assert len(service._repos.runs.list_errors(result.run_id)) == 1


def test_collect_channel_total_failure(tmp_path) -> None:
    provider = FakeAcquisitionProvider(channel_raw=None)  # no channel
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_channel("https://www.youtube.com/@example")

    assert result.status == CollectionStatus.FAILED
    assert result.ok is False
    assert result.errors[0].error_type == ErrorType.INVALID_URL
    assert result.target_id is None


# ----------------------------------------------------------------------
# Video workflow
# ----------------------------------------------------------------------
def test_collect_video_with_comments(tmp_path) -> None:
    video_raw = _load("video_raw.json")
    video_raw = {**video_raw, "comments": _load("comments_raw.json")}
    provider = FakeAcquisitionProvider(videos={"v1example0000000000000000001": video_raw})
    service = _build_service(tmp_path, provider)

    result = service.collect_video("https://www.youtube.com/watch?v=v1example0000000000000000001")

    assert result.status == CollectionStatus.SUCCESS
    assert result.target_id == "v1example0000000000000000001"
    assert result.comments_collected > 0
    assert result.entities_created == 1

    video = service._repos.videos.get_video("v1example0000000000000000001")
    assert video is not None
    assert video.channel_id == "UCexample00000000000000000"

    comments = service._repos.comments.list_comments("v1example0000000000000000001")
    assert len(comments) == result.comments_collected

    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.target_video_id == "v1example0000000000000000001"


def test_collect_video_with_comments_disabled(tmp_path) -> None:
    video_raw = _load("video_raw.json")
    video_raw = {**video_raw, "comments": _load("comments_raw.json")}
    provider = FakeAcquisitionProvider(videos={"v1example0000000000000000001": video_raw})
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_video("https://www.youtube.com/watch?v=v1example0000000000000000001")

    assert result.status == CollectionStatus.SUCCESS
    assert result.comments_collected == 0
    assert len(service._repos.comments.list_comments("v1example0000000000000000001")) == 0


def test_collect_video_failure_records_error(tmp_path) -> None:
    provider = FakeAcquisitionProvider(fail_videos={"badvideo"})
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_video("https://www.youtube.com/watch?v=badvideo")

    assert result.status == CollectionStatus.FAILED
    assert result.ok is False
    assert result.errors[0].error_type == ErrorType.UNAVAILABLE
    assert len(service._repos.runs.list_errors(result.run_id)) == 1


# ----------------------------------------------------------------------
# Recommendation workflow
# ----------------------------------------------------------------------
def test_recommendations_unsupported_is_explicit_not_zero(tmp_path) -> None:
    video_raw = _load("video_raw.json")
    provider = FakeAcquisitionProvider(
        videos={"v1example0000000000000000001": video_raw},
        rec_unsupported=True,
    )
    service = RecommendationService(
        provider,
        build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="svc")),
    )

    result = service.collect_recommendations(
        "https://www.youtube.com/watch?v=v1example0000000000000000001"
    )

    # The limitation is surfaced explicitly, never silently treated as zero.
    assert result.status == CollectionStatus.PARTIAL
    assert len(result.errors) == 1
    assert result.errors[0].error_type == ErrorType.RECOMMENDATION_UNSUPPORTED
    assert result.errors[0].entity_type == EntityType.RECOMMENDATION
    # The source video itself was still collected.
    assert service._repos.videos.get_video("v1example0000000000000000001") is not None
    assert len(service._repos.recommendations.list_recommendation_edges()) == 0


def test_recommendations_observed_edges_saved(tmp_path) -> None:
    video_raw = _load("video_raw.json")
    provider = FakeAcquisitionProvider(
        videos={"v1example0000000000000000001": video_raw},
        recommendations=[{"id": "rec_one"}, {"id": "rec_two"}],
    )
    service = RecommendationService(
        provider,
        build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="svc")),
    )

    result = service.collect_recommendations(
        "https://www.youtube.com/watch?v=v1example0000000000000000001"
    )

    assert result.status == CollectionStatus.SUCCESS
    edges = service._repos.recommendations.list_recommendation_edges(
        source_video_id="v1example0000000000000000001"
    )
    assert {e.recommended_video_id for e in edges} == {"rec_one", "rec_two"}
    positions = {e.position for e in edges}
    assert positions == {0, 1}  # ordering preserved for ranking research
