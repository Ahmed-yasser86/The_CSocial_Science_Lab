"""API + service tests for the session-context endpoints.

Exercises ``GET``/``PUT /session/context`` (default nulls, absent-vs-null
field semantics, 404 on unknown ids) and the file-backed persistence of
:class:`SessionContextService` across instances and corrupt files.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.dataset_models import Dataset, Project
from SocialScienceResearch.domain.session_models import SessionContextPatch
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.session_service import SessionContextService

PREFIX = "/api/v1/social-science"

T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="session"),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="session")
    )
    repos.projects.save_project(
        Project(
            project_id="proj_1",
            name="Project One",
            config_hash="h" * 16,
            created_at=T0,
            updated_at=T0,
        )
    )
    repos.datasets.save_dataset(
        Dataset(
            dataset_id="ds_1",
            name="Dataset One",
            entity_type="video",
            created_at=T0,
        )
    )
    repos.store.close()


@pytest.fixture
def client(tmp_path):
    _seed(tmp_path)
    with TestClient(create_app(_settings(tmp_path))) as test_client:
        yield test_client


def test_get_defaults_to_nulls(client) -> None:
    resp = client.get(f"{PREFIX}/session/context")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_project_id"] is None
    assert body["active_dataset_id"] is None
    assert body["updated_at"]


def test_put_sets_both_ids(client) -> None:
    resp = client.put(
        f"{PREFIX}/session/context",
        json={"active_project_id": "proj_1", "active_dataset_id": "ds_1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_project_id"] == "proj_1"
    assert body["active_dataset_id"] == "ds_1"
    assert body["updated_at"]
    assert client.get(f"{PREFIX}/session/context").json() == body


def test_put_absent_field_leaves_other_unchanged(client) -> None:
    client.put(
        f"{PREFIX}/session/context",
        json={"active_project_id": "proj_1", "active_dataset_id": "ds_1"},
    )
    resp = client.put(f"{PREFIX}/session/context", json={"active_dataset_id": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_project_id"] == "proj_1"
    assert body["active_dataset_id"] is None


def test_put_null_clears_one_field(client) -> None:
    client.put(
        f"{PREFIX}/session/context",
        json={"active_project_id": "proj_1", "active_dataset_id": "ds_1"},
    )
    resp = client.put(f"{PREFIX}/session/context", json={"active_project_id": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_project_id"] is None
    assert body["active_dataset_id"] == "ds_1"


def test_put_unknown_project_404(client) -> None:
    resp = client.put(f"{PREFIX}/session/context", json={"active_project_id": "missing"})
    assert resp.status_code == 404


def test_put_unknown_dataset_404(client) -> None:
    resp = client.put(f"{PREFIX}/session/context", json={"active_dataset_id": "missing"})
    assert resp.status_code == 404


def test_persistence_across_service_instances(tmp_path) -> None:
    first = SessionContextService(settings=_settings(tmp_path))
    first.update(SessionContextPatch(active_project_id="p_any"))
    second = SessionContextService(settings=_settings(tmp_path))
    context = second.load()
    assert context.active_project_id == "p_any"
    assert context.active_dataset_id is None


def test_corrupt_file_falls_back_to_defaults(tmp_path) -> None:
    service = SessionContextService(settings=_settings(tmp_path))
    service.update(SessionContextPatch(active_dataset_id="d_any"))
    service._path.write_text("{not json", encoding="utf-8")
    context = SessionContextService(settings=_settings(tmp_path)).load()
    assert context.active_project_id is None
    assert context.active_dataset_id is None
