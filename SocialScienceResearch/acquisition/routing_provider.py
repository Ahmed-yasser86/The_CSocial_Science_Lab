"""Provider that routes transcript extraction to a selectable backend.

Everything except transcripts (channels, videos, recommendations) is always
handled by yt-dlp. Transcript extraction is routed to whichever backend the
researcher selected at runtime (``transcript_provider``): yt-dlp or
FreeTranscriptAPI. Both backends apply their own retry policy, so the router
only chooses.
"""

from __future__ import annotations

from typing import Any

from SocialScienceResearch.acquisition.base import AcquisitionProvider, TranscriptExtract
from SocialScienceResearch.acquisition.errors import TranscriptUnsupportedError


class RoutingAcquisitionProvider(AcquisitionProvider):
    """Delegates to yt-dlp, but routes ``extract_transcript`` by selector."""

    def __init__(
        self,
        ytdlp: AcquisitionProvider,
        freetranscriptapi: AcquisitionProvider | None,
        selector,
    ) -> None:
        self._ytdlp = ytdlp
        self._free = freetranscriptapi
        # selector() -> "ytdlp" | "freetranscriptapi"
        self._selector = selector

    def _transcript_provider_name(self) -> str:
        try:
            name = self._selector()
        except Exception:  # noqa: BLE001
            name = None
        return (name or "ytdlp").lower()

    def extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        if self._transcript_provider_name() == "freetranscriptapi" and self._free is not None:
            return self._free.extract_transcript(video_url, lang=lang)
        return self._ytdlp.extract_transcript(video_url, lang=lang)

    def extract_channel(self, channel_url: str) -> Any:
        return self._ytdlp.extract_channel(channel_url)

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        return self._ytdlp.extract_video(video_url, include_comments=include_comments)

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        return self._ytdlp.extract_recommendations(video_url)
