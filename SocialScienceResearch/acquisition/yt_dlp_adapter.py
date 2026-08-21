"""yt-dlp implementation of the acquisition provider.

The only module in the application that knows about yt-dlp. It:

* extracts channel metadata + video entries (flat by default for speed),
* extracts full video metadata, including comments when configured,
* exposes recommendations only when the library actually provides them,
  otherwise raises :class:`RecommendationUnsupportedError` (no fabrication).

Failures are classified through ``errors.classify_exception`` and transient
network/rate-limit failures are retried via the tenacity policy.
"""

from __future__ import annotations

import html
import os
import re
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from SocialScienceResearch.config.settings import CollectionSettings, ScraperSettings
from SocialScienceResearch.domain.enums import TranscriptStatus
from SocialScienceResearch.utils.logger import get_logger

from .base import AcquisitionProvider, ChannelExtract, TranscriptExtract
from .errors import (
    InvalidURLError,
    LiveEventSkipError,
    NetworkError,
    RecommendationUnsupportedError,
    TranscriptUnsupportedError,
    build_error,
    classify_exception,
)
from .retry import retry_policy
from .up_next import scan_page_dumps

logger = get_logger(__name__)

#: Optional recommendation provider (yt-search-python, MIT). It wraps the same
#: INNERTUBE ``/next`` endpoint the watch page uses and returns clean
#: recommendation entries, so no hand-written scraper is needed. When it is not
#: installed the adapter transparently falls back to the page-dump parser.
try:
    from youtubesearchpython import Recommendations as _YT_Recommendations
except Exception:  # pragma: no cover - optional dependency
    _YT_Recommendations = None

#: ``--write-pages`` dumps land in the process working directory, so page-dump
#: fallback extraction runs in a temp cwd. The lock serialises the cwd swap
#: against concurrent collection jobs in the same process.
_PAGE_DUMP_LOCK = threading.Lock()


@contextmanager
def _temporary_cwd(path: str) -> Iterator[None]:
    """Temporarily change the process working directory (lock-guarded)."""
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)

#: yt-dlp ``live_status`` values for which comments are not yet collectible.
#: ``is_live`` streams and ``is_upcoming`` premieres have no comment section
#: until they air; ``was_live``/``post_live`` are ended and may have comments.
_LIVE_NO_COMMENTS_STATUSES = ("is_upcoming", "is_live")

#: yt-dlp ``DownloadError`` messages that mean "this stream has not aired yet".
_LIVE_EVENT_ERROR_MARKERS = (
    "this live event will begin",
    "live event will begin",
    "will begin in a few moments",
    "premieres in",
    "premiere has not started",
    "stream has not started",
)


def _is_live_or_upcoming(info: dict[str, Any]) -> bool:
    """True when a payload describes a stream with no comment section yet."""
    return info.get("live_status") in _LIVE_NO_COMMENTS_STATUSES


def _is_live_event_error(message: str) -> bool:
    """True when a yt-dlp failure is really "the stream has not aired"."""
    lowered = message.lower()
    return any(marker in lowered for marker in _LIVE_EVENT_ERROR_MARKERS)


def _channel_uploads_playlist_id(channel_id: str) -> str | None:
    """Convert a YouTube channel ID (UC...) to its uploads playlist ID (UU...).

    YouTube channel IDs start with 'UC'. The uploads playlist ID is the same
    but with 'UC' replaced by 'UU'.
    """
    if channel_id.startswith("UC") and len(channel_id) == 24:
        return "UU" + channel_id[2:]
    return None


def _video_id_from_url(url: str) -> str | None:
    """Best-effort YouTube video id extraction from a watch URL.

    Used only to keep the recommendation fallback usable when the source
    video's full yt-dlp extraction fails (e.g. the extractor gates on
    availability/region), so the INNERTUBE-based fallback can still run.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        return None
    query = urllib.parse.parse_qs(parsed.query)
    v = query.get("v")
    if v and v[0]:
        return v[0]
    match = re.search(r"(?:/|v=)([A-Za-z0-9_-]{11})(?:[&?#]|$)", url)
    if match:
        return match.group(1)
    return None


def _extract_channel_id(url: str) -> str | None:
    """Extract channel ID from a YouTube channel URL.

    Handles both /channel/UC... and /@handle formats.
    For @handle URLs, we need to extract the channel ID from the page.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.netloc not in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
            return None
        path = parsed.path.rstrip("/")
        if path.startswith("/channel/"):
            channel_id = path.split("/channel/")[-1]
            if channel_id.startswith("UC") and len(channel_id) == 24:
                return channel_id
    except Exception:
        pass
    return None


class _YtDlpLogger:
    """Silent yt-dlp logger that forwards warnings/errors to our logger."""

    def debug(self, msg: str) -> None:  # noqa: D401
        logger.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        logger.debug("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        logger.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        logger.error("yt-dlp: %s", msg)


class YtDlpAcquisitionProvider(AcquisitionProvider):
    """yt-dlp-backed :class:`AcquisitionProvider`."""

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        collection: CollectionSettings | None = None,
    ) -> None:
        self._settings = settings or ScraperSettings()
        self._collection = collection or CollectionSettings()
        self._retry = retry_policy(
            retries=self._settings.retries,
            backoff=self._settings.retry_backoff,
        )

    # ------------------------------------------------------------------
    # Public interface (wrapped with the retry policy)
    # ------------------------------------------------------------------
    def extract_channel(self, channel_url: str) -> ChannelExtract:
        return self._retry(self._extract_channel)(channel_url)

    def extract_video(self, video_url: str) -> dict[str, Any]:
        return self._retry(self._extract_video)(video_url)

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        return self._retry(self._extract_recommendations)(video_url)

    def extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        return self._retry(self._extract_transcript)(video_url, lang)

    # ------------------------------------------------------------------
    # Internal implementations
    # ------------------------------------------------------------------
    def _extract_channel(self, channel_url: str) -> ChannelExtract:
        opts = self._base_opts()
        if self._collection.extract_flat:
            opts["extract_flat"] = "in_playlist"
        # playlistend is honoured by yt-dlp for both flat and deep extraction;
        # when the quota is unset/None we omit it so the full channel is read.
        if self._collection.max_videos_per_channel:
            opts["playlistend"] = self._collection.max_videos_per_channel

        # First, extract channel metadata from the channel URL
        channel_info = self._extract(channel_url, opts)
        if channel_info.get("_type") != "playlist":
            raise InvalidURLError(
                f"URL does not resolve to a channel/playlist: {channel_url}"
            )
        channel_raw = {k: v for k, v in channel_info.items() if k != "entries"}

        # Resolve the stable channel id: prefer the URL (UC...), then the
        # extracted metadata. This makes @handle URLs work, where the id is
        # resolved by yt-dlp rather than present in the path.
        channel_id = _extract_channel_id(channel_url) or channel_info.get("channel_id")

        want_live = (
            self._collection.include_live_videos
            or (
                self._collection.video_tabs
                and "streams" in self._collection.video_tabs
            )
            or self._collection.scrape_live_only
        )
        live_only = bool(self._collection.scrape_live_only)

        video_entries: list[dict[str, Any]] = []
        video_ids: set[str] = set()

        if not live_only:
            # Extract ALL uploads from the channel's uploads playlist (UU...),
            # falling back to the channel's own entries when unavailable.
            self._append_video_entries(
                video_entries,
                video_ids,
                self._extract_uploads(channel_url, channel_id, channel_info, opts),
            )

        if want_live:
            # Live/streams are fetched on top of uploads and deduped by id so
            # entries that also appear in the uploads playlist are not repeated.
            self._append_video_entries(
                video_entries,
                video_ids,
                self._extract_live_videos(channel_url, channel_id, opts),
            )

        if not video_entries and not live_only:
            # Final fallback to the channel's own entries (never in live-only
            # mode, where uploads would be fetched against the explicit intent).
            self._append_video_entries(
                video_entries,
                video_ids,
                self._channel_video_entries(channel_info, channel_id),
            )

        return ChannelExtract(
            channel=channel_raw,
            videos=video_entries,
            video_ids=list(video_ids),
        )

    @staticmethod
    def _append_video_entries(
        video_entries: list[dict[str, Any]],
        video_ids: set[str],
        entries: list[dict[str, Any]],
    ) -> None:
        """Append entries to the result, deduplicating by video id."""
        for e in entries:
            if not isinstance(e, dict):
                continue
            raw_id = e.get("id") or e.get("video_id")
            if raw_id:
                vid = str(raw_id)
                if vid not in video_ids:
                    video_ids.add(vid)
                    video_entries.append(e)

    def _extract_uploads(
        self,
        channel_url: str,
        channel_id: str | None,
        channel_info: dict[str, Any],
        opts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract the channel's uploads playlist (UU...), falling back to the
        channel's own entries when the playlist is unavailable."""
        if channel_id:
            playlist_id = _channel_uploads_playlist_id(channel_id)
            if playlist_id:
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                try:
                    playlist_info = self._extract(playlist_url, opts)
                    if playlist_info.get("_type") == "playlist":
                        return [
                            e
                            for e in (playlist_info.get("entries") or [])
                            if isinstance(e, dict)
                        ]
                    logger.warning(
                        "uploads playlist for %s did not resolve to a playlist",
                        channel_url,
                    )
                except Exception as exc:  # noqa: BLE001 - fall back, don't fail the channel
                    logger.warning(
                        "uploads playlist extraction failed for %s (%s): %s",
                        channel_url,
                        playlist_url,
                        exc,
                    )
        # Fall back to the channel's own entries (excluding channel-tab entries).
        return self._channel_video_entries(channel_info, channel_id)

    @staticmethod
    def _channel_video_entries(
        channel_info: dict[str, Any], channel_id: str | None
    ) -> list[dict[str, Any]]:
        """Return real video entries from a channel info dict.

        Channel-tab entries (the channel itself, ``_type == 'playlist'`` and id
        equal to the channel id) are excluded so they never masquerade as videos.
        """
        valid: list[dict[str, Any]] = []
        for e in channel_info.get("entries") or []:
            if not isinstance(e, dict):
                continue
            eid = e.get("id") or e.get("video_id")
            if not eid:
                continue
            if channel_id and str(eid) == str(channel_id):
                continue
            if e.get("_type") == "playlist":
                continue
            valid.append(e)
        return valid

    def _extract_live_videos(
        self, channel_url: str, channel_id: str | None, opts: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract live/streaming videos from a channel's streams tab.

        Points yt-dlp's youtubetab extractor at the channel ``/streams`` URL,
        which natively paginates the streams tab. The extractor-arg form
        (``youtubetab.tab=streams``) does not reliably select the tab, so we use
        the tab URL directly. Failures are logged, never silently swallowed.
        """
        if channel_id:
            streams_url = f"https://www.youtube.com/channel/{channel_id}/streams"
        else:
            streams_url = channel_url.rstrip("/") + "/streams"
        try:
            live_info = self._extract(streams_url, opts)
        except Exception as exc:  # noqa: BLE001 - warn, never fail the channel
            logger.warning(
                "live/streams extraction failed for %s (%s): %s",
                channel_url,
                streams_url,
                exc,
            )
            return []
        if live_info.get("_type") != "playlist":
            logger.warning(
                "live/streams tab for %s did not resolve to a playlist",
                channel_url,
            )
            return []
        return [
            e for e in (live_info.get("entries") or []) if isinstance(e, dict)
        ]

    def _extract_video(self, video_url: str) -> dict[str, Any]:
        opts = self._base_opts()
        want_comments = self._collection.collect_comments
        if want_comments:
            opts["getcomments"] = True
            opts["max_comments"] = (
                None,
                None,
                self._collection.max_comments_per_video,
            )
        try:
            info = self._extract(video_url, opts)
        except LiveEventSkipError:
            if not want_comments:
                raise
            # Upcoming/live streams cannot be comment-extracted until they
            # air; fall back to a plain extraction so their metadata is still
            # captured (research-quality: never drop the video row).
            logger.info(
                "video %s: live/upcoming stream, retrying without comments",
                video_url,
            )
            info = self._extract(video_url, self._base_opts())
        if info.get("_type") == "playlist":
            raise InvalidURLError(
                f"URL resolves to a playlist/channel, not a video: {video_url}"
            )
        if want_comments and _is_live_or_upcoming(info):
            info["comments_unavailable"] = True
        
        # Ensure metadata fields are always present
        info.setdefault("title", None)
        info.setdefault("channel_id", None)
        info.setdefault("thumbnail_url", None)
        info.setdefault("view_count", None)
        info.setdefault("like_count", None)
        info.setdefault("duration", None)
        return info

    def get_video_metadata(self, video_id: str) -> dict[str, Any]:
        """Fetch metadata for a single video using yt-dlp."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            info = self._extract(video_url, self._base_opts())
            return {
                "title": info.get("title"),
                "channel_id": info.get("channel_id"),
                "thumbnail_url": info.get("thumbnail"),
                "views": info.get("view_count"),
                "likes": info.get("like_count"),
                "duration": info.get("duration"),
            }
        except Exception as exc:
            logger.warning("Failed to fetch metadata for video %s: %s", video_id, exc)
            return {}

    def _extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        """Extract observed Up Next recommendations for a video.

        Layered so absence is only reported after every reliable source fails:

        1. the library's own ``recommended_videos``/``related`` fields when the
           provider actually populates them (never fabricated),
        2. yt-search-python's ``Recommendations`` (INNERTUBE ``/next``),
        3. a ``--write-pages`` dump of the raw watch page parsed with the
           defensive Up Next parser (survives renderer/nesting rotations).

        If none of the layers yields entries, ``RecommendationUnsupportedError``
        is raised exactly as before - observations are never invented.

        The source-video extraction is best-effort: when yt-dlp cannot fully
        extract the video (e.g. it gates on availability/region while the
        recommendations sidebar is still observable), we do *not* abort the
        run - we fall through to the INNERTUBE ``/next`` fallback using the
        video id parsed from the URL.
        """
        info: dict[str, Any] | None = None
        try:
            info = self._extract(video_url, self._base_opts())
        except InvalidURLError:
            raise
        except Exception as exc:  # noqa: BLE001 - degrade to fallback providers
            logger.info(
                "recommendations for %s: source extraction failed (%s); "
                "falling back to recommendation providers",
                video_url,
                exc,
            )
            info = None

        if info is not None:
            if info.get("_type") == "playlist":
                raise InvalidURLError(
                    f"URL resolves to a playlist/channel, not a video: {video_url}"
                )
            entries = info.get("recommended_videos") or info.get("related") or []
            if entries:
                return [e for e in entries if isinstance(e, dict)]
            video_id = info.get("id")
        else:
            video_id = _video_id_from_url(video_url)

        if video_id:
            recs = self._recommendations_via_yt_search_python(str(video_id))
            if recs:
                return recs
            recs = self._recommendations_via_page_dump(video_url)
            if recs:
                return recs

        raise RecommendationUnsupportedError(
            "no observed recommendation data available for "
            f"{video_url}; yt-dlp provides none and the recommendation "
            "fallback providers returned nothing."
        )

    def _recommendations_via_yt_search_python(
        self, video_id: str
    ) -> list[dict[str, Any]] | None:
        """Use yt-search-python's ``Recommendations`` (INNERTUBE ``/next``).

        Returns ``None`` when the optional dependency is missing or the request
        fails, letting the caller try the next layer.
        """
        if _YT_Recommendations is None:
            return None
        try:
            components = _YT_Recommendations.get(video_id)
        except Exception as exc:  # noqa: BLE001 - degrade to next layer
            logger.debug(
                "yt-search-python recommendations unavailable for %s: %s",
                video_id,
                exc,
            )
            return None
        if not isinstance(components, list):
            return None
        mapped: list[dict[str, Any]] = []
        for component in components:
            if not isinstance(component, dict):
                continue
            rec_id = component.get("id") or component.get("video_id")
            if not rec_id:
                continue
            entry: dict[str, Any] = {"id": str(rec_id)}
            if component.get("title"):
                entry["title"] = component["title"]
            channel = component.get("channel")
            if isinstance(channel, dict):
                if channel.get("id"):
                    entry["channel_id"] = str(channel["id"])
                for name_key in ("name", "title", "uploader"):
                    name = channel.get(name_key)
                    if isinstance(name, str) and name:
                        entry["channel_name"] = name
                        break
            elif isinstance(channel, str) and channel:
                entry["channel_name"] = channel
            elif component.get("uploader") and isinstance(component.get("uploader"), str):
                entry["channel_name"] = component["uploader"]
            mapped.append(entry)
        return mapped

    def _recommendations_via_page_dump(self, video_url: str) -> list[dict[str, Any]]:
        """Dump the raw watch page with ``--write-pages`` and smart-parse it.

        yt-dlp writes its page dumps to the process working directory, so the
        extraction runs inside a temporary cwd (guarded by ``_PAGE_DUMP_LOCK``
        against concurrent jobs) and the dumps are scanned for Up Next entries.
        """
        opts = self._base_opts()
        opts["write_pages"] = True
        with tempfile.TemporaryDirectory(prefix="ssr_upnext_") as tmp:
            with _PAGE_DUMP_LOCK:
                with _temporary_cwd(tmp):
                    try:
                        self._extract(video_url, opts)
                    except Exception as exc:  # noqa: BLE001 - fallback layer
                        logger.debug(
                            "up-next page dump for %s failed (%s); no recs",
                            video_url,
                            exc,
                        )
                        return []
            return scan_page_dumps(Path(tmp))

    def _extract_transcript(
        self, video_url: str, lang: str | None = None
    ) -> TranscriptExtract:
        """Best-effort caption transcript extraction for one video.

        Never fabricates content: videos without captions return ``MISSING``;
        captions that exist but cannot be retrieved raise
        :class:`TranscriptUnsupportedError` (classified, auditable).
        """
        lang = lang or self._settings.transcript_lang
        opts = self._base_opts()
        opts["subtitleslangs"] = [lang]
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        info = self._extract(video_url, opts)

        tracks: dict[str, list[dict[str, Any]]] = info.get("subtitles") or {}
        automatic: dict[str, list[dict[str, Any]]] = info.get("automatic_captions") or {}
        track_url, track_lang = self._pick_track(tracks, automatic, lang)
        if track_url is None:
            return TranscriptExtract(
                status=TranscriptStatus.MISSING,
                lang=lang,
                message="No caption track is available for this video.",
            )

        try:
            raw = self._fetch_caption(track_url)
        except urllib.error.HTTPError as exc:
            raise NetworkError(f"caption download failed: {exc}") from exc
        except urllib.error.URLError as exc:
            raise NetworkError(f"caption download failed: {exc}") from exc

        text = _parse_vtt_to_text(raw)
        if not text.strip():
            return TranscriptExtract(
                status=TranscriptStatus.MISSING,
                lang=track_lang,
                message="Caption track exists but contained no text.",
            )
        return TranscriptExtract(
            content=text, lang=track_lang, status=TranscriptStatus.AVAILABLE
        )

    @staticmethod
    def _pick_track(
        tracks: dict[str, list[dict[str, Any]]],
        automatic: dict[str, list[dict[str, Any]]],
        lang: str,
    ) -> tuple[str | None, str | None]:
        """Choose a caption track URL, preferring the requested language.

        Prefers manually-provided subtitles over auto-captions; falls back to
        the first available language when the requested one is absent.
        """
        for source in (tracks, automatic):
            if source.get(lang):
                track = source[lang][-1]
                return track.get("url"), lang
        for name, entries in tracks.items():
            if entries:
                return entries[-1].get("url"), name
        for name, entries in automatic.items():
            if entries:
                return entries[-1].get("url"), name
        return None, None

    def _fetch_caption(self, url: str) -> str:
        if self._settings.proxy:
            handler = urllib.request.ProxyHandler(
                {"http": self._settings.proxy, "https": self._settings.proxy}
            )
            opener = urllib.request.build_opener(handler)
        else:
            opener = urllib.request.build_opener()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": self._settings.transcript_lang or "en",
            },
        )
        with opener.open(req, timeout=self._settings.socket_timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Shared extraction
    # ------------------------------------------------------------------
    def _extract(self, url: str, opts: dict[str, Any]) -> dict[str, Any]:
        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except DownloadError as exc:
                raise self._classify_download_error(exc) from exc
            except Exception as exc:  # noqa: BLE001 - classify anything else
                raise build_error(classify_exception(exc), str(exc)) from exc
            if info is None:
                raise InvalidURLError(f"Could not resolve URL: {url}")
            return ydl.sanitize_info(info)

    @staticmethod
    def _classify_download_error(exc: DownloadError) -> AcquisitionError:
        """Turn a raw yt-dlp failure into a typed acquisition error.

        Live-event messages are a *skip* signal (the stream has not aired, so
        comments cannot be collected) - never a generic library failure.
        """
        if _is_live_event_error(str(exc)):
            return LiveEventSkipError(str(exc))
        return build_error(classify_exception(exc), str(exc))

    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": self._settings.socket_timeout,
            "logger": _YtDlpLogger(),
            "extractor_retries": 0,  # retries handled by our tenacity policy
            # Channel tabs to fetch via the youtubetab extractor (used as the
            # default feed when a channel/tab URL is extracted).
            "extractor_args": {
                "youtubetab": {
                    "tab": list(self._collection.video_tabs or ["videos", "shorts"])
                }
            },
        }
        if self._settings.proxy:
            opts["proxy"] = self._settings.proxy
        if self._settings.impersonate:
            opts["impersonate"] = self._settings.impersonate
        return opts


_CUE_LINE = re.compile(r"\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}")


def _parse_vtt_to_text(raw: str) -> str:
    """Convert a WebVTT/SRT caption payload into plain transcript text."""
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("webvtt"):
            continue
        if _CUE_LINE.match(stripped):
            continue
        if re.fullmatch(r"NOTE.*", stripped):
            continue
        if lower.startswith("kind:") or lower.startswith("language:"):
            continue
        cleaned = html.unescape(re.sub(r"<[^>]+>", "", stripped))
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)
