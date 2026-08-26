"""PostgreSQL database access for the SocialScienceResearch module.

Implements the persistence contract in ``persistence.base`` against a
PostgreSQL database using raw SQL + psycopg 3 (no ORM). ``JSONB`` columns
replace the Excel overflow sidecars entirely: there is no 32k cell limit, no
``__CELL_OVERFLOW__`` sentinel, and no boot-time ``json.load`` of a huge
sidecar.

The schema is declared here as a declarative table map and created idempotently
via ``SqlDatabase.create_schema()``.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

#: Default connection string (matches the local dev Postgres created during the
#: migration; override via ``SOCIAL_DATABASE_URL``).
DEFAULT_DATABASE_URL = "postgresql://postgres:123456@localhost:5432/social_science"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

#: Column -> SQL type for each table. ``!PK`` marks the primary key.
TABLES: dict[str, dict[str, str]] = {
    "channels": {
        "channel_id": "TEXT !PK",
        "url": "TEXT NOT NULL",
        "title": "TEXT",
        "description": "TEXT",
        "handle": "TEXT",
        "is_verified": "BOOLEAN",
        "avatar_url": "TEXT",
        "banner_url": "TEXT",
        "country": "TEXT",
        "joined_date": "DATE",
        "first_observed_run_id": "TEXT NOT NULL",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "channel_observations": {
        "observation_id": "TEXT !PK",
        "seq": "BIGSERIAL",
        "collection_run_id": "TEXT NOT NULL",
        "channel_id": "TEXT NOT NULL",
        "observed_at": "TIMESTAMPTZ NOT NULL",
        "subscriber_count": "BIGINT",
        "video_count": "BIGINT",
        "view_count": "BIGINT",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "videos": {
        "video_id": "TEXT !PK",
        "url": "TEXT NOT NULL",
        "channel_id": "TEXT",
        "title": "TEXT",
        "description": "TEXT",
        "duration": "BIGINT",
        "upload_date": "DATE",
        "upload_timestamp": "TIMESTAMPTZ",
        "tags": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "categories": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "language": "TEXT",
        "live_status": "TEXT",
        "availability": "TEXT",
        "age_limit": "BIGINT",
        "is_short": "BOOLEAN",
        "thumbnail_url": "TEXT",
        "chapters_json": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "transcript_path": "TEXT",
        "transcript_status": "TEXT",
        "transcript_lang": "TEXT",
        "first_observed_run_id": "TEXT NOT NULL",
        "recommendations_scraped": "BOOLEAN NOT NULL DEFAULT false",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "video_observations": {
        "observation_id": "TEXT !PK",
        "seq": "BIGSERIAL",
        "collection_run_id": "TEXT NOT NULL",
        "video_id": "TEXT NOT NULL",
        "observed_at": "TIMESTAMPTZ NOT NULL",
        "view_count": "BIGINT",
        "like_count": "BIGINT",
        "comment_count": "BIGINT",
        "favorite_count": "BIGINT",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "comments": {
        "comment_id": "TEXT !PK",
        "video_id": "TEXT NOT NULL",
        "author_name": "TEXT",
        "author_id": "TEXT",
        "comment_text": "TEXT",
        "published_at": "TIMESTAMPTZ",
        "is_reply": "BOOLEAN NOT NULL DEFAULT false",
        "parent_comment_id": "TEXT",
        "root_comment_id": "TEXT",
        "is_author": "BOOLEAN",
        "first_observed_run_id": "TEXT NOT NULL",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "comment_observations": {
        "observation_id": "TEXT !PK",
        "seq": "BIGSERIAL",
        "collection_run_id": "TEXT NOT NULL",
        "comment_id": "TEXT NOT NULL",
        "observed_at": "TIMESTAMPTZ NOT NULL",
        "like_count": "BIGINT",
        "reply_count": "BIGINT",
        "is_removed": "BOOLEAN",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "collection_runs": {
        "run_id": "TEXT !PK",
        "run_type": "TEXT NOT NULL",
        "target_url": "TEXT NOT NULL",
        "target_channel_id": "TEXT",
        "target_video_id": "TEXT",
        "parent_run_id": "TEXT",
        "started_at": "TIMESTAMPTZ NOT NULL",
        "finished_at": "TIMESTAMPTZ",
        "status": "TEXT NOT NULL",
        "provider": "TEXT NOT NULL",
        "provider_version": "TEXT",
        "config_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "entities_discovered": "BIGINT NOT NULL DEFAULT 0",
        "entities_succeeded": "BIGINT NOT NULL DEFAULT 0",
        "entities_existing": "BIGINT",
        "entities_failed": "BIGINT NOT NULL DEFAULT 0",
        "comments_collected": "BIGINT",
        "notes": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "name": "TEXT",
        "layer_index": "BIGINT",
        "job_id": "TEXT",
        "tags": "JSONB NOT NULL DEFAULT '[]'::jsonb",
    },
    "collection_errors": {
        "error_id": "TEXT !PK",
        "run_id": "TEXT NOT NULL",
        "entity_type": "TEXT NOT NULL",
        "entity_id": "TEXT",
        "error_type": "TEXT NOT NULL",
        "message": "TEXT NOT NULL",
        "occurred_at": "TIMESTAMPTZ NOT NULL",
        "retryable": "BOOLEAN NOT NULL DEFAULT false",
        "details": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "recommendations": {
        "observation_id": "TEXT !PK",
        "seq": "BIGSERIAL",
        "collection_run_id": "TEXT NOT NULL",
        "source_video_id": "TEXT NOT NULL",
        "recommended_video_id": "TEXT NOT NULL",
        "position": "BIGINT",
        "status": "TEXT NOT NULL",
        "channel_id": "TEXT",
        "channel_name": "TEXT",
        "title": "TEXT",
        "observed_at": "TIMESTAMPTZ",
        "layer_index": "BIGINT",
        "raw_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "transcripts": {
        "transcript_id": "TEXT !PK",
        "seq": "BIGSERIAL",
        "video_id": "TEXT NOT NULL",
        "collection_run_id": "TEXT NOT NULL",
        "path": "TEXT",
        "lang": "TEXT",
        "status": "TEXT NOT NULL",
        "message": "TEXT",
        "observed_at": "TIMESTAMPTZ",
    },
    "datasets": {
        "dataset_id": "TEXT !PK",
        "name": "TEXT NOT NULL",
        "description": "TEXT",
        "entity_type": "TEXT NOT NULL",
        "created_at": "TIMESTAMPTZ NOT NULL",
        "created_by_run_id": "TEXT",
        "source_projection": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "member_count": "BIGINT NOT NULL DEFAULT 0",
        "overflow": "BOOLEAN NOT NULL DEFAULT false",
    },
    "dataset_members": {
        "row_id": "TEXT !PK",
        "dataset_id": "TEXT NOT NULL",
        "chunk_index": "BIGINT NOT NULL",
        "member_json": "JSONB NOT NULL",
    },
    "projects": {
        "project_id": "TEXT !PK",
        "name": "TEXT NOT NULL",
        "description": "TEXT",
        "targets": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "collection_spec": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "sampling_specs": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "research_query": "JSONB",
        "variable_selection": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "notes": "TEXT",
        "config_hash": "TEXT NOT NULL",
        "created_at": "TIMESTAMPTZ NOT NULL",
        "updated_at": "TIMESTAMPTZ NOT NULL",
    },
    "project_items": {
        "item_id": "TEXT !PK",
        "project_id": "TEXT NOT NULL",
        "name": "TEXT NOT NULL",
        "description": "TEXT",
        "item_type": "TEXT NOT NULL",
        "sample_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "dataset_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "tags": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "created_at": "TIMESTAMPTZ NOT NULL",
        "updated_at": "TIMESTAMPTZ NOT NULL",
    },
    "samples": {
        "sample_id": "TEXT !PK",
        "entity_type": "TEXT NOT NULL",
        "strategy": "TEXT NOT NULL",
        "population_query_hash": "TEXT NOT NULL DEFAULT ''",
        "population_size": "BIGINT NOT NULL",
        "sample_size": "BIGINT NOT NULL",
        "seed": "BIGINT",
        "criteria_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "member_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "overflow": "BOOLEAN NOT NULL DEFAULT false",
        "created_at": "TIMESTAMPTZ NOT NULL",
        "created_by_run_id": "TEXT",
        "scope": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "filters_applied": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "labels": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "layer_runs": {
        "layer_run_id": "TEXT !PK",
        "layer_index": "BIGINT NOT NULL",
        "parent_run_id": "TEXT",
        "parent_layer_run_id": "TEXT",
        "projection": "TEXT NOT NULL DEFAULT 'video'",
        "started_at": "TIMESTAMPTZ NOT NULL",
        "finished_at": "TIMESTAMPTZ",
        "status": "TEXT NOT NULL",
        "frontier_video_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "discovered_video_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "run_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "comments_collected": "BIGINT NOT NULL DEFAULT 0",
        "summary": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "config_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
    },
    "collection_jobs": {
        "job_id": "TEXT !PK",
        "kind": "TEXT NOT NULL DEFAULT 'collect'",
        "status": "TEXT NOT NULL DEFAULT 'pending'",
        "tags": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "params_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "result_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "message": "TEXT",
        "error": "TEXT",
        "created_at": "TIMESTAMPTZ",
        "started_at": "TIMESTAMPTZ",
        "finished_at": "TIMESTAMPTZ",
        "updated_at": "TIMESTAMPTZ",
    },
    "echo_detections": {
        "detection_id": "TEXT !PK",
        "seed_video_id": "TEXT",
        "seed_run_id": "TEXT",
        "root_layer_run_id": "TEXT",
        "job_id": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'pending'",
        "params": "JSONB NOT NULL DEFAULT '{}'::jsonb",
        "layers": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "score": "JSONB",
        "error": "TEXT",
        "created_at": "TIMESTAMPTZ",
        "updated_at": "TIMESTAMPTZ",
    },
}

#: Secondary (non-unique) indexes: ``table -> [(columns...), ...]``.
INDEXES: dict[str, list[tuple[str, ...]]] = {
    "channels": [("url",)],
    "channel_observations": [("channel_id",), ("collection_run_id",)],
    "videos": [("channel_id",), ("first_observed_run_id",), ("recommendations_scraped",)],
    "video_observations": [("video_id",), ("collection_run_id",)],
    "comments": [("video_id",), ("parent_comment_id",), ("root_comment_id",)],
    "comment_observations": [("comment_id",), ("collection_run_id",)],
    "collection_runs": [("run_type",), ("started_at",), ("job_id",)],
    "collection_errors": [("run_id",)],
    "recommendations": [
        ("source_video_id",),
        ("collection_run_id",),
        ("recommended_video_id",),
    ],
    "transcripts": [("video_id",)],
    "dataset_members": [("dataset_id",)],
    "project_items": [("project_id",)],
    "samples": [("entity_type",)],
    "layer_runs": [("layer_index",), ("parent_run_id",)],
    "collection_jobs": [("status",), ("kind",), ("created_at",)],
    "echo_detections": [("status",), ("created_at",), ("job_id",)],
}

#: Unique constraints beyond the PK: ``table -> [([cols...], name), ...]``.
UNIQUE_CONSTRAINTS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "recommendations": [
        (
            ("collection_run_id", "source_video_id", "recommended_video_id"),
            "uq_recommendations_run_source_target",
        )
    ]
}


def build_schema_sql() -> str:
    """Return the full idempotent DDL (CREATE TABLE IF NOT EXISTS + indexes)."""
    statements: list[str] = []
    for table, columns in TABLES.items():
        col_defs: list[str] = []
        pk = None
        for name, col_type in columns.items():
            if col_type.endswith("!PK"):
                col_defs.append(f'"{name}" {col_type[:-3].strip()} NOT NULL')
                pk = name
            else:
                col_defs.append(f'"{name}" {col_type}')
        constraints = [f'PRIMARY KEY ("{pk}")'] if pk else []
        for cols, name in UNIQUE_CONSTRAINTS.get(table, []):
            col_list = ", ".join(f'"{c}"' for c in cols)
            constraints.append(f'CONSTRAINT "{name}" UNIQUE ({col_list})')
        body = ",\n    ".join(col_defs + constraints)
        statements.append(f'CREATE TABLE IF NOT EXISTS "{table}" (\n    {body}\n);')
    for table, indexes in INDEXES.items():
        for cols in indexes:
            suffix = "_".join(cols)
            col_list = ", ".join(f'"{c}"' for c in cols)
            statements.append(
                f'CREATE INDEX IF NOT EXISTS "ix_{table}_{suffix}" '
                f'ON "{table}" ({col_list});'
            )
    return "\n\n".join(statements)


class SqlDatabase:
    """Thread-safe PostgreSQL connection pool with JSONB helpers."""

    def __init__(self, url: str = DEFAULT_DATABASE_URL) -> None:
        self._url = url
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row},
        )

    @property
    def url(self) -> str:
        return self._url

    def create_schema(self) -> None:
        """Create all tables/indexes idempotently."""
        # Run column migrations FIRST: on an existing database the CREATE TABLE
        # statements are no-ops, so any column that backs a new index must
        # exist before the index DDL runs.
        self._migrate()
        with self._pool.connection() as conn:
            conn.execute(build_schema_sql())
            conn.commit()
        logger.info("PostgreSQL schema ensured at %s", self._url.rsplit("@", 1)[-1])

    def _migrate(self) -> None:
        """Idempotently add columns introduced after initial provisioning.

        ``CREATE TABLE IF NOT EXISTS`` cannot add a column to an existing
        table, so columns that were added later are applied here with
        ``ADD COLUMN IF NOT EXISTS``. Safe to run on every startup.
        """
        migrations: list[tuple[str, str]] = [
            (
                "videos",
                'ALTER TABLE "videos" ADD COLUMN IF NOT EXISTS '
                '"recommendations_scraped" BOOLEAN NOT NULL DEFAULT false',
            ),
            (
                "collection_runs",
                'ALTER TABLE "collection_runs" ADD COLUMN IF NOT EXISTS "job_id" TEXT',
            ),
            (
                "collection_runs",
                "ALTER TABLE \"collection_runs\" ADD COLUMN IF NOT EXISTS "
                "\"tags\" JSONB NOT NULL DEFAULT '[]'::jsonb",
            ),
            (
                "collection_jobs",
                "ALTER TABLE \"collection_jobs\" ADD COLUMN IF NOT EXISTS "
                "\"tags\" JSONB NOT NULL DEFAULT '[]'::jsonb",
            ),
        ]
        with self._pool.connection() as conn:
            for table, sql in migrations:
                try:
                    conn.execute(sql)
                except Exception as exc:  # noqa: BLE001 - table may not exist yet
                    logger.warning("Column migration for %s failed: %s", table, exc)
            conn.commit()

    def execute(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a statement and return any result rows (read/write both)."""
        with self._pool.connection() as conn:
            cur = conn.execute(sql, params or {})
            if cur.description is not None:
                return cur.fetchall()
            conn.commit()
            return []

    def fetchone(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            cur = conn.execute(sql, params or {})
            row = cur.fetchone()
            conn.commit()
            return row

    def executemany(
        self, sql: str, rows: list[dict[str, Any]]
    ) -> None:
        """Bulk-insert many rows in one transaction (for imports)."""
        if not rows:
            return
        with self._pool.connection() as conn:
            conn.executemany(sql, rows)
            conn.commit()

    def close(self) -> None:
        self._pool.close()

    def __enter__(self) -> "SqlDatabase":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()