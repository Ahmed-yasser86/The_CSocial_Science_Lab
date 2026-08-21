"""Normalization: raw yt-dlp dictionaries -> domain models.

This is where *source observations* become typed domain objects. All
extraction is defensive: missing fields become ``None`` / empty collections,
never guesses. Raw payloads are preserved on the ``raw_json`` field for
provenance and later re-processing.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from SocialScienceResearch.domain.enums import RecommendationStatus
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.utils.idgen import new_id, utcnow


# ----------------------------------------------------------------------
# Defensive value helpers
# ----------------------------------------------------------------------
def _first(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return default


def _to_int(raw: dict[str, Any], *keys: str) -> int | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(raw: dict[str, Any], *keys: str) -> float | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(raw: dict[str, Any], *keys: str) -> bool | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _to_date(raw: dict[str, Any], *keys: str) -> date | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    # yt-dlp uses YYYYMMDD
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _to_datetime(raw: dict[str, Any], *keys: str) -> datetime | None:
    value = _first(raw, *keys)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _to_str_list(raw: dict[str, Any], *keys: str) -> list[str]:
    value = _first(raw, *keys, default=[])
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value]
    return []


def _url_for_video(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# ----------------------------------------------------------------------
# Channels
# ----------------------------------------------------------------------
def normalize_channel(raw: dict[str, Any], run_id: str) -> Channel | None:
    """Build a :class:`Channel` from a raw yt-dlp payload.

    Returns ``None`` when no stable channel id can be resolved (the payload is
    not a channel).
    """
    channel_id = _first(raw, "channel_id", "id")
    if not channel_id:
        return None
    url = _first(raw, "channel_url") or f"https://www.youtube.com/channel/{channel_id}"
    handle = _first(raw, "uploader_id")
    if isinstance(handle, str) and not handle.startswith("@"):
        handle = None
    thumbnails = raw.get("thumbnails") or []
    avatar_url = _first(raw, "avatar") or (
        thumbnails[-1].get("url") if thumbnails else None
    )
    return Channel(
        channel_id=str(channel_id),
        url=str(url),
        title=_first(raw, "channel", "uploader", "title"),
        description=raw.get("description"),
        handle=handle,
        is_verified=_to_bool(raw, "is_verified"),
        avatar_url=avatar_url,
        banner_url=raw.get("banner"),
        country=raw.get("country"),
        joined_date=_to_date(raw, "joined_date"),
        first_observed_run_id=run_id,
        raw_json=dict(raw),
    )


def normalize_channel_observation(
    raw: dict[str, Any],
    run_id: str,
    channel_id: str | None = None,
    observed_at: datetime | None = None,
) -> ChannelObservation | None:
    """Build a :class:`ChannelObservation` from a raw payload (stats snapshot)."""
    resolved_id = channel_id or _first(raw, "channel_id", "id")
    if not resolved_id:
        return None
    return ChannelObservation(
        observation_id=new_id("obs_ch"),
        collection_run_id=run_id,
        channel_id=str(resolved_id),
        observed_at=observed_at or utcnow(),
        subscriber_count=_to_int(raw, "channel_follower_count"),
        video_count=_to_int(raw, "channel_video_count", "playlist_count"),
        view_count=_to_int(raw, "channel_view_count"),
        raw_json=dict(raw),
    )


# ----------------------------------------------------------------------
# Videos
# ----------------------------------------------------------------------
def normalize_video(raw: dict[str, Any], run_id: str) -> Video | None:
    """Build a :class:`Video` from a raw yt-dlp payload.

    Returns ``None`` when no stable video id can be resolved.
    """
    video_id = _first(raw, "id", "video_id")
    if not video_id:
        return None
    chapters = raw.get("chapters") or []
    return Video(
        video_id=str(video_id),
        url=_first(raw, "webpage_url") or _url_for_video(str(video_id)),
        channel_id=_first(raw, "channel_id"),
        title=raw.get("title"),
        description=raw.get("description"),
        duration=_to_int(raw, "duration"),
        upload_date=_to_date(raw, "upload_date"),
        upload_timestamp=_to_datetime(raw, "timestamp"),
        tags=_to_str_list(raw, "tags"),
        categories=_to_str_list(raw, "categories"),
        language=raw.get("language"),
        live_status=raw.get("live_status"),
        availability=raw.get("availability"),
        age_limit=_to_int(raw, "age_limit"),
        is_short=_to_bool(raw, "is_short"),
        thumbnail_url=raw.get("thumbnail"),
        chapters_json=[dict(c) for c in chapters if isinstance(c, dict)],
        first_observed_run_id=run_id,
        raw_json=dict(raw),
    )


def normalize_video_observation(
    raw: dict[str, Any],
    run_id: str,
    video_id: str | None = None,
    observed_at: datetime | None = None,
) -> VideoObservation | None:
    """Build a :class:`VideoObservation` (the run-scoped stats snapshot)."""
    resolved_id = video_id or _first(raw, "id", "video_id")
    if not resolved_id:
        return None
    return VideoObservation(
        observation_id=new_id("obs_vid"),
        collection_run_id=run_id,
        video_id=str(resolved_id),
        observed_at=observed_at or utcnow(),
        view_count=_to_int(raw, "view_count"),
        like_count=_to_int(raw, "like_count"),
        comment_count=_to_int(raw, "comment_count"),
        favorite_count=_to_int(raw, "favorite_count"),
        raw_json=dict(raw),
    )


# ----------------------------------------------------------------------
# Comments
# ----------------------------------------------------------------------
def _comment_published_at(raw: dict[str, Any]) -> datetime | None:
    value = _first(raw, "timestamp")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _compute_thread_roots(comments: list[Comment]) -> None:
    """Fill ``root_comment_id`` for replies by walking parent chains.

    Guards against cycles and unknown parents (root stays ``None`` when the
    chain cannot be resolved), so thread-depth analysis is always safe.
    """
    by_id = {c.comment_id: c for c in comments if c.comment_id}
    for comment in comments:
        if not comment.is_reply or not comment.parent_comment_id:
            comment.root_comment_id = comment.root_comment_id or (
                comment.comment_id if not comment.is_reply else None
            )
            continue
        if comment.root_comment_id:
            continue
        seen: set[str] = set()
        parent_id = comment.parent_comment_id
        root_id: str | None = None
        for _ in range(100):  # hard cap against pathological chains
            if parent_id in seen or parent_id not in by_id:
                break
            seen.add(parent_id)
            parent = by_id[parent_id]
            if not parent.is_reply:
                root_id = parent.comment_id
                break
            parent_id = parent.parent_comment_id or None
        comment.root_comment_id = root_id


def normalize_comments(
    raw_comments: list[dict[str, Any]],
    video_id: str,
    run_id: str,
    observed_at: datetime | None = None,
) -> tuple[list[Comment], list[CommentObservation]]:
    """Normalize raw yt-dlp comment entries into comments + observations.

    Returns ``(comments, observations)``. The observation time is the
    *collection* time (``observed_at``), never the comment's publish time.
    """
    observed_at = observed_at or utcnow()
    comments: list[Comment] = []
    observations: list[CommentObservation] = []
    for raw in raw_comments:
        comment_id = _first(raw, "id")
        if not comment_id:
            continue
        parent_id = _first(raw, "parent")
        parent = str(parent_id) if parent_id else None
        is_reply = bool(parent)
        comment = Comment(
            comment_id=str(comment_id),
            video_id=video_id,
            author_name=raw.get("author"),
            author_id=_first(raw, "author_id", "author_channel_id"),
            comment_text=raw.get("text"),
            published_at=_comment_published_at(raw),
            is_reply=is_reply,
            parent_comment_id=parent,
            is_author=_to_bool(raw, "author_is_uploader"),
            first_observed_run_id=run_id,
            raw_json=dict(raw),
        )
        comments.append(comment)
        observations.append(
            CommentObservation(
                observation_id=new_id("obs_cm"),
                collection_run_id=run_id,
                comment_id=comment.comment_id,
                observed_at=observed_at,
                like_count=_to_int(raw, "like_count"),
                reply_count=_to_int(raw, "reply_count"),
                is_removed=raw.get("is_removed"),
                raw_json=dict(raw),
            )
        )
    _compute_thread_roots(comments)
    return comments, observations


# ----------------------------------------------------------------------
# Recommendations
# ----------------------------------------------------------------------
def _channel_name(raw: dict[str, Any]) -> str | None:
    """Best-effort channel *name* from a recommendation entry.

    yt-dlp/INNERTUBE entries carry the channel under varying keys and shapes
    (``channel``/``uploader`` as a string name, or as a dict with ``name``/
    ``title``/``id``). Name-only is intentionally accepted here: the stable
    id (``channel_id``) is extracted separately and a missing id must never
    erase an observed channel name.
    """
    for key in ("channel", "uploader", "channel_name", "uploader_name",
                "channel_title", "channel_uploader"):
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            for name_key in ("name", "title", "channel", "uploader"):
                name = value.get(name_key)
                if name and isinstance(name, str):
                    return name
        elif isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_recommendations(
    source_video_id: str,
    raw_entries: list[dict[str, Any]],
    run_id: str,
    observed_at: datetime | None = None,
) -> list[RecommendationObservation]:
    """Build observed recommendation edges (source video -> recommended video).

    ``position`` preserves any ordering the source provides, which matters for
    future recommendation-ranking research.
    """
    observed_at = observed_at or utcnow()
    edges: list[RecommendationObservation] = []
    for position, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            continue
        rec_id = _first(raw, "id", "video_id")
        if not rec_id:
            continue
        edges.append(
            RecommendationObservation(
                observation_id=new_id("obs_rec"),
                collection_run_id=run_id,
                source_video_id=source_video_id,
                recommended_video_id=str(rec_id),
                position=position,
                status=RecommendationStatus.OBSERVED,
                channel_id=_first(raw, "channel_id"),
                channel_name=_channel_name(raw),
                title=raw.get("title"),
                observed_at=observed_at,
                raw_json=dict(raw),
            )
        )
    return edges
