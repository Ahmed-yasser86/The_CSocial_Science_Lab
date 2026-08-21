"""Read-side query service: filtered corpus selection.

Implements :class:`VideoFilter` semantics over persisted videos. View-based
criteria apply to the *latest* observation of each video - never to fabricated
historical values - and criteria the data cannot answer (e.g. a video with no
duration for a duration filter) exclude the video without inventing a value.

B1 additions
------------
* :meth:`filter_comments` wires the previously-unwired :class:`CommentFilter`.
* :meth:`resolve_latest_rows` builds row dicts keyed by *variable name* (the
  VariableRegistry contract) with observed metrics resolved to their latest
  observation; the research-query evaluator and the future explorer share it.
* :meth:`filter_videos` now resolves latest observations with one batch scan
  (``get_latest_video_observations``) instead of one N+1 lookup per video.
"""

from __future__ import annotations

from typing import Any

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.models import Video
from SocialScienceResearch.domain.query import (
    CommentFilter,
    QueryContext,
    VideoFilter,
)
from SocialScienceResearch.persistence.base import Repositories


class QueryService:
    """Read-only queries over the corpus."""

    def __init__(
        self, repos: Repositories, settings: SocialScienceSettings | None = None
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._long_video_threshold = (
            self._settings.query.long_video_threshold_seconds
        )

    # ------------------------------------------------------------------
    def filter_videos(
        self, channel_id: str, filter: VideoFilter | None = None
    ) -> list[Video]:
        """Return videos of a channel matching the filter (all if ``None``)."""
        filter = filter or VideoFilter()
        videos = self._repos.videos.list_videos(channel_id=channel_id)
        latest = self._repos.videos.get_latest_video_observations(
            [video.video_id for video in videos]
        )
        return [v for v in videos if self._matches(v, filter, latest)]

    # ------------------------------------------------------------------
    def _matches(
        self,
        video: Video,
        filter: VideoFilter,
        latest_observations: dict | None = None,
    ) -> bool:
        if filter.date_from is not None:
            if video.upload_date is None or video.upload_date < filter.date_from:
                return False
        if filter.date_to is not None:
            if video.upload_date is None or video.upload_date > filter.date_to:
                return False

        if filter.duration_min is not None:
            if video.duration is None or video.duration < filter.duration_min:
                return False
        if filter.duration_max is not None:
            if video.duration is None or video.duration > filter.duration_max:
                return False

        if filter.video_type is not None and not self._matches_type(video, filter.video_type):
            return False

        if filter.upload_hour is not None:
            hour = self._upload_hour(video)
            if hour is None or hour != filter.upload_hour:
                return False
        if filter.upload_weekday is not None:
            weekday = self._upload_weekday(video)
            if weekday is None or weekday != filter.upload_weekday:
                return False

        if filter.tags and not (set(filter.tags) & set(video.tags)):
            return False
        if filter.category is not None and filter.category not in video.categories:
            return False
        if filter.keywords:
            haystack = f"{video.title or ''} {video.description or ''}".lower()
            if not all(keyword.lower() in haystack for keyword in filter.keywords):
                return False

        # View-range filters use the latest observation; videos without one
        # cannot be judged and are excluded (never assigned a fabricated count).
        if filter.views_min is not None or filter.views_max is not None:
            views = self._latest_views(video.video_id, latest_observations)
            if views is None:
                return False
            if filter.views_min is not None and views < filter.views_min:
                return False
            if filter.views_max is not None and views > filter.views_max:
                return False

        return True

    def _matches_type(self, video: Video, video_type: str) -> bool:
        if video_type == "short":
            return video.is_short is True
        if video_type == "long":
            if video.duration is None:
                return False
            return (
                video.duration >= self._long_video_threshold
                and video.is_short is not True
            )
        if video_type == "live":
            return video.live_status in ("is_live", "was_live", "post_live")
        return True

    @staticmethod
    def _upload_hour(video: Video) -> int | None:
        if video.upload_timestamp is not None:
            return video.upload_timestamp.hour
        return None

    @staticmethod
    def _upload_weekday(video: Video) -> int | None:
        if video.upload_timestamp is not None:
            return video.upload_timestamp.weekday()
        return None

    @staticmethod
    def _latest_views(video_id: str, latest_observations: dict | None = None) -> int | None:
        obs = (
            latest_observations.get(video_id)
            if latest_observations is not None
            else None
        )
        return obs.view_count if obs else None

    # ------------------------------------------------------------------
    # Comment filtering (B1: wires the previously-unwired CommentFilter)
    # ------------------------------------------------------------------
    def filter_comments(self, filter: CommentFilter, rows: list[dict]) -> list[dict]:
        """Apply a :class:`CommentFilter` to comment row dicts.

        Rows are keyed by variable name (see :meth:`resolve_latest_rows`);
        like/reply counts are the *latest* observed values. Comment text,
        date range, author, root-vs-reply and author-comment criteria apply to
        the static comment fields.
        """
        return [row for row in rows if self._comment_row_matches(filter, row)]

    def _comment_row_matches(self, filter: CommentFilter, row: dict) -> bool:
        if filter.date_from is not None:
            published = row.get("published_at")
            if published is None or published < filter.date_from:
                return False
        if filter.date_to is not None:
            published = row.get("published_at")
            if published is None or published > filter.date_to:
                return False

        if filter.author_id is not None and row.get("author_id") != filter.author_id:
            return False
        if filter.is_author is not None and row.get("is_author") is not filter.is_author:
            return False

        likes = row.get("like_count")
        if filter.min_likes is not None:
            if likes is None or likes < filter.min_likes:
                return False
        if filter.max_likes is not None:
            if likes is None or likes > filter.max_likes:
                return False

        replies = row.get("reply_count")
        if filter.min_replies is not None:
            if replies is None or replies < filter.min_replies:
                return False
        if filter.max_replies is not None:
            if replies is None or replies > filter.max_replies:
                return False

        if filter.only_roots and row.get("is_reply") is True:
            return False
        if filter.only_replies and row.get("is_reply") is not True:
            return False

        if filter.keywords:
            text = (row.get("comment_text") or "").lower()
            if not all(keyword.lower() in text for keyword in filter.keywords):
                return False
        return True

    # ------------------------------------------------------------------
    # Row resolution shared by the query evaluator and the explorer
    # ------------------------------------------------------------------
    def resolve_latest_rows(
        self,
        entity: str,
        filter: VideoFilter | CommentFilter | None = None,
        sort: str | None = None,
        context: QueryContext | None = None,
        run_ids: list[str] | None = None,
    ) -> list[dict]:
        """Resolve the corpus into row dicts keyed by variable name.

        Observed metrics (view/like/comment counts, subscriber counts, ...)
        are resolved to their *latest* observation via one batch scan per
        entity. ``filter`` (VideoFilter/CommentFilter) narrows video/comment
        rows; ``context`` scopes the population (channel/video); ``run_ids``
        scopes recommendation rows to edges observed in those runs.
        """
        entity = entity.lower()
        if entity == "video":
            rows = self._video_rows(context.channel_id if context else None)
            if isinstance(filter, VideoFilter):
                rows = [row for row in rows if self._match_video_row(row, filter)]
        elif entity == "comment":
            rows = self._comment_rows(context.video_id if context else None)
            if isinstance(filter, CommentFilter):
                rows = self.filter_comments(filter, rows)
        elif entity == "channel":
            rows = self._channel_rows()
        elif entity == "recommendation":
            rows = self._recommendation_rows(run_ids=run_ids)
        elif entity == "author":
            rows = self._author_rows()
        else:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of "
                "channel, video, comment, recommendation, author"
            )
        if sort is not None:
            rows = self._sorted_rows(rows, sort)
        return rows

    # ------------------------------------------------------------------
    def _video_rows(self, channel_id: str | None = None) -> list[dict[str, Any]]:
        videos = self._repos.videos.list_videos(channel_id=channel_id)
        latest = self._repos.videos.get_latest_video_observations(
            [video.video_id for video in videos]
        )
        rows: list[dict[str, Any]] = []
        for video in videos:
            obs = latest.get(video.video_id)
            # ``tags``/``categories`` are stored lists; the evaluator reads
            # them under the registered variable names.
            rows.append(
                {
                    "video_id": video.video_id,
                    "channel_id": video.channel_id,
                    "title": video.title,
                    "description": video.description,
                    "duration": video.duration,
                    "upload_date": video.upload_date,
                    "upload_timestamp": video.upload_timestamp,
                    "tags": video.tags,
                    "categories": video.categories,
                    "language": video.language,
                    "live_status": video.live_status,
                    "availability": video.availability,
                    "age_limit": video.age_limit,
                    "is_short": video.is_short,
                    "thumbnail_url": video.thumbnail_url,
                    "transcript_status": video.transcript_status,
                    "transcript_lang": video.transcript_lang,
                    "transcript_length_chars": None,  # derived from the external artifact
                    "view_count": obs.view_count if obs else None,
                    "like_count": obs.like_count if obs else None,
                    "comment_count": obs.comment_count if obs else None,
                    "favorite_count": obs.favorite_count if obs else None,
                }
            )
        return rows

    def _comment_rows(self, video_id: str | None = None) -> list[dict[str, Any]]:
        comments = self._repos.comments.list_comments(video_id)
        latest = self._repos.comments.get_latest_comment_observations(
            [comment.comment_id for comment in comments]
        )
        rows: list[dict[str, Any]] = []
        for comment in comments:
            obs = latest.get(comment.comment_id)
            rows.append(
                {
                    "comment_id": comment.comment_id,
                    "video_id": comment.video_id,
                    "author_id": comment.author_id,
                    "author_name": comment.author_name,
                    "comment_text": comment.comment_text,
                    "published_at": comment.published_at,
                    "is_reply": comment.is_reply,
                    "parent_comment_id": comment.parent_comment_id,
                    "root_comment_id": comment.root_comment_id,
                    "is_author": comment.is_author,
                    "like_count": obs.like_count if obs else None,
                    "reply_count": obs.reply_count if obs else None,
                    "is_removed": obs.is_removed if obs else None,
                }
            )
        return rows

    def _channel_rows(self) -> list[dict[str, Any]]:
        channels = self._repos.channels.list_channels()
        latest = self._repos.channels.get_latest_channel_observations(
            [channel.channel_id for channel in channels]
        )
        rows: list[dict[str, Any]] = []
        for channel in channels:
            obs = latest.get(channel.channel_id)
            rows.append(
                {
                    "channel_id": channel.channel_id,
                    "title": channel.title,
                    "description": channel.description,
                    "handle": channel.handle,
                    "is_verified": channel.is_verified,
                    "avatar_url": channel.avatar_url,
                    "banner_url": channel.banner_url,
                    "country": channel.country,
                    "joined_date": channel.joined_date,
                    "subscriber_count": obs.subscriber_count if obs else None,
                    "video_count": obs.video_count if obs else None,
                    "view_count": obs.view_count if obs else None,
                }
            )
        return rows

    def _recommendation_rows(
        self, run_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        edges = self._repos.recommendations.list_recommendation_edges()
        if run_ids:
            run_set = set(run_ids)
            edges = [e for e in edges if e.collection_run_id in run_set]
        rows: list[dict[str, Any]] = []
        for edge in edges:
            rows.append(
                {
                    "source_video_id": edge.source_video_id,
                    "recommended_video_id": edge.recommended_video_id,
                    "position": edge.position,
                    "status": edge.status.value,
                    "channel_id": edge.channel_id,
                    "title": edge.title,
                    "observed_at": edge.observed_at,
                }
            )
        # Feed-rank order: grouped by source, then ascending rail position
        # (unknown positions last) so the query/explorer surface reflects the
        # observed "Up Next" order.
        return sorted(
            rows,
            key=lambda row: (
                row["source_video_id"],
                row["position"] is None,
                row["position"] if row["position"] is not None else 0,
                row["recommended_video_id"],
            ),
        )

    def _author_rows(self) -> list[dict[str, Any]]:
        profiles = self._repos.authors.list_authors()
        rows: list[dict[str, Any]] = []
        for profile in profiles:
            rows.append(
                {
                    "author_id": profile.author_id,
                    "author_name": profile.author_name,
                    "comment_count": profile.comment_count,
                    "video_ids": profile.video_ids,
                    "first_seen_at": profile.first_seen_at,
                    "last_seen_at": profile.last_seen_at,
                    "is_author": profile.is_author,
                    "first_seen_run_id": profile.first_seen_run_id,
                }
            )
        return rows

    # ------------------------------------------------------------------
    def _match_video_row(self, row: dict, filter: VideoFilter) -> bool:
        """VideoFilter semantics evaluated against row dicts (same rules as
        :meth:`_matches` on Video objects)."""
        if filter.date_from is not None:
            value = row.get("upload_date")
            if value is None or value < filter.date_from:
                return False
        if filter.date_to is not None:
            value = row.get("upload_date")
            if value is None or value > filter.date_to:
                return False

        if filter.duration_min is not None:
            duration = row.get("duration")
            if duration is None or duration < filter.duration_min:
                return False
        if filter.duration_max is not None:
            duration = row.get("duration")
            if duration is None or duration > filter.duration_max:
                return False

        if filter.video_type is not None and not self._row_matches_type(row, filter.video_type):
            return False

        if filter.upload_hour is not None:
            timestamp = row.get("upload_timestamp")
            if timestamp is None or timestamp.hour != filter.upload_hour:
                return False
        if filter.upload_weekday is not None:
            timestamp = row.get("upload_timestamp")
            if timestamp is None or timestamp.weekday() != filter.upload_weekday:
                return False

        if filter.tags:
            tags = row.get("tags") or []
            if not (set(filter.tags) & set(tags)):
                return False
        if filter.category is not None:
            categories = row.get("categories") or []
            if filter.category not in categories:
                return False
        if filter.keywords:
            haystack = f"{row.get('title') or ''} {row.get('description') or ''}".lower()
            if not all(keyword.lower() in haystack for keyword in filter.keywords):
                return False

        if filter.views_min is not None or filter.views_max is not None:
            views = row.get("view_count")
            if views is None:
                return False
            if filter.views_min is not None and views < filter.views_min:
                return False
            if filter.views_max is not None and views > filter.views_max:
                return False
        return True

    def _row_matches_type(self, row: dict, video_type: str) -> bool:
        if video_type == "short":
            return row.get("is_short") is True
        if video_type == "long":
            duration = row.get("duration")
            if duration is None:
                return False
            return duration >= self._long_video_threshold and row.get("is_short") is not True
        if video_type == "live":
            return row.get("live_status") in ("is_live", "was_live", "post_live")
        return True

    @staticmethod
    def _sorted_rows(rows: list[dict], sort: str) -> list[dict]:
        return sorted(rows, key=lambda row: (row.get(sort) is None, row.get(sort)))