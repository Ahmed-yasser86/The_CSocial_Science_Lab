"""Unit tests for the routing transcript provider (delegation by selector)."""

from __future__ import annotations

from unittest.mock import MagicMock

from SocialScienceResearch.acquisition.routing_provider import (
    RoutingAcquisitionProvider,
)
from SocialScienceResearch.domain.enums import TranscriptStatus


def _extract(transcript: str | None, status: TranscriptStatus):
    out = MagicMock()
    out.status = status
    out.content = transcript or ""
    return out


def test_extract_transcript_routes_to_selected_provider() -> None:
    yt = MagicMock()
    free = MagicMock()
    free.extract_transcript.return_value = _extract("hello", TranscriptStatus.AVAILABLE)

    # Selector starts on yt-dlp, then flips to freetranscriptapi.
    state = {"sel": "ytdlp"}
    router = RoutingAcquisitionProvider(
        ytdlp=yt, freetranscriptapi=free, selector=lambda: state["sel"]
    )

    router.extract_transcript("v1")
    assert yt.extract_transcript.called and not free.extract_transcript.called

    state["sel"] = "freetranscriptapi"
    router.extract_transcript("v2")
    assert free.extract_transcript.called


def test_non_transcript_methods_delegate_to_ytdlp() -> None:
    yt = MagicMock()
    free = MagicMock()

    router = RoutingAcquisitionProvider(
        ytdlp=yt, freetranscriptapi=free, selector=lambda: "freetranscriptapi"
    )
    router.extract_channel("c")
    router.extract_video("v")
    router.extract_recommendations("v")
    assert yt.extract_channel.called
    assert yt.extract_video.called
    assert yt.extract_recommendations.called
    assert not free.extract_channel.called
    assert not free.extract_video.called
    assert not free.extract_recommendations.called

