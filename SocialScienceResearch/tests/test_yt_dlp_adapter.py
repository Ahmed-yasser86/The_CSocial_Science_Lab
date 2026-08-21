"""Tests for the yt-dlp adapter using a fake YoutubeDL (no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from SocialScienceResearch.acquisition.errors import (
    InvalidURLError,
    LiveEventSkipError,
    NetworkError,
    RateLimitError,
    RecommendationUnsupportedError,
    VideoUnavailableError,
    classify_exception,
)
from SocialScienceResearch.acquisition.yt_dlp_adapter import YtDlpAcquisitionProvider
from SocialScienceResearch.config.settings import CollectionSettings, ScraperSettings

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


class _FakeYoutubeDL:
    """Minimal stand-in for yt_dlp.YoutubeDL."""

    instances: list["_FakeYoutubeDL"] = []

    def __init__(self, opts: dict) -> None:
        self.opts = opts
        self.behavior = _FakeYoutubeDL._behavior
        self.calls: list[str] = []
        _FakeYoutubeDL.instances.append(self)

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def extract_info(self, url: str, download: bool = False) -> dict:
        self.calls.append(url)
        result = self.behavior.get(url)
        if callable(result):
            result = result(url)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise InvalidURLError(f"No behavior configured for {url}")
        return result

    def sanitize_info(self, info: dict) -> dict:
        return info


@pytest.fixture
def patch_ytdlp(monkeypatch) -> None:
    monkeypatch.setattr(
        "SocialScienceResearch.acquisition.yt_dlp_adapter.YoutubeDL", _FakeYoutubeDL
    )
    # Keep recommendation tests hermetic: never reach the live INNERTUBE
    # endpoint from the yt-search-python fallback layer.
    monkeypatch.setattr(
        "SocialScienceResearch.acquisition.yt_dlp_adapter._YT_Recommendations", None
    )


def _provider() -> YtDlpAcquisitionProvider:
    return YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=3, retry_backoff=0.01),
        collection=CollectionSettings(collect_comments=True, max_comments_per_video=500),
    )


def test_extract_channel_returns_channel_and_videos(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {"https://youtube.com/@example": raw}
    provider = _provider()
    result = provider.extract_channel("https://youtube.com/@example")
    assert result.channel["channel_id"] == "UCexample00000000000000000"
    assert len(result.videos) == 2
    assert result.videos[0]["id"] == "v1example0000000000000000001"
    fake = _FakeYoutubeDL.instances[-1]
    assert fake.opts["extractor_args"]["youtubetab"]["tab"] == ["videos", "shorts"]


def test_extract_channel_rejects_non_playlist(patch_ytdlp) -> None:
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=xyz": {"id": "xyz"}}
    provider = _provider()
    with pytest.raises(InvalidURLError):
        provider.extract_channel("https://youtube.com/watch?v=xyz")


# ----------------------------------------------------------------------
# max_videos_per_channel -> playlistend
# ----------------------------------------------------------------------
_PLAYLIST_URL = "https://www.youtube.com/playlist?list=UUexample00000000000000000"
_STREAMS_URL = "https://www.youtube.com/channel/UCexample00000000000000000/streams"


def test_extract_channel_applies_playlistend_when_quota_set(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(max_videos_per_channel=7),
    )
    result = provider.extract_channel("https://youtube.com/@example")
    assert len(result.videos) == 2
    fake = _FakeYoutubeDL.instances[-1]
    assert fake.opts["playlistend"] == 7
    assert fake.opts["extract_flat"] == "in_playlist"


def test_extract_channel_omits_playlistend_when_quota_unset(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(max_videos_per_channel=None),
    )
    provider.extract_channel("https://youtube.com/@example")
    fake = _FakeYoutubeDL.instances[-1]
    assert "playlistend" not in fake.opts
    assert fake.opts["extract_flat"] == "in_playlist"


def test_extract_channel_applies_playlistend_even_when_not_flat(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(max_videos_per_channel=3, extract_flat=False),
    )
    provider.extract_channel("https://youtube.com/@example")
    fake = _FakeYoutubeDL.instances[-1]
    assert "extract_flat" not in fake.opts
    assert fake.opts["playlistend"] == 3


# ----------------------------------------------------------------------
# Live videos
# ----------------------------------------------------------------------
def test_extract_channel_includes_and_dedupes_live_videos(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    live_raw = {
        "_type": "playlist",
        "id": "UCexample00000000000000000",
        "entries": [
            {"id": "v3example0000000000000003", "title": "Live Stream 1"},
            {"id": "v1example0000000000000000001", "title": "Already in uploads"},
        ],
    }
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
        _STREAMS_URL: live_raw,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(include_live_videos=True),
    )
    result = provider.extract_channel("https://youtube.com/@example")
    ids = [v["id"] for v in result.videos]
    assert "v3example0000000000000003" in ids  # live appended
    assert len(ids) == len(set(ids))  # deduped against uploads
    assert len(result.videos) == 3  # 2 uploads + 1 new live
    assert any(c == _STREAMS_URL for c in _FakeYoutubeDL.instances[-1].calls)


def test_extract_channel_scrape_live_only_returns_only_streams(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    live_raw = {
        "_type": "playlist",
        "id": "UCexample00000000000000000",
        "entries": [
            {"id": "v3example0000000000000003", "title": "Live Stream 1"},
        ],
    }
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _STREAMS_URL: live_raw,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(scrape_live_only=True),
    )
    result = provider.extract_channel("https://youtube.com/@example")
    assert [v["id"] for v in result.videos] == ["v3example0000000000000003"]
    # uploads playlist must NOT be fetched in live-only mode
    assert all(_PLAYLIST_URL not in c for c in _FakeYoutubeDL.instances[-1].calls)


def test_extract_channel_live_failure_logs_warning_not_silent(
    patch_ytdlp, caplog
) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
        # _STREAMS_URL intentionally missing -> extraction raises
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(include_live_videos=True),
    )
    with caplog.at_level("WARNING"):
        result = provider.extract_channel("https://youtube.com/@example")
    assert len(result.videos) == 2  # uploads still returned
    assert any("live/streams extraction failed" in r.message for r in caplog.records)


def test_extract_channel_returns_upcoming_live_flat_entries(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    streams = {
        "_type": "playlist",
        "id": "UCexample00000000000000000",
        "entries": [
            {
                "id": "upexample00000000000000000001",
                "title": "Upcoming Stream",
                "live_status": "is_upcoming",
            },
            {
                "id": "livex00000000000000000000001",
                "title": "Live Now",
                "live_status": "is_live",
            },
        ],
    }
    _FakeYoutubeDL._behavior = {
        "https://youtube.com/@example": raw,
        _PLAYLIST_URL: raw,
        _STREAMS_URL: streams,
    }
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=0, retry_backoff=0.01),
        collection=CollectionSettings(include_live_videos=True),
    )
    result = provider.extract_channel("https://youtube.com/@example")
    by_id = {v["id"]: v for v in result.videos}
    assert by_id["upexample00000000000000000001"]["live_status"] == "is_upcoming"
    assert by_id["livex00000000000000000000001"]["live_status"] == "is_live"


def test_extract_video_upcoming_live_returns_clean_result(patch_ytdlp) -> None:
    upcoming = _load("video_raw.json")
    upcoming["live_status"] = "is_upcoming"
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": upcoming}
    provider = _provider()

    info = provider.extract_video("https://youtube.com/watch?v=abc")

    assert info["live_status"] == "is_upcoming"
    assert info.get("comments_unavailable") is True


def test_extract_video_live_event_error_falls_back_without_comments(
    patch_ytdlp,
) -> None:
    from yt_dlp.utils import DownloadError

    calls = {"n": 0}
    upcoming = _load("video_raw.json")
    upcoming["live_status"] = "is_upcoming"

    def flaky(url: str):
        calls["n"] += 1
        if calls["n"] == 1:
            raise DownloadError(
                "ERROR: [youtube] NfKFGlc_UJg: This live event will begin in a few moments."
            )
        return upcoming

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": flaky}
    provider = _provider()

    info = provider.extract_video("https://youtube.com/watch?v=abc")

    # The live-event error is swallowed as a *skip* and a plain extraction is
    # retried so metadata (and the live_status) are still captured.
    assert calls["n"] == 2
    assert info["live_status"] == "is_upcoming"
    assert info.get("comments_unavailable") is True
    fake = _FakeYoutubeDL.instances[-1]
    assert "getcomments" not in fake.opts  # fallback ran without comments


def test_extract_video_live_event_error_classified_as_skip(patch_ytdlp) -> None:
    from yt_dlp.utils import DownloadError

    def always_live(url: str):
        raise DownloadError(
            "ERROR: This live event will begin in a few moments."
        )

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": always_live}
    provider = _provider()

    # When even the comment-less fallback cannot be fetched, the failure is a
    # LiveEventSkipError (an explicit skip), never a generic library error.
    with pytest.raises(LiveEventSkipError):
        provider.extract_video("https://youtube.com/watch?v=abc")


def test_live_event_download_error_classified_as_skip() -> None:
    from yt_dlp.utils import DownloadError

    exc = DownloadError("ERROR: This live event will begin in a few moments.")
    # The generic classifier alone would call this a library error; the
    # adapter's dedicated check is what turns it into an explicit skip.
    assert classify_exception(exc) == "library"
    classified = YtDlpAcquisitionProvider._classify_download_error(exc)
    assert isinstance(classified, LiveEventSkipError)


def test_extract_video_requests_comments(patch_ytdlp) -> None:
    raw = _load("video_raw.json")
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    info = provider.extract_video("https://youtube.com/watch?v=abc")
    assert info["id"] == "v1example0000000000000000001"
    fake = _FakeYoutubeDL.instances[-1]
    assert fake.opts["getcomments"] is True
    assert fake.opts["max_comments"] == (None, None, 500)


def test_extract_video_rejects_playlist(patch_ytdlp) -> None:
    raw = _load("channel_raw.json")
    _FakeYoutubeDL._behavior = {"https://youtube.com/@x": raw}
    provider = _provider()
    with pytest.raises(InvalidURLError):
        provider.extract_video("https://youtube.com/@x")


def test_extract_recommendations_unsupported_by_default(patch_ytdlp) -> None:
    raw = _load("video_raw.json")
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    with pytest.raises(RecommendationUnsupportedError):
        provider.extract_recommendations("https://youtube.com/watch?v=abc")


def test_extract_recommendations_uses_provided_data(patch_ytdlp) -> None:
    raw = _load("video_raw.json")
    raw["recommended_videos"] = [{"id": "r1"}, {"id": "r2"}]
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    recs = provider.extract_recommendations("https://youtube.com/watch?v=abc")
    assert [r["id"] for r in recs] == ["r1", "r2"]


class _FakeRecommendations:
    """Stand-in for yt-search-python's ``Recommendations`` static API."""

    components: list[dict] = []

    @classmethod
    def get(cls, video_id: str):
        return cls.components


def test_extract_recommendations_falls_back_to_yt_search_python(
    patch_ytdlp, monkeypatch
) -> None:
    raw = _load("video_raw.json")
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    _FakeRecommendations.components = [
        {"id": "up1", "title": "First", "channel": {"id": "UCx", "name": "C"}},
        {"id": "up2", "title": None},
        {"type": "radio", "playlistId": "RD1"},  # no id -> skipped
    ]
    monkeypatch.setattr(
        "SocialScienceResearch.acquisition.yt_dlp_adapter._YT_Recommendations",
        _FakeRecommendations,
    )
    provider = _provider()
    recs = provider.extract_recommendations("https://youtube.com/watch?v=abc")
    assert [r["id"] for r in recs] == ["up1", "up2"]
    assert recs[0]["title"] == "First"
    assert recs[0]["channel_id"] == "UCx"
    assert "channel_id" not in recs[1]


def test_extract_recommendations_falls_back_to_page_dump(
    patch_ytdlp, monkeypatch
) -> None:
    """The ``--write-pages`` dump is smart-parsed when the library supplies
    nothing and yt-search-python is unavailable."""
    from pathlib import Path as _Path

    up_next_payload = {
        "contents": {
            "twoColumnWatchNextResults": {
                "secondaryResults": {
                    "secondaryResults": {
                        "results": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {"lockupViewModel": {"contentId": "up1"}},
                                        {
                                            "lockupViewModel": {
                                                "contentId": "up2",
                                                "metadata": {
                                                    "lockupMetadataViewModel": {
                                                        "title": {
                                                            "content": "Second"
                                                        }
                                                    }
                                                },
                                            }
                                        },
                                        {"continuationItemRenderer": {"token": "x"}},
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    watch_html = (
        "<html><script>var ytInitialData = "
        + json.dumps(up_next_payload)
        + ";</script></html>"
    )

    def fake_extract(self, url: str, opts: dict) -> dict:
        if opts.get("write_pages"):
            (_Path.cwd() / "watch_1.dump").write_text(watch_html, encoding="utf-8")
        return {"id": "v1example0000000000000000001"}

    monkeypatch.setattr(
        "SocialScienceResearch.acquisition.yt_dlp_adapter.YtDlpAcquisitionProvider._extract",
        fake_extract,
    )
    provider = _provider()
    recs = provider.extract_recommendations("https://youtube.com/watch?v=abc")
    assert [r["id"] for r in recs] == ["up1", "up2"]
    assert recs[1]["title"] == "Second"


def test_extract_recommendations_survives_source_extraction_failure(
    patch_ytdlp, monkeypatch
) -> None:
    """When yt-dlp cannot extract the source video (e.g. availability/region
    gate raising ``ERROR: This video is not available``), the run must not
    abort - the INNERTUBE fallback still returns the observed recommendations."""
    from yt_dlp.utils import DownloadError

    _FakeRecommendations.components = [
        {"id": "up1", "title": "First", "channel": {"id": "UCx", "name": "C"}},
        {"id": "up2"},
    ]
    monkeypatch.setattr(
        "SocialScienceResearch.acquisition.yt_dlp_adapter._YT_Recommendations",
        _FakeRecommendations,
    )

    def unavailable(url: str):
        raise DownloadError("ERROR: [youtube] abc: This video is not available")

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": unavailable}
    provider = _provider()
    recs = provider.extract_recommendations("https://youtube.com/watch?v=abc")
    assert [r["id"] for r in recs] == ["up1", "up2"]
    assert recs[0]["channel_id"] == "UCx"


def test_extract_recommendations_raises_unsupported_when_all_providers_fail(
    patch_ytdlp,
) -> None:
    """If the source extraction fails *and* no fallback provider yields recs,
    the run still surfaces a clear unsupported error (never fabricates)."""
    from yt_dlp.utils import DownloadError

    def unavailable(url: str):
        raise DownloadError("ERROR: [youtube] abc: This video is not available")

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": unavailable}
    provider = _provider()
    with pytest.raises(RecommendationUnsupportedError):
        provider.extract_recommendations("https://youtube.com/watch?v=abc")


# ----------------------------------------------------------------------
# Retry behaviour
# ----------------------------------------------------------------------
def test_transient_network_error_is_retried_then_succeeds(patch_ytdlp) -> None:
    from yt_dlp.utils import DownloadError

    calls = {"n": 0}
    raw = _load("video_raw.json")

    def flaky(url: str):
        calls["n"] += 1
        if calls["n"] < 3:
            raise DownloadError("ERROR: timed out while fetching")
        return raw

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": flaky}
    provider = _provider()
    info = provider.extract_video("https://youtube.com/watch?v=abc")
    assert info["id"] == "v1example0000000000000000001"
    assert calls["n"] == 3


def test_permanent_error_not_retried(patch_ytdlp) -> None:
    from yt_dlp.utils import DownloadError

    calls = {"n": 0}

    def failing(url: str):
        calls["n"] += 1
        raise DownloadError("ERROR: Video unavailable, this video is unavailable")

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": failing}
    provider = _provider()
    with pytest.raises(VideoUnavailableError):
        provider.extract_video("https://youtube.com/watch?v=abc")
    assert calls["n"] == 1


def test_rate_limit_error_classified(patch_ytdlp) -> None:
    from yt_dlp.utils import DownloadError

    def failing(url: str):
        raise DownloadError("ERROR: HTTP Error 429: Too Many Requests")

    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": failing}
    provider = _provider()
    with pytest.raises(RateLimitError):
        provider.extract_video("https://youtube.com/watch?v=abc")


def test_network_error_retryable_flag() -> None:
    assert NetworkError("x").retryable is True
    assert RateLimitError("x").retryable is True
    assert VideoUnavailableError("x").retryable is False


def test_classify_exception_mapping() -> None:
    from yt_dlp.utils import DownloadError

    assert classify_exception(DownloadError("ERROR: HTTP Error 429")) == "rate_limit"
    assert classify_exception(DownloadError("ERROR: Video unavailable")) == "unavailable"
    assert classify_exception(DownloadError("ERROR: Unsupported URL")) == "invalid_url"
    assert classify_exception(DownloadError("ERROR: timed out")) == "network"
    assert classify_exception(DownloadError("ERROR: Some weird thing")) == "library"
    assert classify_exception(ValueError("boom")) == "library"


# ----------------------------------------------------------------------
# Transcript extraction
# ----------------------------------------------------------------------
_SAMPLE_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:03.000
Hello world.

00:00:03.500 --> 00:00:06.000
This is a <i>caption</i> test &amp; more.
"""


def test_extract_transcript_available(patch_ytdlp, monkeypatch) -> None:
    raw = _load("video_raw.json")
    raw["subtitles"] = {
        "en": [{"url": "https://example.com/captions.vtt", "ext": "vtt"}]
    }
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    monkeypatch.setattr(provider, "_fetch_caption", lambda url: _SAMPLE_VTT)

    extract = provider.extract_transcript("https://youtube.com/watch?v=abc", lang="en")

    from SocialScienceResearch.domain.enums import TranscriptStatus

    assert extract.status == TranscriptStatus.AVAILABLE
    assert extract.lang == "en"
    assert extract.content == "Hello world.\nThis is a caption test & more."


def test_extract_transcript_prefers_manual_over_auto(patch_ytdlp, monkeypatch) -> None:
    raw = _load("video_raw.json")
    raw["subtitles"] = {
        "en": [{"url": "https://example.com/manual.vtt", "ext": "vtt"}]
    }
    raw["automatic_captions"] = {
        "en": [{"url": "https://example.com/auto.vtt", "ext": "vtt"}]
    }
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    fetched = []
    monkeypatch.setattr(
        provider, "_fetch_caption", lambda url: fetched.append(url) or _SAMPLE_VTT
    )

    extract = provider.extract_transcript("https://youtube.com/watch?v=abc", lang="en")

    from SocialScienceResearch.domain.enums import TranscriptStatus

    assert extract.status == TranscriptStatus.AVAILABLE
    assert fetched == ["https://example.com/manual.vtt"]


def test_extract_transcript_missing_when_no_tracks(patch_ytdlp) -> None:
    raw = _load("video_raw.json")  # no subtitles / automatic_captions keys
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()

    extract = provider.extract_transcript("https://youtube.com/watch?v=abc", lang="en")

    from SocialScienceResearch.domain.enums import TranscriptStatus

    assert extract.status == TranscriptStatus.MISSING
    assert extract.content is None


def test_extract_transcript_missing_when_track_has_no_text(patch_ytdlp, monkeypatch) -> None:
    raw = _load("video_raw.json")
    raw["automatic_captions"] = {
        "en": [{"url": "https://example.com/empty.vtt", "ext": "vtt"}]
    }
    _FakeYoutubeDL._behavior = {"https://youtube.com/watch?v=abc": raw}
    provider = _provider()
    monkeypatch.setattr(provider, "_fetch_caption", lambda url: "WEBVTT\n\n\n")

    extract = provider.extract_transcript("https://youtube.com/watch?v=abc", lang="en")

    from SocialScienceResearch.domain.enums import TranscriptStatus

    assert extract.status == TranscriptStatus.MISSING


def test_parse_vtt_to_text_strips_timing_and_tags() -> None:
    from SocialScienceResearch.acquisition.yt_dlp_adapter import _parse_vtt_to_text

    assert _parse_vtt_to_text(_SAMPLE_VTT) == (
        "Hello world.\nThis is a caption test & more."
    )
    assert _parse_vtt_to_text("") == ""
    assert _parse_vtt_to_text("WEBVTT\n\n00:00:01,000 --> 00:00:02,000\nnothing") == (
        "nothing"
    )
