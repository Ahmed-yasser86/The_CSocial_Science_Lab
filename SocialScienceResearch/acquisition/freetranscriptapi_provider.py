"""FreeTranscriptAPI transcript provider.

Third-party REST API (https://api.freetranscriptapi.com/v1) that returns
YouTube transcripts without hitting YouTube's caption endpoint directly, so it
avoids the ``429 Too Many Requests`` throttling yt-dlp sees on caption
downloads. It is selectable at runtime alongside yt-dlp via
``transcript_provider``. Only ``extract_transcript`` is supported; other
acquisition methods delegate to yt-dlp through the routing provider.
"""

from __future__ import annotations

import urllib.request
import urllib.parse
import json
from typing import Any

from SocialScienceResearch.acquisition.base import AcquisitionProvider, TranscriptExtract
from SocialScienceResearch.acquisition.errors import (
    NetworkError,
    RateLimitError,
    RecommendationUnsupportedError,
    TranscriptUnsupportedError,
)
from SocialScienceResearch.acquisition.retry import retry_policy
from SocialScienceResearch.domain.enums import TranscriptStatus

_BASE_URL = "https://api.freetranscriptapi.com/v1"


class FreeTranscriptApiProvider(AcquisitionProvider):
    """Fetch transcripts via the FreeTranscriptAPI REST endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        lang: str = "en",
        timeout: float = 30.0,
        retries: int = 10,
        backoff: float = 5.0,
    ) -> None:
        self._api_key = api_key
        self._lang = lang
        self._timeout = timeout
        self._retry = retry_policy(retries=retries, backoff=backoff)

    def extract_channel(self, channel_url: str) -> Any:  # pragma: no cover - not used
        raise TranscriptUnsupportedError("FreeTranscriptAPI does not support channel extraction")

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        raise TranscriptUnsupportedError("FreeTranscriptAPI does not support video extraction")

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        raise RecommendationUnsupportedError("FreeTranscriptAPI does not support recommendations")

    def extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        return self._retry(self._extract_transcript)(video_url, lang)

    def _extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        lang = lang or self._lang
        url = (
            f"{_BASE_URL}/transcript?"
            + urllib.parse.urlencode({"video_url": video_url, "lang": lang})
        )
        req = urllib.request.Request(url)
        # The API sits behind Cloudflare, which rejects the default
        # "Python-urllib" UA with 403 (error code 1010). Send a browser-like UA.
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        if self._api_key:
            req.add_header("Authorization", f"Bearer {self._api_key}")
        status = None
        error_headers = None
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            error_headers = getattr(exc, "headers", None)
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
        except Exception as exc:  # noqa: BLE001 - network/transport failure
            raise NetworkError(f"FreeTranscriptAPI request failed: {exc}") from exc

        if status == 200:
            data = json.loads(body) if body else {}
            transcript = data.get("transcript")
            if isinstance(transcript, list):
                text = "\n".join(
                    str(seg.get("text", "")) for seg in transcript if isinstance(seg, dict)
                )
            else:
                text = transcript or ""
            if not text.strip():
                return TranscriptExtract(
                    status=TranscriptStatus.MISSING,
                    lang=lang,
                    message="transcript returned empty",
                )
            return TranscriptExtract(
                content=text,
                lang=data.get("language", lang),
                status=TranscriptStatus.AVAILABLE,
            )
        if status == 404:
            # video_not_found -> genuinely no captions for this video
            return TranscriptExtract(
                status=TranscriptStatus.MISSING,
                lang=lang,
                message="no transcript available for this video",
            )
        if status == 429:
            retry_after = None
            try:
                h = error_headers
                raw = h.get("Retry-After") if h else None
                if raw and str(raw).strip().isdigit():
                    retry_after = float(raw)
            except Exception:  # noqa: BLE001
                retry_after = None
            raise RateLimitError(
                "FreeTranscriptAPI rate limit exceeded",
                retry_after=retry_after,
            )
        if status in (401, 403):
            raise TranscriptUnsupportedError(
                f"FreeTranscriptAPI auth error: {status}"
            )
        if status >= 500:
            raise NetworkError(f"FreeTranscriptAPI server error: {status}")
        raise NetworkError(f"FreeTranscriptAPI unexpected status: {status}")
