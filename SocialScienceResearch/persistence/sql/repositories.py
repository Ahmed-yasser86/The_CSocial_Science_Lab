"""PostgreSQL implementations of the persistence contract.

Each repository mirrors the behaviour of its Excel counterpart in
``persistence.excel_repository`` / ``persistence.*_repository`` so the domain
services and tests behave identically, while using ``JSONB`` columns (no
32k-cell sidecars), real deletes and indexed latest-observation resolution.

Shared mapping helpers
----------------------
* ``_cols(model)`` -> declared column names (``headers_for``).
* ``_params(model)`` -> parameter dict with ``datetime``/``date`` kept native
  and ``dict``/``list`` wrapped in :class:`psycopg.types.json.Jsonb`.
* ``_row(model, db_row)`` -> ``row_to_model``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from psycopg.types.json import Jsonb

from SocialScienceResearch.domain.dataset_models import Dataset, Project, ProjectItem
from SocialScienceResearch.domain.echo_models import EchoDetection
from SocialScienceResearch.domain.enums import EntityType
from SocialScienceResearch.domain.job_models import CollectionJob
from SocialScienceResearch.domain.layer_models import LayerRun
from SocialScienceResearch.domain.models import (
    AuthorProfile,
    Channel,
    ChannelObservation,
    CollectionError,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    TranscriptRecord,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.sample_models import Sample
from SocialScienceResearch.persistence.base import (
    ChannelRepository,
    CollectionRunRepository,
    CommentRepository,
    EchoDetectionRepository,
    JobRepository,
    LayerRunRepository,
    ProjectItemRepository,
    RecommendationRepository,
    Repositories,
    TranscriptRepository,
    UpsertResult,
    VideoRepository,
)
from SocialScienceResearch.persistence.serialization import headers_for


def _proj_cols(model_cls: type) -> str:
    """Comma-separated, quoted column list for ``model_cls`` minus the
    ``raw_json`` TOAST blob -- used by observation/latest lookups so a
    ``SELECT *`` doesn't pull the heavy JSONB for every row."""
    return ", ".join(f'"{c}"' for c in headers_for(model_cls) if c != "raw_json")
from SocialScienceResearch.persistence.sql.database import DEFAULT_DATABASE_URL, SqlDatabase

from .mapping import _params, _row
from .author_projection import SqlAuthorRepository


# ---------------------------------------------------------------------------
# Shared SQL entity repository
# ---------------------------------------------------------------------------

class _SqlEntityRepository:
    """Common upsert/get/list plumbing for PK-keyed entity tables."""

    _TABLE = ""
    _MODEL = None
    _KEY = ""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def _columns(self) -> list[str]:
        return headers_for(self._MODEL)  # type: ignore[arg-type]

    def _upsert(self, model, entity_type: EntityType) -> UpsertResult:
        cols = self._columns()
        key = str(getattr(model, self._KEY))
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != self._KEY)
        sql = (
            f'INSERT INTO "{self._TABLE}" ({col_list}) VALUES ({ph}) '
            f'ON CONFLICT ("{self._KEY}") DO UPDATE SET {update} '
            "RETURNING (xmax = 0) AS created"
        )
        row = self._db.fetchone(sql, _params(model))
        created = bool(row["created"]) if row else False
        return UpsertResult(entity_type=entity_type, entity_id=key, created=created)

    def _get(self, key: str):
        row = self._db.fetchone(
            f'SELECT * FROM "{self._TABLE}" WHERE "{self._KEY}" = %(key)s',
            {"key": str(key)},
        )
        return _row(self._MODEL, row)  # type: ignore[arg-type]

    def _list(self):
        # Project every declared column except the ``raw_json`` TOAST blob: a
        # full ``SELECT *`` pulls the JSONB for every row and is extremely slow
        # at scale. List callers only need the structured columns; the raw
        # payload stays available via the single-row ``_get``.
        cols = [c for c in headers_for(self._MODEL) if c != "raw_json"]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        rows = self._db.execute(f'SELECT {col_sql} FROM "{self._TABLE}"')
        return [_row(self._MODEL, r) for r in rows]  # type: ignore[arg-type]

    def _save_observation(self, model) -> None:
        table = self._OBS_TABLE
        cols = headers_for(type(model))
        key = "observation_id"
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != key)
        self._db.execute(
            f'INSERT INTO "{table}" ({col_list}) VALUES ({ph}) '
            f'ON CONFLICT ("{key}") DO UPDATE SET {update}',
            _params(model),
        )

    def _list_observations(self, model_cls, table: str):
        rows = self._db.execute(f'SELECT * FROM "{table}"')
        return [_row(model_cls, r) for r in rows]  # type: ignore[arg-type]


def _latest_by_id(
    rows: list[dict[str, Any]], ids: list[str] | None, id_field: str
) -> dict[str, Any]:
    """Group rows by ``id_field`` keeping the most recent ``observed_at``.

    Mirrors ``_ExcelEntityRepository._latest_obs_by_id``: on ties the last
    scanned row wins (rows arrive in ``observed_at DESC, seq DESC`` order from
    the SQL query, so the first occurrence of each id is the newest).
    """
    wanted = set(ids) if ids is not None else None
    latest: dict[str, Any] = {}
    for row in rows:
        key = str(row.get(id_field))
        if wanted is not None and key not in wanted:
            continue
        if key not in latest:
            latest[key] = row
    if wanted is None:
        return latest
    return {key: latest[key] for key in ids if key in latest}


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class SqlChannelRepository(_SqlEntityRepository, ChannelRepository):
    _TABLE = "channels"
    _MODEL = Channel
    _KEY = "channel_id"
    _OBS_TABLE = "channel_observations"

    def upsert_channel(self, channel: Channel) -> UpsertResult:
        return self._upsert(channel, EntityType.CHANNEL)

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._get(channel_id)  # type: ignore[return-value]

    def list_channels(self, channel_ids: list[str] | None = None) -> list[Channel]:
        if channel_ids is None:
            return self._list()  # type: ignore[return-value]
        cols = [c for c in headers_for(Channel) if c != "raw_json"]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        rows = self._db.execute(
            f'SELECT {col_sql} FROM "channels" WHERE "channel_id" = ANY(%(ids)s)',
            {"ids": list(channel_ids)},
        )
        return [_row(Channel, r) for r in rows]  # type: ignore[return-value]

    def list_channel_titles(self) -> dict[str, str]:
        rows = self._db.execute('SELECT "channel_id", "title" FROM "channels"')
        return {str(r["channel_id"]): str(r["title"]) for r in rows}

    def list_channel_descriptors(self) -> dict[str, dict[str, Any]]:
        rows = self._db.execute(
            'SELECT "channel_id", "title", "avatar_url" FROM "channels"'
        )
        return {
            str(r["channel_id"]): {
                "channel_id": str(r["channel_id"]),
                "title": r["title"],
                "avatar_url": r["avatar_url"],
            }
            for r in rows
        }

    def latest_channel_metrics(
        self, channel_ids: list[str]
    ) -> dict[str, dict[str, int | None]]:
        if not channel_ids:
            return {}
        rows = self._db.execute(
            f'SELECT "channel_id", "subscriber_count", "video_count", "view_count" '
            f'FROM "{self._OBS_TABLE}" '
            'WHERE "channel_id" = ANY(%(ids)s) '
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(channel_ids)},
        )
        best: dict[str, dict[str, int | None]] = {}
        for r in rows:
            cid = str(r["channel_id"])
            if cid not in best:
                best[cid] = {
                    "subscriber_count": r["subscriber_count"],
                    "video_count": r["video_count"],
                    "view_count": r["view_count"],
                }
        return best

    def explore_channel_rows(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            'SELECT "channel_id", "title", "description", "handle", "is_verified", '
            '"avatar_url", "banner_url", "country", "joined_date" FROM "channels"'
        )
        channels = [dict(r) for r in rows]
        latest = self.latest_channel_metrics([r["channel_id"] for r in channels])
        return [
            {
                "channel_id": r["channel_id"],
                "title": r["title"],
                "description": r["description"],
                "handle": r["handle"],
                "is_verified": r["is_verified"],
                "avatar_url": r["avatar_url"],
                "banner_url": r["banner_url"],
                "country": r["country"],
                "joined_date": r["joined_date"],
                "subscriber_count": latest.get(r["channel_id"], {}).get("subscriber_count"),
                "video_count": latest.get(r["channel_id"], {}).get("video_count"),
                "view_count": latest.get(r["channel_id"], {}).get("view_count"),
            }
            for r in channels
        ]

    def save_channel_observation(self, observation: ChannelObservation) -> None:
        self._save_observation(observation)

    def list_channel_observations(self, channel_id: str) -> list[ChannelObservation]:
        rows = self._db.execute(
            f'SELECT * FROM "{self._OBS_TABLE}" '
            'WHERE "channel_id" = %(cid)s ORDER BY "observed_at", "seq"',
            {"cid": channel_id},
        )
        return [_row(ChannelObservation, r) for r in rows]  # type: ignore[return-value]

    def get_latest_channel_observation(
        self, channel_id: str
    ) -> ChannelObservation | None:
        row = self._db.fetchone(
            f'SELECT * FROM "{self._OBS_TABLE}" '
            'WHERE "channel_id" = %(cid)s '
            'ORDER BY "observed_at" DESC, "seq" DESC LIMIT 1',
            {"cid": channel_id},
        )
        return _row(ChannelObservation, row)  # type: ignore[return-value]

    def get_latest_channel_observations(
        self, channel_ids: list[str]
    ) -> dict[str, ChannelObservation]:
        if not channel_ids:
            return {}
        rows = self._db.execute(
            f'SELECT {_proj_cols(ChannelObservation)} FROM "{self._OBS_TABLE}" '
            "WHERE \"channel_id\" = ANY(%(ids)s) "
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(channel_ids)},
        )
        by_id = _latest_by_id(rows, channel_ids, "channel_id")
        return {
            cid: _row(ChannelObservation, row)  # type: ignore[misc]
            for cid, row in by_id.items()
        }


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

class SqlVideoRepository(_SqlEntityRepository, VideoRepository):
    _TABLE = "videos"
    _MODEL = Video
    _KEY = "video_id"
    _OBS_TABLE = "video_observations"

    def upsert_video(self, video: Video) -> UpsertResult:
        return self._upsert(video, EntityType.VIDEO)

    def get_video(self, video_id: str) -> Video | None:
        return self._get(video_id)  # type: ignore[return-value]

    def list_videos(
        self,
        channel_id: str | None = None,
        video_ids: list[str] | None = None,
    ) -> list[Video]:
        cols = [c for c in headers_for(Video) if c != "raw_json"]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        if video_ids is not None:
            # Scope to the explicit id set (bounded query; avoids a full-table scan
            # for audience-detail lookups that only need a handful of videos).
            rows = self._db.execute(
                f'SELECT {col_sql} FROM "videos" WHERE "video_id" = ANY(%(vids)s)',
                {"vids": list(video_ids)},
            )
        elif channel_id is None:
            rows = self._db.execute(f'SELECT {col_sql} FROM "videos"')
        else:
            rows = self._db.execute(
                f'SELECT {col_sql} FROM "videos" WHERE "channel_id" = %(cid)s',
                {"cid": channel_id},
            )
        return [_row(Video, r) for r in rows]  # type: ignore[return-value]

    def list_videos_by_run(self, run_id: str) -> list[Video]:
        rows = self._db.execute(
            'SELECT * FROM "videos" WHERE "first_observed_run_id" = %(rid)s',
            {"rid": run_id},
        )
        return [_row(Video, r) for r in rows]  # type: ignore[return-value]

    def mark_recommendations_scraped(self, video_id: str) -> None:
        self._db.execute(
            'UPDATE "videos" SET "recommendations_scraped" = true '
            'WHERE "video_id" = %(vid)s',
            {"vid": video_id},
        )

    def delete_video(self, video_id: str) -> None:
        self._db.execute(
            'DELETE FROM "videos" WHERE "video_id" = %(vid)s', {"vid": video_id}
        )

    def save_video_observation(self, observation: VideoObservation) -> None:
        self._save_observation(observation)

    def list_video_observations(self, video_id: str) -> list[VideoObservation]:
        rows = self._db.execute(
            f'SELECT * FROM "{self._OBS_TABLE}" '
            'WHERE "video_id" = %(vid)s ORDER BY "observed_at", "seq"',
            {"vid": video_id},
        )
        return [_row(VideoObservation, r) for r in rows]  # type: ignore[return-value]

    def get_latest_video_observation(
        self, video_id: str
    ) -> VideoObservation | None:
        row = self._db.fetchone(
            f'SELECT * FROM "{self._OBS_TABLE}" '
            'WHERE "video_id" = %(vid)s '
            'ORDER BY "observed_at" DESC, "seq" DESC LIMIT 1',
            {"vid": video_id},
        )
        return _row(VideoObservation, row)  # type: ignore[return-value]

    def get_latest_video_observations(
        self, video_ids: list[str]
    ) -> dict[str, VideoObservation]:
        if not video_ids:
            return {}
        rows = self._db.execute(
            f'SELECT {_proj_cols(VideoObservation)} FROM "{self._OBS_TABLE}" '
            "WHERE \"video_id\" = ANY(%(ids)s) "
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(video_ids)},
        )
        by_id = _latest_by_id(rows, video_ids, "video_id")
        return {
            vid: _row(VideoObservation, row)  # type: ignore[misc]
            for vid, row in by_id.items()
        }

    def list_video_metadata(
        self, video_ids: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        sql = (
            'SELECT "video_id", "channel_id", "title", "thumbnail_url", '
            '"duration", "recommendations_scraped" FROM "videos"'
        )
        params: dict[str, Any] = {}
        if video_ids is not None:
            sql += ' WHERE "video_id" = ANY(%(ids)s)'
            params["ids"] = list(video_ids)
        rows = self._db.execute(sql, params)
        return {
            str(r["video_id"]): {
                "video_id": str(r["video_id"]),
                "channel_id": r["channel_id"],
                "title": r["title"],
                "thumbnail_url": r["thumbnail_url"],
                "duration": r["duration"],
                "recommendations_scraped": bool(r["recommendations_scraped"]),
            }
            for r in rows
        }

    def latest_observation_metrics(
        self, video_ids: list[str]
    ) -> dict[str, dict[str, int | None]]:
        if not video_ids:
            return {}
        rows = self._db.execute(
            f'SELECT "video_id", "view_count", "like_count", "comment_count", '
            f'"favorite_count" FROM "{self._OBS_TABLE}" '
            'WHERE "video_id" = ANY(%(ids)s) '
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(video_ids)},
        )
        best: dict[str, dict[str, int | None]] = {}
        for r in rows:
            vid = str(r["video_id"])
            if vid not in best:
                best[vid] = {
                    "view_count": r["view_count"],
                    "like_count": r["like_count"],
                    "comment_count": r["comment_count"],
                    "favorite_count": r["favorite_count"],
                }
        return best

    def explore_video_rows(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            'SELECT "video_id", "channel_id", "title", "description", "duration", '
            '"upload_date", "upload_timestamp", "tags", "categories", "language", '
            '"live_status", "availability", "age_limit", "is_short", '
            '"thumbnail_url", "transcript_status", "transcript_lang" FROM "videos"'
        )
        videos = [dict(r) for r in rows]
        latest = self.latest_observation_metrics([str(r["video_id"]) for r in videos])
        return [
            {
                "video_id": str(r["video_id"]),
                "channel_id": r["channel_id"],
                "title": r["title"],
                "description": r["description"],
                "duration": r["duration"],
                "upload_date": r["upload_date"],
                "upload_timestamp": r["upload_timestamp"],
                "tags": r["tags"] or [],
                "categories": r["categories"] or [],
                "language": r["language"],
                "live_status": r["live_status"],
                "availability": r["availability"],
                "age_limit": r["age_limit"],
                "is_short": r["is_short"],
                "thumbnail_url": r["thumbnail_url"],
                "transcript_status": r["transcript_status"],
                "transcript_lang": r["transcript_lang"],
                "transcript_length_chars": None,
                "view_count": latest.get(str(r["video_id"]), {}).get("view_count"),
                "like_count": latest.get(str(r["video_id"]), {}).get("like_count"),
                "comment_count": latest.get(str(r["video_id"]), {}).get("comment_count"),
                "favorite_count": latest.get(str(r["video_id"]), {}).get("favorite_count"),
            }
            for r in videos
        ]


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class SqlCommentRepository(_SqlEntityRepository, CommentRepository):
    _TABLE = "comments"
    _MODEL = Comment
    _KEY = "comment_id"
    _OBS_TABLE = "comment_observations"

    def upsert_comment(self, comment: Comment) -> UpsertResult:
        return self._upsert(comment, EntityType.COMMENT)

    def get_comment(self, comment_id: str) -> Comment | None:
        return self._get(comment_id)  # type: ignore[return-value]

    def list_comments(self, video_id: str | None = None) -> list[Comment]:
        if video_id is None:
            return self._list()  # type: ignore[return-value]
        rows = self._db.execute(
            'SELECT * FROM "comments" WHERE "video_id" = %(vid)s', {"vid": video_id}
        )
        return [_row(Comment, r) for r in rows]  # type: ignore[return-value]

    def iter_comments(
        self,
        chunk_size: int = 5000,
        columns: list[str] | None = None,
        video_ids: list[str] | None = None,
    ) -> Iterator[list[Comment]]:
        """Keyset-paginated, column-projected comment scan (bounded memory).

        Chunks of ``chunk_size`` rows are fetched per query (ordered by the
        ``comment_id`` primary key, resuming after the last seen key) so a
        full-corpus scan never materializes the whole result set -- an
        unbounded ``SELECT`` on the production corpus exhausts client memory.
        ``columns`` projects only the fields the caller consumes; ``video_ids``
        scopes the scan to a set of videos server-side. The model's required
        columns are always included so rows rebuild into ``Comment``.

        When ``video_ids`` is given we scope with ``video_id = ANY(...)`` and
        paginate by OFFSET (the result set is already bounded by the video set,
        so the planner can use the video_id index instead of a full table
        scan keyed by comment_id).
        """
        declared = [c for c in headers_for(Comment) if c != "raw_json"]
        wanted = [c for c in (columns or declared) if c in declared]
        for required in ("comment_id", "video_id", "first_observed_run_id"):
            if required not in wanted:
                wanted.append(required)
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        if video_ids:
            params: dict[str, Any] = {
                "chunk": chunk_size,
                "vids": list(video_ids),
                "offset": 0,
            }
            while True:
                sql = (
                    f'SELECT {col_sql} FROM "comments" '
                    'WHERE "video_id" = ANY(%(vids)s) '
                    'ORDER BY "comment_id" LIMIT %(chunk)s OFFSET %(offset)s'
                )
                rows = self._db.execute(sql, params)
                if not rows:
                    break
                yield [_row(Comment, r) for r in rows]  # type: ignore[misc]
                if len(rows) < chunk_size:
                    break
                params["offset"] += chunk_size
            return
        last_key: str | None = None
        while True:
            sql = f'SELECT {col_sql} FROM "comments"'
            params = {"chunk": chunk_size}
            if last_key is not None:
                sql += ' WHERE "comment_id" > %(last)s'
                params["last"] = last_key
            sql += ' ORDER BY "comment_id" LIMIT %(chunk)s'
            rows = self._db.execute(sql, params)
            if not rows:
                break
            yield [_row(Comment, r) for r in rows]  # type: ignore[misc]
            if len(rows) < chunk_size:
                break
            last_key = str(rows[-1]["comment_id"])

    def list_root_comments(self, video_id: str) -> list[Comment]:
        rows = self._db.execute(
            'SELECT * FROM "comments" '
            'WHERE "video_id" = %(vid)s AND "parent_comment_id" IS NULL',
            {"vid": video_id},
        )
        return [_row(Comment, r) for r in rows]  # type: ignore[return-value]

    def list_replies(self, parent_comment_id: str) -> list[Comment]:
        rows = self._db.execute(
            'SELECT * FROM "comments" WHERE "parent_comment_id" = %(pid)s',
            {"pid": parent_comment_id},
        )
        return [_row(Comment, r) for r in rows]  # type: ignore[return-value]

    def list_replies_by_ids(
        self, parent_comment_ids: list[str]
    ) -> dict[str, list[Comment]]:
        result: dict[str, list[Comment]] = {pid: [] for pid in parent_comment_ids}
        if not parent_comment_ids:
            return result
        rows = self._db.execute(
            'SELECT * FROM "comments" WHERE "parent_comment_id" = ANY(%(ids)s)',
            {"ids": list(parent_comment_ids)},
        )
        for row in rows:
            pid = row.get("parent_comment_id")
            if pid in result:
                result[pid].append(_row(Comment, row))
        return result

    def save_comment_observation(self, observation: CommentObservation) -> None:
        self._save_observation(observation)

    def list_comment_observations(
        self, video_id: str | None = None, comment_id: str | None = None
    ) -> list[CommentObservation]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if comment_id is not None:
            clauses.append('"comment_id" = %(cid)s')
            params["cid"] = comment_id
        if video_id is not None:
            clauses.append(
                '"comment_id" IN (SELECT "comment_id" FROM "comments" '
                'WHERE "video_id" = %(vid)s)'
            )
            params["vid"] = video_id
        sql = f'SELECT * FROM "{self._OBS_TABLE}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += ' ORDER BY "observed_at", "seq"'
        rows = self._db.execute(sql, params)
        return [_row(CommentObservation, r) for r in rows]  # type: ignore[return-value]

    def get_latest_comment_observation(
        self, comment_id: str
    ) -> CommentObservation | None:
        row = self._db.fetchone(
            f'SELECT * FROM "{self._OBS_TABLE}" '
            'WHERE "comment_id" = %(cid)s '
            'ORDER BY "observed_at" DESC, "seq" DESC LIMIT 1',
            {"cid": comment_id},
        )
        return _row(CommentObservation, row)  # type: ignore[return-value]

    def get_latest_comment_observations(
        self, comment_ids: list[str]
    ) -> dict[str, CommentObservation]:
        if not comment_ids:
            return {}
        rows = self._db.execute(
            f'SELECT {_proj_cols(CommentObservation)} FROM "{self._OBS_TABLE}" '
            "WHERE \"comment_id\" = ANY(%(ids)s) "
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(comment_ids)},
        )
        by_id = _latest_by_id(rows, comment_ids, "comment_id")
        return {
            cid: _row(CommentObservation, row)  # type: ignore[misc]
            for cid, row in by_id.items()
        }

    def latest_comment_metrics(
        self, comment_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        if not comment_ids:
            return {}
        rows = self._db.execute(
            f'SELECT "comment_id", "like_count", "reply_count", "is_removed" '
            f'FROM "{self._OBS_TABLE}" '
            'WHERE "comment_id" = ANY(%(ids)s) '
            'ORDER BY "observed_at" DESC, "seq" DESC',
            {"ids": list(comment_ids)},
        )
        best: dict[str, dict[str, Any]] = {}
        for r in rows:
            cid = str(r["comment_id"])
            if cid not in best:
                best[cid] = {
                    "like_count": r["like_count"],
                    "reply_count": r["reply_count"],
                    "is_removed": r["is_removed"],
                }
        return best

    def explore_comment_rows(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            'SELECT "comment_id", "video_id", "author_name", "author_id", '
            '"comment_text", "published_at", "is_reply", "parent_comment_id", '
            '"root_comment_id", "is_author" FROM "comments"'
        )
        comments = [dict(r) for r in rows]
        latest = self.latest_comment_metrics([str(r["comment_id"]) for r in comments])
        return [
            {
                "comment_id": str(r["comment_id"]),
                "video_id": str(r["video_id"]),
                "author_name": r["author_name"],
                "author_id": r["author_id"],
                "comment_text": r["comment_text"],
                "published_at": r["published_at"],
                "is_reply": r["is_reply"],
                "parent_comment_id": r["parent_comment_id"],
                "root_comment_id": r["root_comment_id"],
                "is_author": r["is_author"],
                "like_count": latest.get(str(r["comment_id"]), {}).get("like_count"),
                "reply_count": latest.get(str(r["comment_id"]), {}).get("reply_count"),
                "is_removed": latest.get(str(r["comment_id"]), {}).get("is_removed"),
            }
            for r in comments
        ]


# ---------------------------------------------------------------------------
# Collection runs
# ---------------------------------------------------------------------------

class SqlCollectionRunRepository(_SqlEntityRepository, CollectionRunRepository):
    _TABLE = "collection_runs"
    _MODEL = CollectionRun
    _KEY = "run_id"

    def create_run(self, run: CollectionRun) -> None:
        self._save_run(run)

    def update_run(self, run: CollectionRun) -> None:
        self._save_run(run)

    def _save_run(self, run: CollectionRun) -> None:
        cols = headers_for(CollectionRun)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "run_id")
        self._db.execute(
            f'INSERT INTO "collection_runs" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("run_id") DO UPDATE SET ' + update,
            _params(run),
        )

    def get_run(self, run_id: str) -> CollectionRun | None:
        return self._get(run_id)  # type: ignore[return-value]

    def list_runs(self, run_type=None) -> list[CollectionRun]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if run_type is not None:
            clauses.append('"run_type" = %(rt)s')
            params["rt"] = run_type.value
        sql = 'SELECT * FROM "collection_runs"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += ' ORDER BY "started_at", "run_id"'
        rows = self._db.execute(sql, params)
        return [_row(CollectionRun, r) for r in rows]  # type: ignore[return-value]

    def list_sub_runs(self, parent_run_id: str) -> list[CollectionRun]:
        rows = self._db.execute(
            'SELECT * FROM "collection_runs" '
            'WHERE "parent_run_id" = %(pid)s ORDER BY "started_at", "run_id"',
            {"pid": parent_run_id},
        )
        return [_row(CollectionRun, r) for r in rows]  # type: ignore[return-value]

    def record_error(self, error: CollectionError) -> None:
        cols = headers_for(CollectionError)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "error_id")
        self._db.execute(
            f'INSERT INTO "collection_errors" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("error_id") DO UPDATE SET ' + update,
            _params(error),
        )

    def list_errors(self, run_id: str) -> list[CollectionError]:
        rows = self._db.execute(
            'SELECT * FROM "collection_errors" WHERE "run_id" = %(rid)s',
            {"rid": run_id},
        )
        return [_row(CollectionError, r) for r in rows]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class SqlRecommendationRepository(_SqlEntityRepository, RecommendationRepository):
    _TABLE = "recommendations"
    _MODEL = RecommendationObservation
    _KEY = "observation_id"

    def save_recommendation(
        self, observation: RecommendationObservation
    ) -> UpsertResult:
        key = observation.observation_id
        cols = headers_for(RecommendationObservation)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "observation_id")
        row = self._db.fetchone(
            f'INSERT INTO "recommendations" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("observation_id") DO UPDATE SET ' + update
            + " RETURNING (xmax = 0) AS created",
            _params(observation),
        )
        created = bool(row["created"]) if row else False
        return UpsertResult(
            entity_type=EntityType.RECOMMENDATION,
            entity_id=key,
            created=created,
        )

    def list_recommendations_for_source(
        self, source_video_id: str, run_id: str | None = None
    ) -> list[RecommendationObservation]:
        return self.list_recommendation_edges(
            source_video_id=source_video_id, run_id=run_id
        )

    def list_recommendation_edges(
        self,
        source_video_id: str | None = None,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        exclude_run_ids: list[str] | None = None,
    ) -> list[RecommendationObservation]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if source_video_id is not None:
            clauses.append('"source_video_id" = %(sv)s')
            params["sv"] = source_video_id
        if run_id is not None:
            clauses.append('"collection_run_id" = %(rid)s')
            params["rid"] = run_id
        if run_ids is not None:
            clauses.append('"collection_run_id" = ANY(%(rids)s)')
            params["rids"] = list(run_ids)
        if exclude_run_ids is not None:
            clauses.append('"collection_run_id" != ALL(%(excl)s)')
            params["excl"] = list(exclude_run_ids)
        sql = 'SELECT * FROM "recommendations"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += ' ORDER BY "seq"'
        rows = self._db.execute(sql, params)
        return [_row(RecommendationObservation, r) for r in rows]  # type: ignore[return-value]

    def list_recommendation_edges_graph(
        self, run_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        sql = (
            'SELECT "source_video_id", "recommended_video_id", "position", '
            '"collection_run_id", "title", "channel_id", "channel_name" '
            'FROM "recommendations"'
        )
        params: dict[str, Any] = {}
        if run_ids:
            sql += ' WHERE "collection_run_id" = ANY(%(rids)s)'
            params["rids"] = list(run_ids)
        sql += ' ORDER BY "seq"'
        rows = self._db.execute(sql, params)
        return [
            {
                "source_video_id": r["source_video_id"],
                "recommended_video_id": r["recommended_video_id"],
                "position": r["position"],
                "collection_run_id": r["collection_run_id"],
                "title": r["title"],
                "channel_id": r["channel_id"],
                "channel_name": r["channel_name"],
            }
            for r in rows
        ]

    def explore_recommendation_rows(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            'SELECT "observation_id", "source_video_id", "recommended_video_id", '
            '"position", "status", "channel_id", "title", "observed_at" '
            'FROM "recommendations"'
        )
        return [
            {
                "observation_id": str(r["observation_id"]),
                "source_video_id": r["source_video_id"],
                "recommended_video_id": r["recommended_video_id"],
                "position": r["position"],
                "status": r["status"],
                "channel_id": r["channel_id"],
                "title": r["title"],
                "observed_at": r["observed_at"],
            }
            for r in rows
        ]

    def list_source_video_ids(self) -> list[str]:
        rows = self._db.execute(
            'SELECT DISTINCT "source_video_id" FROM "recommendations" '
            'ORDER BY "source_video_id"'
        )
        return [str(r["source_video_id"]) for r in rows]


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

class SqlTranscriptRepository(_SqlEntityRepository, TranscriptRepository):
    _TABLE = "transcripts"
    _MODEL = TranscriptRecord
    _KEY = "transcript_id"

    def __init__(self, db: SqlDatabase, transcripts_dir: str | Path | None = None) -> None:
        super().__init__(db)
        self._transcripts_dir = (
            Path(transcripts_dir) if transcripts_dir is not None else None
        )

    def _artifact_path(self, video_id: str) -> Path:
        return self._transcripts_dir / f"{video_id}.txt"

    def write_artifact(self, video_id: str, content: str) -> Path:
        """Write transcript content to an external file and return the path."""
        path = self._artifact_path(video_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_artifact(self, video_id: str) -> str | None:
        """Read transcript content back from the external file, if present."""
        if self._transcripts_dir is None:
            return None
        path = self._artifact_path(video_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_transcript(self, record: TranscriptRecord) -> None:
        cols = headers_for(TranscriptRecord)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "transcript_id"
        )
        self._db.execute(
            f'INSERT INTO "transcripts" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("transcript_id") DO UPDATE SET ' + update,
            _params(record),
        )

    def get_transcript(self, video_id: str) -> TranscriptRecord | None:
        records = self.list_transcripts(video_id)
        return records[-1] if records else None

    def list_transcripts(
        self, video_id: str | None = None
    ) -> list[TranscriptRecord]:
        if video_id is None:
            rows = self._db.execute(
                'SELECT * FROM "transcripts" '
                'ORDER BY ("observed_at" IS NULL), "observed_at", "seq"'
            )
        else:
            rows = self._db.execute(
                'SELECT * FROM "transcripts" '
                'WHERE "video_id" = %(vid)s '
                'ORDER BY ("observed_at" IS NULL), "observed_at", "seq"',
                {"vid": video_id},
            )
        return [_row(TranscriptRecord, r) for r in rows]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Datasets (concrete repo, no ABC)
# ---------------------------------------------------------------------------

class SqlDatasetRepository:
    """PostgreSQL-backed datasets + members (no 28k chunking needed)."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def upsert_dataset(self, dataset: Dataset) -> None:
        cols = headers_for(Dataset)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "dataset_id")
        self._db.execute(
            f'INSERT INTO "datasets" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("dataset_id") DO UPDATE SET ' + update,
            _params(dataset),
        )

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        row = self._db.fetchone(
            'SELECT * FROM "datasets" WHERE "dataset_id" = %(key)s', {"key": dataset_id}
        )
        return _row(Dataset, row)  # type: ignore[return-value]

    def list_datasets(self) -> list[Dataset]:
        rows = self._db.execute('SELECT * FROM "datasets"')
        return [_row(Dataset, r) for r in rows]  # type: ignore[return-value]

    def delete_dataset(self, dataset_id: str) -> None:
        self._db.execute('DELETE FROM "datasets" WHERE "dataset_id" = %(key)s', {"key": dataset_id})
        self._db.execute(
            'DELETE FROM "dataset_members" WHERE "dataset_id" = %(key)s', {"key": dataset_id}
        )

    def save_dataset(self, dataset) -> None:
        self.upsert_dataset(dataset)

    def get_dataset_raw(self, dataset_id: str):
        return self.get_dataset(dataset_id)

    def list_datasets_raw(self):
        return self.list_datasets()

    def save_members(self, dataset_id: str, members: list[dict[str, Any]]) -> int:
        self._db.execute(
            'DELETE FROM "dataset_members" WHERE "dataset_id" = %(key)s', {"key": dataset_id}
        )
        payload = Jsonb(members)
        self._db.execute(
            'INSERT INTO "dataset_members" ("row_id", "dataset_id", "chunk_index", "member_json") '
            "VALUES (%(row)s, %(key)s, 0, %(payload)s)",
            {"row": f"{dataset_id}::0", "key": dataset_id, "payload": payload},
        )
        return 1

    def list_members(self, dataset_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            'SELECT * FROM "dataset_members" WHERE "dataset_id" = %(key)s '
            'ORDER BY "chunk_index"',
            {"key": dataset_id},
        )
        members: list[dict[str, Any]] = []
        for row in rows:
            payload = row.get("member_json")
            if payload:
                members.extend(payload)
        return members

    def dataset_member_count(self, dataset_id: str) -> int:
        return len(self.list_members(dataset_id))


# ---------------------------------------------------------------------------
# Projects / Project items
# ---------------------------------------------------------------------------

class SqlProjectRepository:
    """PostgreSQL-backed projects."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def upsert_project(self, project: Project) -> None:
        cols = headers_for(Project)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "project_id")
        self._db.execute(
            f'INSERT INTO "projects" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("project_id") DO UPDATE SET ' + update,
            _params(project),
        )

    def get_project(self, project_id: str) -> Project | None:
        row = self._db.fetchone(
            'SELECT * FROM "projects" WHERE "project_id" = %(key)s', {"key": project_id}
        )
        return _row(Project, row)  # type: ignore[return-value]

    def list_projects(self) -> list[Project]:
        rows = self._db.execute('SELECT * FROM "projects"')
        return [_row(Project, r) for r in rows]  # type: ignore[return-value]

    def save_project(self, project: Project) -> None:
        self.upsert_project(project)

    def update_project(self, project: Project) -> None:
        self.upsert_project(project)

    def delete_project(self, project_id: str) -> None:
        self._db.execute('DELETE FROM "projects" WHERE "project_id" = %(key)s', {"key": project_id})


class SqlProjectItemRepository(ProjectItemRepository):
    """PostgreSQL-backed project items."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def save_item(self, item: ProjectItem) -> None:
        cols = headers_for(ProjectItem)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "item_id")
        self._db.execute(
            f'INSERT INTO "project_items" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("item_id") DO UPDATE SET ' + update,
            _params(item),
        )

    def get_item(self, item_id: str) -> ProjectItem | None:
        row = self._db.fetchone(
            'SELECT * FROM "project_items" WHERE "item_id" = %(key)s', {"key": item_id}
        )
        return _row(ProjectItem, row)  # type: ignore[return-value]

    def list_items(self, project_id: str | None = None) -> list[ProjectItem]:
        if project_id:
            rows = self._db.execute(
                'SELECT * FROM "project_items" WHERE "project_id" = %(key)s',
                {"key": project_id},
            )
        else:
            rows = self._db.execute('SELECT * FROM "project_items"')
        return [_row(ProjectItem, r) for r in rows]  # type: ignore[return-value]

    def list_items_by_project(self, project_id: str) -> list[ProjectItem]:
        return self.list_items(project_id=project_id)

    def update_item(self, item: ProjectItem) -> None:
        self.save_item(item)

    def delete_item(self, item_id: str) -> None:
        self._db.execute('DELETE FROM "project_items" WHERE "item_id" = %(key)s', {"key": item_id})


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------

class SqlSampleRepository:
    """PostgreSQL-backed samples (member ids in a JSONB column, no chunking)."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def save(self, sample: Sample) -> Sample:
        stored = sample.model_copy(update={"overflow": False})
        cols = headers_for(Sample)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "sample_id")
        self._db.execute(
            f'INSERT INTO "samples" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("sample_id") DO UPDATE SET ' + update,
            _params(stored),
        )
        return stored

    def delete(self, sample_id: str) -> bool:
        cur = self._db.fetchone(
            'DELETE FROM "samples" WHERE "sample_id" = %(key)s RETURNING "sample_id"',
            {"key": sample_id},
        )
        return cur is not None

    def get(self, sample_id: str) -> Sample | None:
        row = self._db.fetchone(
            'SELECT * FROM "samples" WHERE "sample_id" = %(key)s', {"key": sample_id}
        )
        return _row(Sample, row)  # type: ignore[return-value]

    def list(self) -> list[Sample]:
        rows = self._db.execute('SELECT * FROM "samples"')
        return [_row(Sample, r) for r in rows]  # type: ignore[return-value]

    def list_members(self, sample_id: str) -> list[str]:
        sample = self.get(sample_id)
        return list(sample.member_ids) if sample else []


# ---------------------------------------------------------------------------
# Layer runs
# ---------------------------------------------------------------------------

class SqlLayerRunRepository(LayerRunRepository):
    """PostgreSQL-backed layer-run anchors."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    def save_layer_run(self, layer_run: LayerRun) -> None:
        cols = headers_for(LayerRun)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "layer_run_id"
        )
        self._db.execute(
            f'INSERT INTO "layer_runs" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("layer_run_id") DO UPDATE SET ' + update,
            _params(layer_run),
        )

    def get_layer_run(self, layer_run_id: str) -> LayerRun | None:
        row = self._db.fetchone(
            'SELECT * FROM "layer_runs" WHERE "layer_run_id" = %(key)s',
            {"key": layer_run_id},
        )
        return _row(LayerRun, row)  # type: ignore[return-value]

    def list_layer_runs(self) -> list[LayerRun]:
        rows = self._db.execute('SELECT * FROM "layer_runs" ORDER BY "layer_index"')
        return [_row(LayerRun, r) for r in rows]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Persisted jobs (plan J1 write-through)
# ---------------------------------------------------------------------------

class SqlJobRepository(JobRepository):
    """PostgreSQL-backed collection-job rows."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    _UPDATABLE = (
        "kind",
        "status",
        "params_json",
        "result_json",
        "message",
        "error",
        "created_at",
        "started_at",
        "finished_at",
        "updated_at",
    )

    def save_job(self, job: CollectionJob) -> None:
        cols = headers_for(CollectionJob)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in self._UPDATABLE)
        self._db.execute(
            f'INSERT INTO "collection_jobs" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("job_id") DO UPDATE SET ' + update,
            _params(job),
        )

    def get_job(self, job_id: str) -> CollectionJob | None:
        row = self._db.fetchone(
            'SELECT * FROM "collection_jobs" WHERE "job_id" = %(key)s',
            {"key": job_id},
        )
        return _row(CollectionJob, row)  # type: ignore[return-value]

    def list_jobs(
        self,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[CollectionJob]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if kind is not None:
            clauses.append('"kind" = %(kind)s')
            params["kind"] = kind
        if status is not None:
            clauses.append('"status" = %(status)s')
            params["status"] = status
        sql = 'SELECT * FROM "collection_jobs"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += ' ORDER BY "created_at" DESC NULLS LAST'
        rows = self._db.execute(sql, params)
        return [_row(CollectionJob, r) for r in rows]  # type: ignore[return-value]

    def reconcile_stale_running(self, message: str) -> int:
        row = self._db.fetchone(
            'UPDATE "collection_jobs" '
            'SET "status" = %(status)s, "error" = %(msg)s, '
            '"finished_at" = NOW(), "updated_at" = NOW() '
            'WHERE "status" IN (%(p)s, %(r)s) RETURNING "job_id"',
            {"status": "interrupted", "msg": message, "p": "pending", "r": "running"},
        )
        return 1 if row else 0


# ---------------------------------------------------------------------------
# Echo-chamber detections (echo plan §4)
# ---------------------------------------------------------------------------

class SqlEchoDetectionRepository(EchoDetectionRepository):
    """PostgreSQL-backed echo-detection rows."""

    def __init__(self, db: SqlDatabase) -> None:
        self._db = db

    _UPDATABLE = (
        "seed_video_id",
        "seed_run_id",
        "root_layer_run_id",
        "job_id",
        "status",
        "params",
        "layers",
        "score",
        "error",
        "created_at",
        "updated_at",
    )

    def save_detection(self, detection: EchoDetection) -> None:
        cols = headers_for(EchoDetection)
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f"%({c})s" for c in cols)
        update = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in self._UPDATABLE)
        self._db.execute(
            f'INSERT INTO "echo_detections" ({col_list}) VALUES ({ph}) '
            'ON CONFLICT ("detection_id") DO UPDATE SET ' + update,
            _params(detection),
        )

    def get_detection(self, detection_id: str) -> EchoDetection | None:
        row = self._db.fetchone(
            'SELECT * FROM "echo_detections" WHERE "detection_id" = %(key)s',
            {"key": detection_id},
        )
        return _row(EchoDetection, row)  # type: ignore[return-value]

    def list_detections(self) -> list[EchoDetection]:
        rows = self._db.execute(
            'SELECT * FROM "echo_detections" ORDER BY "created_at" DESC NULLS LAST'
        )
        return [_row(EchoDetection, r) for r in rows]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Container + factory
# ---------------------------------------------------------------------------

class SqlRepositories(Repositories):
    """Container of all SQL repositories sharing one database pool."""

    datasets: SqlDatasetRepository
    samples: SqlSampleRepository
    projects: SqlProjectRepository
    project_items: SqlProjectItemRepository
    layers: SqlLayerRunRepository
    jobs: SqlJobRepository
    echo_detections: SqlEchoDetectionRepository

    def __init__(self, db: SqlDatabase, transcripts_dir: str | Path | None = None) -> None:
        self._db = db
        self.channels = SqlChannelRepository(db)
        self.videos = SqlVideoRepository(db)
        self.comments = SqlCommentRepository(db)
        self.runs = SqlCollectionRunRepository(db)
        self.recommendations = SqlRecommendationRepository(db)
        self.transcripts = SqlTranscriptRepository(db, transcripts_dir)
        self.authors = SqlAuthorRepository(db)
        self.datasets = SqlDatasetRepository(db)
        self.samples = SqlSampleRepository(db)
        self.projects = SqlProjectRepository(db)
        self.project_items = SqlProjectItemRepository(db)
        self.layers = SqlLayerRunRepository(db)
        self.jobs = SqlJobRepository(db)
        self.echo_detections = SqlEchoDetectionRepository(db)

    @property
    def store(self):
        """Compatibility shim: SQL has no workbook store, but exposes the DB."""
        return self._db

    def close(self) -> None:
        self._db.close()


def build_sql_repositories(
    database_url: str | None = None,
    transcripts_dir: str | Path | None = None,
) -> SqlRepositories:
    """Build all SQL repositories against one PostgreSQL database."""
    db = SqlDatabase(database_url or DEFAULT_DATABASE_URL)
    db.create_schema()
    return SqlRepositories(db, transcripts_dir)