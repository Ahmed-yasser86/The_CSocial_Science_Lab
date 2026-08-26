"""Acquisition provider interface.

The acquisition layer is the *only* place that knows about the underlying
YouTube extraction library. Services and analytics depend only on this
interface, which returns raw, uninterpreted source dictionaries. A future
provider (e.g. YouTube Data API) can replace yt-dlp without touching the rest
of the module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from SocialScienceResearch.acquisition.errors import TranscriptUnsupportedError
from SocialScienceResearch.domain.enums import TranscriptStatus


@dataclass(frozen=True)
class ChannelExtract:
    """Raw result of a channel extraction.

    ``channel`` carries the top-level channel metadata; ``videos`` are raw
    video entries (flat metadata when the collector uses flat extraction).
    ``video_ids`` lists the *stable ids* of every video entry (the corpus the
    channel represents, before any per-run quota is applied downstream).
    ``page`` is a provider-specific continuation token for resumability.
    """

    channel: dict[str, Any]
    videos: list[dict[str, Any]] = field(default_factory=list)
    video_ids: list[str] = field(default_factory=list)
    page: Any | None = None


@dataclass(frozen=True)
class TranscriptExtract:
    """Best-effort transcript extraction outcome.

    ``content`` is the plain-text transcript when available; otherwise
    ``status`` is ``MISSING`` (no captions on the video) or ``UNSUPPORTED``
    (captions existed but could not be obtained). Absence is always explicit.
    """

    content: str | None = None
    lang: str | None = None
    status: TranscriptStatus = TranscriptStatus.MISSING
    message: str | None = None


class AcquisitionProvider(ABC):
    """Abstract YouTube acquisition source.

    All methods return *raw* source dictionaries exactly as provided by the
    underlying library; normalization happens downstream. Missing or
    unavailable data is represented as absent keys (never fabricated), and
    unsupported capabilities raise the typed errors from ``errors``.
    """

    @abstractmethod
    def extract_channel(self, channel_url: str) -> ChannelExtract:
        """Extract raw channel metadata and its video entries."""

    @abstractmethod
    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        """Extract raw full metadata for a single video (with comments when configured)."""

    @abstractmethod
    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        """Extract raw recommendation entries for a video.

        Raises ``RecommendationUnsupportedError`` when the underlying library
        cannot provide recommendations (the yt-dlp case) rather than
        fabricating or silently returning an empty list.
        """

    def extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        """Best-effort transcript/caption extraction.

        Never raises for a video without captions: returns ``MISSING``. Raises
        :class:`TranscriptUnsupportedError` only when the extraction method
        cannot provide captions at all for this video (consent wall, etc.).

        The default implementation treats transcripts as unsupported so
        providers that lack the capability record an explicit ``unsupported``
        status instead of a silent missing value.
        """
        raise TranscriptUnsupportedError(
            f"transcripts are not supported by this provider: {video_url}"
        )
