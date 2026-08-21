"""E2: global entity search service.

Searches across every registered entity (channel, video, comment, author,
recommendation) with one free-text ``q`` and returns a *unified* result
projection - ``{entity, entity_id, title, subtitle, score}`` - so the command
palette and search pages render heterogeneous types identically.

Ranking
-------
The query is tokenized on whitespace (lower-cased). Each entity's searchable
fields carry a static weight (title-like fields score higher than body
fields); a field's contribution is ``weight * tokens_present`` and the hit
score is the sum across fields. Hits are ordered ``score desc``, then entity
then id, and each hit is assigned a zero-padded rank so the cursor machinery in
``services.pagination`` can binary-search a stable ordering (mirrors the
explorer's ranked-rows approach).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.pagination import Paginated, page_sorted

#: Searchable text fields per entity: (field, weight). Earlier = more relevant.
_SEARCH_FIELDS: dict[str, list[tuple[str, int]]] = {
    "channel": [("title", 3), ("handle", 2), ("description", 1)],
    "video": [("title", 3), ("description", 1)],
    "comment": [("comment_text", 2), ("author_name", 1)],
    "author": [("author_name", 3), ("author_id", 2)],
    "recommendation": [("title", 3), ("recommended_video_id", 1)],
}

#: (title, subtitle) row fields used for the unified display projection.
_DISPLAY: dict[str, tuple[str, str]] = {
    "channel": ("title", "handle"),
    "video": ("title", "description"),
    "comment": ("comment_text", "author_name"),
    "author": ("author_name", "author_id"),
    "recommendation": ("title", "source_video_id"),
}

#: The stable primary id of the result per entity (also the explorer link key).
_ID_FIELD: dict[str, str] = {
    "channel": "channel_id",
    "video": "video_id",
    "comment": "comment_id",
    "author": "author_id",
    "recommendation": "observation_id",
}

#: Searchable entities, in a stable display order.
ALL_ENTITIES = ("channel", "video", "comment", "author", "recommendation")


class SearchHit(BaseModel):
    """One unified search result row."""

    model_config = ConfigDict(extra="allow")

    entity: str
    entity_id: str
    title: str | None = None
    subtitle: str | None = None
    score: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class SearchService:
    """Cross-entity free-text search with relevance ranking."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    def search(
        self,
        q: str,
        entity: str | None = None,
        cursor: str | None = None,
        page_size: int = 50,
    ) -> Paginated[SearchHit]:
        """Return one cursor-paginated page of relevance-ranked search hits.

        ``entity`` restricts to one entity; ``None`` searches all. An empty
        query returns an empty page (no gratuitous full-corpus listing).
        """
        needle = str(q or "").strip().lower()
        if not needle:
            return Paginated(items=[], next_cursor=None, has_more=False, total=0)

        entities = [entity.lower()] if entity else list(ALL_ENTITIES)
        hits = self._hits(needle, entities)
        hits.sort(key=lambda hit: (-hit.score, hit.entity, hit.entity_id))

        ranked: list[SearchHit] = []
        for index, hit in enumerate(hits):
            copy = hit.model_copy()
            copy.extra = dict(copy.extra)
            copy.extra["__rank"] = f"{index:015d}"
            ranked.append(copy)

        page = page_sorted(
            ranked,
            cursor=cursor,
            page_size=page_size,
            key_func=self._rank_key,
            total=len(ranked),
        )
        page.items = [self._visible(hit) for hit in page.items]
        return page

    # ------------------------------------------------------------------
    def _hits(self, needle: str, entities: list[str]) -> list[SearchHit]:
        tokens = needle.split()
        hits: list[SearchHit] = []
        for entity in entities:
            if entity not in _SEARCH_FIELDS:
                raise ValueError(
                    f"Unknown entity {entity!r}; expected one of {sorted(ALL_ENTITIES)}"
                )
            for row in self._rows(entity):
                score = _score(row, tokens, _SEARCH_FIELDS[entity])
                if score <= 0:
                    continue
                hits.append(_project(entity, row, score))
        return hits

    def _rows(self, entity: str) -> list[dict[str, Any]]:
        if entity == "channel":
            return [
                {
                    "channel_id": channel.channel_id,
                    "title": channel.title,
                    "handle": channel.handle,
                    "description": channel.description,
                    "country": channel.country,
                    "is_verified": channel.is_verified,
                }
                for channel in self._repos.channels.list_channels()
            ]
        if entity == "video":
            return [
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "description": video.description,
                    "channel_id": video.channel_id,
                    "thumbnail_url": video.thumbnail_url,
                }
                for video in self._repos.videos.list_videos()
            ]
        if entity == "comment":
            return [
                {
                    "comment_id": comment.comment_id,
                    "comment_text": comment.comment_text,
                    "author_name": comment.author_name,
                    "video_id": comment.video_id,
                    "published_at": comment.published_at,
                }
                for comment in self._repos.comments.list_comments()
            ]
        if entity == "author":
            return [
                {
                    "author_id": profile.author_id,
                    "author_name": profile.author_name,
                    "comment_count": profile.comment_count,
                }
                for profile in self._repos.authors.list_authors()
            ]
        if entity == "recommendation":
            return [
                {
                    "observation_id": edge.observation_id,
                    "source_video_id": edge.source_video_id,
                    "recommended_video_id": edge.recommended_video_id,
                    "title": edge.title,
                    "channel_id": edge.channel_id,
                }
                for edge in self._repos.recommendations.list_recommendation_edges()
            ]
        raise ValueError(f"Unknown entity {entity!r}")

    # ------------------------------------------------------------------
    @staticmethod
    def _rank_key(hit: SearchHit) -> tuple[str, ...]:
        return (str(hit.extra.get("__rank")), hit.entity, hit.entity_id)

    @staticmethod
    def _visible(hit: SearchHit) -> SearchHit:
        copy = hit.model_copy()
        copy.extra = {key: value for key, value in hit.extra.items() if not key.startswith("__")}
        return copy


def _score(row: dict[str, Any], tokens: list[str], fields: list[tuple[str, int]]) -> int:
    """Weighted token-overlap score; 0 means no searchable field matched."""
    total = 0
    for field, weight in fields:
        haystack = str(row.get(field) or "").lower()
        if not haystack:
            continue
        present = sum(1 for token in tokens if token in haystack)
        if present:
            total += weight * present
    return total


def _project(entity: str, row: dict[str, Any], score: int) -> SearchHit:
    title_field, subtitle_field = _DISPLAY[entity]
    extra = {
        key: value
        for key, value in row.items()
        if key not in {_ID_FIELD[entity], title_field, subtitle_field}
        and value is not None
    }
    return SearchHit(
        entity=entity,
        entity_id=str(row.get(_ID_FIELD[entity]) or ""),
        title=str(row.get(title_field) or "") or None,
        subtitle=str(row.get(subtitle_field) or "") or None,
        score=score,
        extra=extra,
    )
