"""Workspace control-plane tests (plan phase W0/W2).

Covers:

* Legacy bootstrap-on-first-run, idempotent across restarts (nothing deleted);
* workspace creation provisions a NEW PostgreSQL database (sibling of the
  configured database URL) with the full idempotent schema + dedicated
  data dir;
* rename/patch semantics and immutability of ``is_legacy``;
* activation pointer + last-opened touch + class-level cache clearing;
* dual-database isolation parity: rows written through repos A are invisible
  through repos B for every entity family.

SQL tests use the dedicated test server (``SOCIAL_TEST_DATABASE_URL``, same
convention as ``test_sql_backend.py``); each created workspace database is
dropped again in teardown so the suite is repeatable.
"""

from __future__ import annotations

import json
import os
import urllib.parse

import pytest

from SocialScienceResearch.config.settings import (
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import Channel, CollectionRun
from SocialScienceResearch.persistence.sql.database import SqlDatabase
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapService,
)
from SocialScienceResearch.services.recommendation_graph_service import (
    RecommendationGraphService,
)
from SocialScienceResearch.services.workspace_service import WorkspaceService
from SocialScienceResearch.utils.idgen import utcnow

TEST_DATABASE_URL = os.environ.get(
    "SOCIAL_TEST_DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/social_science_test",
)


def _sql_settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="ws_test",
            backend="sql",
            database_url=TEST_DATABASE_URL,
        )
    )


def _excel_settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="ws_test",
            backend="excel",
            database_url=TEST_DATABASE_URL,
        )
    )


def _drop_database(database_url: str) -> None:
    parts = urllib.parse.urlsplit(database_url)
    admin_url = urllib.parse.urlunsplit(parts._replace(path="/postgres"))
    db_name = parts.path.lstrip("/")
    import psycopg

    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (db_name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


@pytest.fixture
def sql_service(tmp_path):
    """WorkspaceService over a temp root + the dedicated SQL test server."""
    service = WorkspaceService(_sql_settings(tmp_path))
    service.bootstrap()  # production wiring calls this at startup
    yield service
    for workspace in service.list_workspaces():
        if workspace.is_legacy:
            continue
        _drop_database(workspace.database_url)


# ---------------------------------------------------------------------------
# Legacy bootstrap (idempotent; nothing deleted)
# ---------------------------------------------------------------------------


def test_legacy_registered_on_first_run(tmp_path) -> None:
    service = WorkspaceService(_excel_settings(tmp_path))
    legacy = service.bootstrap()
    assert legacy is not None
    assert legacy.is_legacy is True
    assert legacy.name == "Legacy"
    # Captures CURRENT settings values verbatim: nothing moves or copies.
    assert legacy.database_url == TEST_DATABASE_URL
    assert legacy.data_dir == str(tmp_path)
    assert service.active_workspace_id() == legacy.workspace_id


def test_legacy_bootstrap_is_idempotent(tmp_path) -> None:
    service = WorkspaceService(_excel_settings(tmp_path))
    first = service.bootstrap()
    registry_before = json.loads(service.registry_path.read_text(encoding="utf-8"))
    second = service.bootstrap()
    assert second is None
    assert service.ensure_legacy_registered() is True
    registry_after = json.loads(service.registry_path.read_text(encoding="utf-8"))
    assert registry_after == registry_before
    assert len(service.list_workspaces()) == 1
    assert first is not None


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


def test_create_provisions_fresh_database_and_data_dir(sql_service) -> None:
    workspace = sql_service.create("Alpha", research_topic="climate discourse")
    assert workspace.workspace_id.startswith("ws_")
    assert workspace.is_legacy is False
    assert workspace.data_dir.startswith(str(sql_service.workspaces_root))
    assert os.path.isdir(workspace.data_dir)

    base_db = TEST_DATABASE_URL.rsplit("/", 1)[1]
    assert workspace.database_url.endswith(f"/{base_db}__{workspace.workspace_id}")

    # The fresh database has the full application schema.
    db = SqlDatabase(workspace.database_url)
    try:
        rows = db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        names = {row["table_name"] for row in rows}
        # ...and it is empty.
        assert db.execute("SELECT count(*) AS n FROM videos")[0]["n"] == 0
    finally:
        db.close()
    assert {"channels", "videos", "comments", "collection_runs", "datasets"} <= names


def test_get_list_and_missing_keyerror(sql_service) -> None:
    created = sql_service.create("Alpha")
    assert sql_service.get(created.workspace_id).name == "Alpha"
    names = {w.name for w in sql_service.list_workspaces()}
    assert {"Legacy", "Alpha"} <= names
    with pytest.raises(KeyError):
        sql_service.get("ws_missing")


def test_rename_patch_semantics(sql_service) -> None:
    workspace = sql_service.create("Alpha", research_topic="topic")
    updated = sql_service.update(
        workspace.workspace_id, {"name": "Pilot 2026"}
    )
    assert updated.name == "Pilot 2026"
    assert updated.research_topic == "topic"  # absent field unchanged
    # is_legacy is not a patchable field - silently ignored by design.
    legacy = next(w for w in sql_service.list_workspaces() if w.is_legacy)
    renamed = sql_service.update(legacy.workspace_id, {"name": "YouTube pilot"})
    assert renamed.name == "YouTube pilot"
    assert renamed.is_legacy is True
    with pytest.raises(KeyError):
        sql_service.update("ws_missing", {"name": "X"})


def test_activation_updates_pointer_touches_last_opened_clears_caches(
    sql_service,
) -> None:
    workspace = sql_service.create("Alpha")

    RecommendationGraphService._graph_cache[(1, True, ())] = (
        utcnow().timestamp(),
        None,
    )  # noqa: SLF001 - poisoned on purpose
    CommenterOverlapService._overlap_cache[("poison",)] = (
        utcnow().timestamp(),
        None,
    )  # noqa: SLF001

    before = workspace.last_opened_at
    import time

    time.sleep(0.02)  # ensure the touch lands on a later timestamp
    activated = sql_service.activate(workspace.workspace_id)
    assert sql_service.active_workspace_id() == workspace.workspace_id
    # Entering a workspace bumps ITS last_opened_at (chooser card ordering).
    assert activated.last_opened_at > before
    assert not RecommendationGraphService._graph_cache  # noqa: SLF001
    assert not CommenterOverlapService._overlap_cache  # noqa: SLF001

    sql_service.deactivate()
    assert sql_service.active_workspace_id() is None
    assert sql_service.get(workspace.workspace_id) is not None  # data intact


# ---------------------------------------------------------------------------
# Isolation parity (dual databases)
# ---------------------------------------------------------------------------


def _seed(repos, run_id: str, channel_id: str) -> None:
    repos.runs.create_run(
        CollectionRun(
            run_id=run_id,
            run_type=RunType.CHANNEL,
            target_url=f"https://www.youtube.com/@{channel_id}",
            target_channel_id=channel_id,
            started_at=utcnow(),
            status="success",
        )
    )
    repos.channels.upsert_channel(
        Channel(
            channel_id=channel_id,
            url=f"https://www.youtube.com/channel/{channel_id}",
            title="Isolation Channel",
            first_observed_run_id=run_id,
        )
    )


_ALL_ENTITY_LISTS = (
    lambda r: r.runs.list_runs(),
    lambda r: r.videos.list_videos(),
    lambda r: r.channels.list_channels(),
    lambda r: r.comments.list_comments(),
    lambda r: r.recommendations.list_recommendation_edges(),
    lambda r: r.datasets.list_datasets(),
    lambda r: r.projects.list_projects(),
    lambda r: r.samples.list(),
    lambda r: r.layers.list_layer_runs(),
)


def test_write_in_workspace_a_invisible_via_workspace_b_repos(sql_service) -> None:
    ws_a = sql_service.create("Alpha")
    ws_b = sql_service.create("Beta")

    repos_a = sql_service.repository_settings(ws_a)
    from SocialScienceResearch.persistence.factory import build_repositories

    container_a = build_repositories(repos_a)
    try:
        _seed(container_a, "run_iso_a", "UCiso000000000000000000a")
    finally:
        container_a.store.close()

    # Every entity family is empty through B's independent binding...
    container_b = build_repositories(sql_service.repository_settings(ws_b))
    try:
        for fetch in _ALL_ENTITY_LISTS:
            assert fetch(container_b) == []
    finally:
        container_b.store.close()

    # ...and fully intact through A's own binding.
    again_a = build_repositories(repos_a)
    try:
        assert len(again_a.runs.list_runs()) == 1
        assert len(again_a.channels.list_channels()) == 1
    finally:
        again_a.store.close()


def test_stats_are_per_workspace(sql_service) -> None:
    ws_a = sql_service.create("Alpha")
    ws_b = sql_service.create("Beta")
    from SocialScienceResearch.persistence.factory import build_repositories

    container = build_repositories(sql_service.repository_settings(ws_a))
    try:
        _seed(container, "run_stats_a", "UCstats00000000000000000a")
    finally:
        container.store.close()

    stats_a = sql_service.stats(ws_a)
    assert stats_a.runs == 1
    assert stats_a.channels == 1
    stats_b = sql_service.stats(ws_b)
    assert stats_b.runs == 0
    assert stats_b.channels == 0
