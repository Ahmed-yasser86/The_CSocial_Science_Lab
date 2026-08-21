"""Excel-backed repository for aggregated author participation profiles (D4).

Author profiles are *derived* from the persisted comments corpus: one profile
per ``author_id`` (falling back to ``author_name``) aggregating comment count,
the distinct videos commented on, first/last seen timestamps, the producing run
and a best-effort ``raw_json`` of the raw author metadata already collected with
comments (ADR-0010). Because profiles are a read-side projection, this
repository reads the ``comments`` sheet through ``WorkbookStore`` + the
``persistence.serialization`` helpers and performs no writes - there is no
separate ``authors`` sheet and no risk of the projection drifting from the
source comments.

Raw profile extraction
----------------------
The comment ``raw_json`` carries the yt-dlp author metadata (``author``,
``author_id``/``author_channel_id``, ``author_is_uploader``,
``author_is_verified``, ``author_thumbnail``, ...). ``raw_json`` of the profile
is the union of those author-prefixed keys seen across the author's comments so
the raw surface is available for dataset/export use without re-parsing source
payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from SocialScienceResearch.domain.models import AuthorProfile, Comment
from SocialScienceResearch.persistence.base import AuthorRepository
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import row_to_model

#: ``comments`` sheet is guaranteed by the shared entity repositories, so the
#: author projection only needs to *read* it - never ``ensure_sheet`` it.
_COMMENTS_SHEET = "comments"

#: Prefix of raw author metadata keys carried in a comment's ``raw_json``.
_AUTHOR_KEY_PREFIX = "author"


class ExcelAuthorRepository(AuthorRepository):
    """Read-only, store-backed aggregation of comment authors."""

    def __init__(self, store: WorkbookStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    def list_authors(self) -> list[AuthorProfile]:
        """Return one aggregated profile per comment author, id-ordered."""
        comments = self._comments()
        by_author: dict[str, list[Comment]] = {}
        for comment in comments:
            key = _author_key(comment)
            if key is None:
                continue
            by_author.setdefault(key, []).append(comment)
        profiles = [
            _aggregate(key, entries) for key, entries in by_author.items()
        ]
        return sorted(profiles, key=lambda profile: profile.author_id)

    def get_author(self, author_id: str) -> AuthorProfile | None:
        """Return the aggregated profile of one author, if any comments exist."""
        comments = [
            comment
            for comment in self._comments()
            if _author_key(comment) == author_id
        ]
        if not comments:
            return None
        return _aggregate(author_id, comments)

    # ------------------------------------------------------------------
    def _comments(self) -> list[Comment]:
        rows = self._store.read_rows(_COMMENTS_SHEET, key_field="comment_id")
        return [
            row_to_model(Comment, row)  # type: ignore[return-value]
            for row in rows
        ]


def _author_key(comment: Comment) -> str | None:
    """Stable aggregation key: ``author_id`` with a name fallback."""
    if comment.author_id:
        return comment.author_id
    if comment.author_name:
        return comment.author_name
    return None


def _aggregate(key: str, comments: list[Comment]) -> AuthorProfile:
    """Build one AuthorProfile from an author's comment set."""
    sorted_comments = sorted(
        comments,
        key=lambda c: (
            c.published_at is None,
            c.published_at.isoformat() if c.published_at else "",
            c.comment_id,
        ),
    )
    first = sorted_comments[0]
    last = sorted_comments[-1]
    video_ids: list[str] = []
    for comment in sorted_comments:
        if comment.video_id and comment.video_id not in video_ids:
            video_ids.append(comment.video_id)
    raw_json = _merge_author_raw(sorted_comments)
    return AuthorProfile(
        author_id=key,
        author_name=first.author_name,
        comment_count=len(sorted_comments),
        video_ids=video_ids,
        first_seen_run_id=first.first_observed_run_id,
        first_seen_at=first.published_at,
        last_seen_at=last.published_at,
        is_author=any(comment.is_author is True for comment in sorted_comments),
        raw_json=raw_json,
    )


def _merge_author_raw(comments: list[Comment]) -> dict[str, Any]:
    """Union of author-prefixed metadata keys across the author's comments.

    Later comments overwrite earlier ones for the same key (the newest value
    wins); keys with ``None`` values are dropped.
    """
    merged: dict[str, Any] = {}
    for comment in comments:
        for raw_key, value in (comment.raw_json or {}).items():
            if raw_key.lower().startswith(_AUTHOR_KEY_PREFIX) and value is not None:
                merged[raw_key] = value
    return merged
