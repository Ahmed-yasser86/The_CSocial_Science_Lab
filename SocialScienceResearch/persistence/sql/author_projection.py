"""PostgreSQL-backed repository for aggregated author participation profiles (D4).

Mirrors ``persistence.author_repository.ExcelAuthorRepository``: profiles are a
read-side projection over the persisted comments corpus (never written back),
so the SQL implementation reads the ``comments`` table through the shared
``_author_key`` / ``_aggregate`` / ``_merge_author_raw`` helpers.
"""

from __future__ import annotations

from typing import Any

from SocialScienceResearch.domain.models import AuthorProfile, Comment
from SocialScienceResearch.persistence.author_repository import (
    _aggregate,
    _author_key,
)
from SocialScienceResearch.persistence.base import AuthorRepository
from SocialScienceResearch.persistence.sql.database import SqlDatabase
from SocialScienceResearch.persistence.sql.mapping import _row


class SqlAuthorRepository(AuthorRepository):
    """Read-only, SQL-backed aggregation of comment authors."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def list_authors(self) -> list[AuthorProfile]:
        comments = self._comments()
        by_author: dict[str, list[Comment]] = {}
        for comment in comments:
            key = _author_key(comment)
            if key is None:
                continue
            by_author.setdefault(key, []).append(comment)
        profiles = [_aggregate(key, entries) for key, entries in by_author.items()]
        return sorted(profiles, key=lambda profile: profile.author_id)

    def get_author(self, author_id: str) -> AuthorProfile | None:
        comments = [
            comment
            for comment in self._comments()
            if _author_key(comment) == author_id
        ]
        if not comments:
            return None
        return _aggregate(author_id, comments)

    def explore_author_rows(self) -> list[dict[str, Any]]:
        """Aggregate author profiles from column-projected comments.

        Builds the same rows the explorer expects without pulling each
        comment's multi-KB ``raw_json`` blob (the profile raw surface is only
        needed by the on-demand raw-record endpoint, not the explorer table).
        """
        comments = self._projected_comments()
        by_author: dict[str, list[Comment]] = {}
        for comment in comments:
            key = _author_key(comment)
            if key is None:
                continue
            by_author.setdefault(key, []).append(comment)
        profiles = [_aggregate(key, entries) for key, entries in by_author.items()]
        profiles.sort(key=lambda p: p.author_id)
        return [
            {
                "author_id": p.author_id,
                "author_name": p.author_name,
                "comment_count": p.comment_count,
                "video_ids": p.video_ids,
                "first_seen_at": p.first_seen_at,
                "last_seen_at": p.last_seen_at,
                "is_author": p.is_author,
                "first_seen_run_id": p.first_seen_run_id,
            }
            for p in profiles
        ]

    def _comments(self) -> list[Comment]:
        rows = self._db.execute('SELECT * FROM "comments"')
        return [
            _row(Comment, row)  # type: ignore[return-value]
            for row in rows
        ]

    def _projected_comments(self) -> list[Comment]:
        rows = self._db.execute(
            'SELECT "comment_id", "video_id", "author_name", "author_id", '
            '"published_at", "first_observed_run_id", "is_author" '
            'FROM "comments"'
        )
        return [
            Comment(
                comment_id=str(row["comment_id"]),
                video_id=row["video_id"],
                author_name=row["author_name"],
                author_id=row["author_id"],
                published_at=row["published_at"],
                first_observed_run_id=row["first_observed_run_id"],
                is_author=row["is_author"],
            )
            for row in rows
        ]