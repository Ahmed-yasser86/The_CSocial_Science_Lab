"""API tests for the workspace endpoints + workspace-aware session context.

Uses the dedicated SQL test server (``SOCIAL_TEST_DATABASE_URL``) so created
workspaces get real sibling databases that are dropped again afterwards.
Covers:

* ``GET/POST /workspaces`` + ``GET/PATCH /workspaces/{id}`` (Legacy present,
  renamable, idempotent registration across app restarts);
* session round-trip including ``active_workspace_id`` (activate -> requests
  routed to the fresh empty DB; deactivate -> Legacy corpus visible again);
* 404 validation for unknown workspace ids;
* absent-vs-null patch semantics preserved for project/dataset fields.
"""

from __future__ import annotations

import os
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import CollectionRun
from SocialScienceResearch.persistence.sql.database import SqlDatabase
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"

TEST_DATABASE_URL = os.environ.get(
    "SOCIAL_TEST_DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/social_science_test",
)


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="ws_api",
            backend="sql",
            database_url=TEST_DATABASE_URL,
        ),
        api=ApiSettings(prefix=PREFIX),
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
def client(tmp_path):
    """TestClient over an isolated root; drops provisioned DBs on teardown."""
    settings = _settings(tmp_path)
    from SocialScienceResearch.services.workspace_service import WorkspaceService

    service = WorkspaceService(settings)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
    test_client.close()
    for workspace in service.list_workspaces():
        if not workspace.is_legacy:
            _drop_database(workspace.database_url)


def _seed_legacy_run() -> None:
    db = SqlDatabase(TEST_DATABASE_URL)
    try:
        db.execute(
            """
            INSERT INTO collection_runs (
                run_id, run_type, target_url, started_at, status, provider
            ) VALUES (
                'run_ws_api_legacy', 'channel',
                'https://www.youtube.com/@wsapi', %(started_at)s, 'success', 'test'
            )
            ON CONFLICT (run_id) DO NOTHING
            """,
            {"started_at": utcnow()},
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------


def test_list_workspaces_includes_active_legacy(client) -> None:
    resp = client.get(f"{PREFIX}/workspaces")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    legacy = [w for w in items if w["is_legacy"]]
    assert len(legacy) == 1
    assert legacy[0]["name"] == "Legacy"
    assert legacy[0]["active"] is True
    assert "database_url" not in legacy[0] and "data_dir" not in legacy[0]
    assert set(legacy[0]["stats"]) >= {
        "runs", "videos", "channels", "comments", "datasets"
    }


def test_create_get_patch_roundtrip(client) -> None:
    created = client.post(
        f"{PREFIX}/workspaces",
        json={"name": "Climate discourse", "research_topic": "climate"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["workspace_id"].startswith("ws_")
    assert body["active"] is False  # creation does NOT auto-activate
    assert body["stats"]["runs"] == 0

    fetched = client.get(f"{PREFIX}/workspaces/{body['workspace_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Climate discourse"

    patched = client.patch(
        f"{PREFIX}/workspaces/{body['workspace_id']}",
        json={"name": "Climate pilot"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Climate pilot"
    assert patched.json()["research_topic"] == "climate"  # absent unchanged

    missing = client.get(f"{PREFIX}/workspaces/ws_missing")
    assert missing.status_code == 404

    invalid = client.post(f"{PREFIX}/workspaces", json={"name": ""})
    assert invalid.status_code == 422


def test_legacy_rename_via_patch_and_restart_idempotency(tmp_path) -> None:
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as first:
        renamed = first.patch(
            f"{PREFIX}/workspaces/ws_legacy", json={"name": "YouTube pilot"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["is_legacy"] is True
        before = first.get(f"{PREFIX}/workspaces").json()

    # A second app instance over the SAME data dir must not re-register or
    # reset anything (idempotent bootstrap).
    with TestClient(create_app(settings)) as second:
        after = second.get(f"{PREFIX}/workspaces").json()
    assert [w["workspace_id"] for w in after] == [
        w["workspace_id"] for w in before
    ]
    assert [w["name"] for w in after] == [w["name"] for w in before]


# ---------------------------------------------------------------------------
# Session routing through workspaces
# ---------------------------------------------------------------------------


def test_session_round_trip_routes_to_active_workspace(client) -> None:
    _seed_legacy_run()

    seeded = client.get(f"{PREFIX}/runs")
    assert seeded.status_code == 200
    assert any(
        run["run_id"] == "run_ws_api_legacy" for run in seeded.json()["items"]
    )

    created = client.post(
        f"{PREFIX}/workspaces", json={"name": "Isolation room"}
    ).json()

    activated = client.put(
        f"{PREFIX}/session/context",
        json={"active_workspace_id": created["workspace_id"]},
    )
    assert activated.status_code == 200
    assert activated.json()["active_workspace_id"] == created["workspace_id"]

    # Requests are now routed to the fresh, empty workspace database...
    isolated = client.get(f"{PREFIX}/runs")
    assert isolated.status_code == 200
    assert isolated.json()["items"] == []
    assert isolated.json()["total"] == 0

    # ...and the pointer survives a reload (server-side state).
    reread = client.get(f"{PREFIX}/session/context").json()
    assert reread["active_workspace_id"] == created["workspace_id"]

    # Explicit null clears the pointer; per-workspace session files persist.
    deactivated = client.put(
        f"{PREFIX}/session/context", json={"active_workspace_id": None}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active_workspace_id"] is None

    restored = client.get(f"{PREFIX}/runs").json()
    assert any(
        run["run_id"] == "run_ws_api_legacy" for run in restored["items"]
    )


def test_put_unknown_workspace_404(client) -> None:
    resp = client.put(
        f"{PREFIX}/session/context", json={"active_workspace_id": "ws_missing"}
    )
    assert resp.status_code == 404


def test_session_project_fields_absent_vs_null_preserved(client) -> None:
    first = client.put(f"{PREFIX}/session/context", json={"active_dataset_id": None})
    assert first.status_code == 200
    # Absent workspace field leaves the pointer untouched (bootstrap points
    # it at Legacy).
    context = client.get(f"{PREFIX}/session/context").json()
    assert context["active_workspace_id"] == "ws_legacy"
    # Absent-vs-null semantics: the dataset field was explicitly cleared.
    assert context["active_dataset_id"] is None
