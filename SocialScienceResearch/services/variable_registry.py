"""VariableRegistry: the static, in-code catalogue of research variables.

Every entity (channel, video, comment, recommendation, author) declares the
variables a researcher may query, along with their type, source (``observed`` /
``derived`` / ``raw``), unit, description, and *availability* - the exact
repository model + field that supplies the value. The catalogue is deliberately
static (no DB): the query evaluator and the explorer UI both read from this
single source of truth, and the variable ``name`` always matches a
``domain.models`` field exactly so values resolve without renaming.

Integrity is enforced by tests: every entry's ``availability`` string is
parsed as ``ModelName.field`` and asserted to exist on a real pydantic model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

_ENTITIES = ("channel", "video", "comment", "recommendation", "author")

_ALLOWED_TYPES = frozenset({"int", "float", "bool", "str", "datetime", "list"})
_ALLOWED_SOURCES = frozenset({"observed", "derived", "raw"})


class VariableMeta(BaseModel):
    """Metadata for one research variable of an entity."""

    model_config = ConfigDict(extra="forbid")

    entity: str
    name: str
    data_type: str  # int | float | bool | str | datetime | list
    source: str  # observed | derived | raw
    description: str
    unit: str | None = None
    availability: str  # "ModelName.field" that supplies the value
    limits: str | None = None


# ----------------------------------------------------------------------
# Catalogue: name is the exact domain.model field name.
# ----------------------------------------------------------------------
_CATALOGUE: dict[str, list[VariableMeta]] = {
    "channel": [
        VariableMeta(
            entity="channel", name="title", data_type="str", source="observed",
            description="Display name of the channel.",
            availability="Channel.title",
        ),
        VariableMeta(
            entity="channel", name="description", data_type="str", source="observed",
            description="Channel description banner text.",
            availability="Channel.description",
        ),
        VariableMeta(
            entity="channel", name="handle", data_type="str", source="observed",
            description="Social handle, e.g. '@example'.",
            availability="Channel.handle",
        ),
        VariableMeta(
            entity="channel", name="is_verified", data_type="bool", source="observed",
            description="Whether the channel is verified by the platform.",
            availability="Channel.is_verified",
        ),
        VariableMeta(
            entity="channel", name="avatar_url", data_type="str", source="observed",
            description="URL of the channel avatar image.",
            availability="Channel.avatar_url",
        ),
        VariableMeta(
            entity="channel", name="banner_url", data_type="str", source="observed",
            description="URL of the channel banner image.",
            availability="Channel.banner_url",
        ),
        VariableMeta(
            entity="channel", name="country", data_type="str", source="observed",
            description="Country the channel is associated with (if disclosed).",
            availability="Channel.country",
        ),
        VariableMeta(
            entity="channel", name="joined_date", data_type="datetime", source="observed",
            description="Date the channel joined the platform.",
            availability="Channel.joined_date",
            limits="ISO date",
        ),
        VariableMeta(
            entity="channel", name="subscriber_count", data_type="int", source="observed",
            description="Latest observed subscriber count.",
            unit="subscribers",
            availability="ChannelObservation.subscriber_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="channel", name="video_count", data_type="int", source="observed",
            description="Latest observed count of public videos.",
            unit="videos",
            availability="ChannelObservation.video_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="channel", name="view_count", data_type="int", source="observed",
            description="Latest observed total channel views.",
            unit="views",
            availability="ChannelObservation.view_count",
            limits=">= 0",
        ),
    ],
    "video": [
        VariableMeta(
            entity="video", name="channel_id", data_type="str", source="observed",
            description="Stable id of the channel that owns the video.",
            availability="Video.channel_id",
        ),
        VariableMeta(
            entity="video", name="title", data_type="str", source="observed",
            description="Video title.",
            availability="Video.title",
        ),
        VariableMeta(
            entity="video", name="description", data_type="str", source="observed",
            description="Video description text.",
            availability="Video.description",
        ),
        VariableMeta(
            entity="video", name="duration", data_type="int", source="observed",
            description="Video duration in seconds (reported as 'duration_seconds').",
            unit="seconds",
            availability="Video.duration",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="upload_date", data_type="datetime", source="observed",
            description="Publication date reported by the source.",
            availability="Video.upload_date",
            limits="ISO date",
        ),
        VariableMeta(
            entity="video", name="upload_timestamp", data_type="datetime", source="observed",
            description="Full publication timestamp; offers hour/weekday granularity.",
            availability="Video.upload_timestamp",
        ),
        VariableMeta(
            entity="video", name="tags", data_type="list", source="observed",
            description="Video tags as published.",
            availability="Video.tags",
        ),
        VariableMeta(
            entity="video", name="categories", data_type="list", source="observed",
            description="Category labels the video belongs to.",
            availability="Video.categories",
        ),
        VariableMeta(
            entity="video", name="language", data_type="str", source="observed",
            description="Detected or declared language.",
            availability="Video.language",
        ),
        VariableMeta(
            entity="video", name="live_status", data_type="str", source="observed",
            description="live state: is_live / was_live / post_live / None.",
            availability="Video.live_status",
        ),
        VariableMeta(
            entity="video", name="availability", data_type="str", source="observed",
            description="Source availability of the video.",
            availability="Video.availability",
        ),
        VariableMeta(
            entity="video", name="age_limit", data_type="int", source="observed",
            description="Age rating limit if the source disclosed one.",
            availability="Video.age_limit",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="is_short", data_type="bool", source="observed",
            description="Whether the video is in short format.",
            availability="Video.is_short",
        ),
        VariableMeta(
            entity="video", name="thumbnail_url", data_type="str", source="observed",
            description="URL of the video thumbnail.",
            availability="Video.thumbnail_url",
        ),
        VariableMeta(
            entity="video", name="view_count", data_type="int", source="observed",
            description="Latest observed view count.",
            unit="views",
            availability="VideoObservation.view_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="like_count", data_type="int", source="observed",
            description="Latest observed like count.",
            unit="likes",
            availability="VideoObservation.like_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="comment_count", data_type="int", source="observed",
            description="Latest observed comment count.",
            unit="comments",
            availability="VideoObservation.comment_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="favorite_count", data_type="int", source="observed",
            description="Latest observed favorite count.",
            unit="favorites",
            availability="VideoObservation.favorite_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="video", name="transcript_status", data_type="str", source="derived",
            description="Transcript availability status (available/missing/unsupported).",
            availability="Video.transcript_status",
        ),
        VariableMeta(
            entity="video", name="transcript_lang", data_type="str", source="derived",
            description="Language of the extracted transcript.",
            availability="Video.transcript_lang",
        ),
        VariableMeta(
            entity="video", name="transcript_length_chars", data_type="int", source="derived",
            description="Character length of the transcript artifact (derived from the file referenced by transcript_path).",
            unit="chars",
            availability="Video.transcript_path",
            limits=">= 0",
        ),
    ],
    "comment": [
        VariableMeta(
            entity="comment", name="author_id", data_type="str", source="observed",
            description="Stable id of the comment author.",
            availability="Comment.author_id",
        ),
        VariableMeta(
            entity="comment", name="author_name", data_type="str", source="observed",
            description="Display name of the comment author.",
            availability="Comment.author_name",
        ),
        VariableMeta(
            entity="comment", name="comment_text", data_type="str", source="observed",
            description="Body of the comment (reported as 'text').",
            availability="Comment.comment_text",
        ),
        VariableMeta(
            entity="comment", name="published_at", data_type="datetime", source="observed",
            description="Publication timestamp of the comment.",
            availability="Comment.published_at",
        ),
        VariableMeta(
            entity="comment", name="is_reply", data_type="bool", source="observed",
            description="True when the comment is a direct reply, not a root comment.",
            availability="Comment.is_reply",
        ),
        VariableMeta(
            entity="comment", name="parent_comment_id", data_type="str", source="observed",
            description="Id of the comment this comment directly replies to (None for roots).",
            availability="Comment.parent_comment_id",
        ),
        VariableMeta(
            entity="comment", name="root_comment_id", data_type="str", source="observed",
            description="Id of the top-most comment of the thread.",
            availability="Comment.root_comment_id",
        ),
        VariableMeta(
            entity="comment", name="is_author", data_type="bool", source="observed",
            description="True when the uploader of the video authored the comment.",
            availability="Comment.is_author",
        ),
        VariableMeta(
            entity="comment", name="like_count", data_type="int", source="observed",
            description="Latest observed like count of the comment.",
            unit="likes",
            availability="CommentObservation.like_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="comment", name="reply_count", data_type="int", source="observed",
            description="Latest observed direct-reply count.",
            unit="replies",
            availability="CommentObservation.reply_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="comment", name="is_removed", data_type="bool", source="observed",
            description="Latest observed removal state of the comment.",
            availability="CommentObservation.is_removed",
        ),
    ],
    "author": [
        VariableMeta(
            entity="author", name="author_id", data_type="str", source="derived",
            description="Stable author key (author_id, falling back to author_name).",
            availability="AuthorProfile.author_id",
        ),
        VariableMeta(
            entity="author", name="author_name", data_type="str", source="raw",
            description="Display name of the comment author (best-known).",
            availability="AuthorProfile.author_name",
        ),
        VariableMeta(
            entity="author", name="comment_count", data_type="int", source="derived",
            description="Total comments the author contributed across the corpus.",
            unit="comments",
            availability="AuthorProfile.comment_count",
            limits=">= 0",
        ),
        VariableMeta(
            entity="author", name="video_ids", data_type="list", source="derived",
            description="Distinct videos the author commented on.",
            availability="AuthorProfile.video_ids",
        ),
        VariableMeta(
            entity="author", name="first_seen_at", data_type="datetime", source="derived",
            description="Earliest comment publication time observed for the author.",
            availability="AuthorProfile.first_seen_at",
        ),
        VariableMeta(
            entity="author", name="last_seen_at", data_type="datetime", source="derived",
            description="Most recent comment publication time observed for the author.",
            availability="AuthorProfile.last_seen_at",
        ),
        VariableMeta(
            entity="author", name="is_author", data_type="bool", source="observed",
            description="True when the author ever authored a commented video.",
            availability="AuthorProfile.is_author",
        ),
        VariableMeta(
            entity="author", name="first_seen_run_id", data_type="str", source="derived",
            description="Run that first observed a comment from this author.",
            availability="AuthorProfile.first_seen_run_id",
        ),
    ],
    "recommendation": [
        VariableMeta(
            entity="recommendation", name="source_video_id", data_type="str", source="observed",
            description="Video the recommendation originates from.",
            availability="RecommendationObservation.source_video_id",
        ),
        VariableMeta(
            entity="recommendation", name="recommended_video_id", data_type="str", source="observed",
            description="Video recommended by the source.",
            availability="RecommendationObservation.recommended_video_id",
        ),
        VariableMeta(
            entity="recommendation", name="position", data_type="int", source="observed",
            description="Ordering reported by the source, if any.",
            availability="RecommendationObservation.position",
            limits=">= 0",
        ),
        VariableMeta(
            entity="recommendation", name="status", data_type="str", source="observed",
            description="observed / unsupported / failed.",
            availability="RecommendationObservation.status",
        ),
        VariableMeta(
            entity="recommendation", name="channel_id", data_type="str", source="observed",
            description="Channel of the recommended video if disclosed.",
            availability="RecommendationObservation.channel_id",
        ),
        VariableMeta(
            entity="recommendation", name="title", data_type="str", source="observed",
            description="Title of the recommended video if disclosed.",
            availability="RecommendationObservation.title",
        ),
        VariableMeta(
            entity="recommendation", name="observed_at", data_type="datetime", source="observed",
            description="When the edge was observed.",
            availability="RecommendationObservation.observed_at",
        ),
    ],
}


#: Per-entity name -> VariableMeta index for O(1) lookups.
_BY_ENTITY: dict[str, dict[str, VariableMeta]] = {
    entity: {meta.name: meta for meta in metas}
    for entity, metas in _CATALOGUE.items()
}


class VariableRegistry:
    """Static accessors over the in-code variable catalogue."""

    @staticmethod
    def entities() -> list[str]:
        return list(_ENTITIES)

    @staticmethod
    def get_variables(entity: str) -> list[VariableMeta]:
        if entity not in _CATALOGUE:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of {sorted(_ENTITIES)}"
            )
        return list(_CATALOGUE[entity])

    @staticmethod
    def get_variable(entity: str, name: str) -> VariableMeta | None:
        if entity not in _BY_ENTITY:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of {sorted(_ENTITIES)}"
            )
        return _BY_ENTITY[entity].get(name)

    @staticmethod
    def all_variables() -> list[VariableMeta]:
        return [meta for entity in _ENTITIES for meta in _CATALOGUE[entity]]

    @staticmethod
    def allowed_types() -> frozenset[str]:
        return _ALLOWED_TYPES

    @staticmethod
    def allowed_sources() -> frozenset[str]:
        return _ALLOWED_SOURCES