"""API tests for ``POST /network/merge`` + ``POST /network/export-to-project``.

Uses the dedicated test PostgreSQL database (``social_science_test`` by
default) exactly like ``test_sql_backend.py`` - never the live
``social_science`` database. Override via ``SOCIAL_TEST_DATABASE_URL``.

Seeded network across two runs (same shape as the Excel service suite):

* ``nm_r1``: a single reciprocated pair ``a <-> b`` (2 edges, 2 nodes);
* ``nm_r2``: ``a2->b2, a2->c2, b2->c2, c2->a2, d2->a2`` (5 edges, 4 nodes).

Whole network: 6 nodes, 7 edges in two weakly-connected components. A Project
``p_netmerge`` exists for the export-to-project tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.dataset_models import Project
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.layer_models import LayerRun
from SocialScienceResearch.domain.models import (
    Channel,
    CollectionRun,
    RecommendationObservation,
    Video,
)
from SocialScienceResearch.persistence.sql.database import SqlDatabase
from SocialScienceResearch.persistence.sql.repositories import build_sql_repositories
from SocialScienceResearch.utils.idgen import utcnow

TEST_DATABASE_URL = os.environ.get(
    "SOCIAL_TEST_DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/social_science_test",
)

PREFIX = "/api/v1/social-science"

_ALL_TABLES = [
    "channels",
    "channel_observations",
    "videos",
    "video_observations",
    "comments",
    "comment_observations",
    "collection_runs",
    "collection_errors",
    "recommendations",
    "transcripts",
    "datasets",
    "dataset_members",
    "projects",
    "project_items",
    "samples",
    "layer_runs",
]


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    db = SqlDatabase(TEST_DATABASE_URL)
    try:
        db.create_schema()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_db():
    db = SqlDatabase(TEST_DATABASE_URL)
    try:
        for table in _ALL_TABLES:
            db.execute(f'TRUNCATE TABLE "{table}" CASCADE')
    finally:
        db.close()
    yield


@pytest.fixture
def settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="netmerge_test",
            backend="sql",
            database_url=TEST_DATABASE_URL,
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed_network(repos) -> None:
    """Seed the deterministic 2-run network + a project for the exports."""
    for run_id in ("nm_r1", "nm_r2"):
        repos.runs.create_run(
            CollectionRun(
                run_id=run_id,
                run_type=RunType.VIDEO,
                target_url=f"https://www.youtube.com/watch?v={run_id}",
                started_at=utcnow(),
                status=CollectionStatus.SUCCESS,
            )
        )
    edges = [
        ("nm_obs_1", "nm_r1", "a", "b", 0, "UC1", "T a->b"),
        ("nm_obs_2", "nm_r1", "b", "a", 1, "UC1", "T b->a"),
        ("nm_obs_3", "nm_r2", "a2", "b2", 0, "UC2", "T a2->b2"),
        ("nm_obs_4", "nm_r2", "a2", "c2", 1, "UC3", "T a2->c2"),
        ("nm_obs_5", "nm_r2", "b2", "c2", 0, "UC3", "T b2->c2"),
        ("nm_obs_6", "nm_r2", "c2", "a2", 2, "UC2", "T c2->a2"),
        ("nm_obs_7", "nm_r2", "d2", "a2", 3, "UC2", "T d2->a2"),
    ]
    for obs_id, run_id, source, target, position, channel_id, title in edges:
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=obs_id,
                collection_run_id=run_id,
                source_video_id=source,
                recommended_video_id=target,
                position=position,
                status=RecommendationStatus.OBSERVED,
                channel_id=channel_id,
                title=title,
            )
        )
    for video_id, channel_id in (
        ("a", "UC1"),
        ("b", "UC1"),
        ("a2", "UC2"),
        ("b2", "UC3"),
        ("c2", "UC3"),
        ("d2", "UC2"),
    ):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id=channel_id,
                title=f"Title {video_id}",
                first_observed_run_id="nm_r1",
            )
        )
    for channel_id in ("UC1", "UC2", "UC3"):
        repos.channels.upsert_channel(
            Channel(
                channel_id=channel_id,
                url=f"https://www.youtube.com/channel/{channel_id}",
                title=f"Channel {channel_id}",
                first_observed_run_id="nm_r1",
            )
        )
    repos.projects.save_project(
        Project(
            project_id="p_netmerge",
            name="Network merge project",
            config_hash="hash",
            targets=[{"kind": "channel", "url": "https://y/@netmerge"}],
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )


def _seed_expansion(action_id: str, *, run_ids: list[str]) -> None:
    """Persist a network-expansion anchor resolved via ``action_id``."""
    repos = build_sql_repositories(TEST_DATABASE_URL)
    repos.layers.save_layer_run(
        LayerRun(
            layer_run_id=action_id,
            layer_index=0,
            projection="video",
            started_at=utcnow(),
            status=CollectionStatus.SUCCESS,
            frontier_video_ids=["a"],
            discovered_video_ids=[],
            run_ids=run_ids,
            config_json={"expansion": {"kind": "all", "project_id": "p_netmerge"}},
        )
    )
    repos.close()


@pytest.fixture
def client(settings):
    repos = build_sql_repositories(TEST_DATABASE_URL)
    _seed_network(repos)
    repos.close()

    app = create_app(settings=settings)
    with TestClient(app) as test_client:
        yield test_client


def _artifact_path(body: dict) -> Path:
    marker = "Artifact file: "
    assert marker in body["description"]
    return Path(body["description"].split(marker)[-1].strip())


# ---------------------------------------------------------------------------
# POST /network/merge
# ---------------------------------------------------------------------------
def test_merge_two_run_scopes_overlap(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={
            "scope_a": {"run_id": "nm_r1"},
            "scope_b": {"run_id": "nm_r2"},
            "top_n": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_a"] == {"run_id": "nm_r1", "run_ids": [], "video_ids": []}
    assert body["scope_b"]["run_id"] == "nm_r2"
    assert body["overlap"]["scope_a_node_count"] == 2
    assert body["overlap"]["scope_b_node_count"] == 4
    assert body["overlap"]["shared_node_count"] == 0
    assert body["overlap"]["union_node_count"] == 6
    assert body["overlap"]["union_edge_count"] == 7
    assert body["overlap"]["edges_only_in_b"] == 5
    assert body["overlap"]["jaccard_node_overlap"] == 0.0
    assert body["overlap"]["jaccard_edge_overlap"] == 0.0
    assert body["merged"]["node_count"] == 6
    assert body["merged"]["edge_count"] == 7
    assert body["node_count"] == 6
    assert body["edge_count"] == 7
    assert len(body["nodes"]) == 6
    assert len(body["edges"]) == 7
    top = body["merged"]["top_degree_nodes"][0]
    assert top["video_id"] == "a2"
    assert top["title"] == "Title a2"
    assert top["total_degree"] == 4


def test_merge_same_scope_full_overlap(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={"scope_a": {"run_id": "nm_r1"}, "scope_b": {"run_id": "nm_r1"}},
    )
    body = resp.json()
    assert body["overlap"]["shared_node_count"] == 2
    assert body["overlap"]["shared_edge_count"] == 2
    assert body["overlap"]["union_edge_count"] == 2
    assert body["overlap"]["jaccard_node_overlap"] == 1.0
    assert body["overlap"]["jaccard_edge_overlap"] == 1.0
    assert body["edge_count"] == 2


def test_merge_whole_network_vs_run_partial_overlap(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={"scope_a": {}, "scope_b": {"run_id": "nm_r1"}},
    )
    body = resp.json()
    assert body["overlap"]["union_edge_count"] == 7
    assert body["overlap"]["shared_edge_count"] == 2
    assert body["overlap"]["nodes_only_in_b"] == 0
    assert body["overlap"]["jaccard_edge_overlap"] == pytest.approx(2 / 7)
    assert body["merged"]["edge_count"] == 7


def test_merge_by_action_id_scope(client):
    _seed_expansion("nm_action_r1", run_ids=["nm_r1"])
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={
            "scope_a": {"action_id": "nm_action_r1"},
            "scope_b": {"run_id": "nm_r2"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_a"]["run_ids"] == ["nm_r1"]
    assert body["overlap"]["scope_a_edge_count"] == 2
    assert body["overlap"]["scope_b_edge_count"] == 5
    assert body["overlap"]["union_edge_count"] == 7


def test_merge_unknown_action_is_400(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={
            "scope_a": {"action_id": "nm_missing"},
            "scope_b": {"run_id": "nm_r2"},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_merge_rejects_both_empty_scopes(client):
    resp = client.post(
        f"{PREFIX}/network/merge", json={"scope_a": {}, "scope_b": {}}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_merge_rejects_unknown_body_fields(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={
            "scope_a": {"run_id": "nm_r1"},
            "scope_b": {"run_id": "nm_r2"},
            "bogus": 1,
        },
    )
    assert resp.status_code == 422


def test_merge_rejects_extra_scope_fields(client):
    resp = client.post(
        f"{PREFIX}/network/merge",
        json={"scope_a": {"run_id": "nm_r1", "nonsense": True}, "scope_b": {}},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /network/merge/options
# ---------------------------------------------------------------------------
def test_merge_options_lists_runs_and_expansions(client):
    _seed_expansion("nm_action_opt", run_ids=["nm_r1"])
    resp = client.get(f"{PREFIX}/network/merge/options")
    assert resp.status_code == 200
    body = resp.json()
    assert {r["run_id"] for r in body["runs"]} == {"nm_r1", "nm_r2"}
    assert body["expansions"][0]["action_id"] == "nm_action_opt"
    assert body["expansions"][0]["run_ids"] == ["nm_r1"]
    assert body["expansions"][0]["kind"] == "all"


# ---------------------------------------------------------------------------
# POST /network/export-to-project
# ---------------------------------------------------------------------------
def test_export_to_project_whole_network_graphml(client, settings):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={"project_id": "p_netmerge", "format": "graphml"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == "p_netmerge"
    assert body["item_type"] == "mixed"
    assert "network_export" in body["tags"]
    assert "format:graphml" in body["tags"]
    assert "scope:all" in body["tags"]
    assert body["name"].startswith("Network export")
    path = _artifact_path(body)
    assert path.exists()
    assert path.parent == Path(settings.repository.data_dir) / "network_exports"
    assert "<graphml" in path.read_text(encoding="utf-8")


def test_export_to_project_scoped_csv_labels_and_file(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={
            "project_id": "p_netmerge",
            "format": "csv",
            "run_id": "nm_r2",
            "name": "Run 2 export",
            "description": "Custom note",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Run 2 export"
    assert "Custom note" in body["description"]
    assert any(t.startswith("run_id:") for t in body["tags"])
    path = _artifact_path(body)
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 6  # header + the 5 nm_r2 edges
    assert lines[0] == "source,target,weight,relationship_type"
    # Each data line is exactly 4 fields; nm_r2 nodes appear as endpoints.
    assert all(len(line.split(",")) == 4 for line in lines[1:])
    assert any("a2" in line for line in lines[1:])


def test_export_to_project_by_action_scope_edgelist(client):
    _seed_expansion("nm_action_exp", run_ids=["nm_r2"])
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={
            "project_id": "p_netmerge",
            "format": "edgelist",
            "action_id": "nm_action_exp",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(t.startswith("action_id:") for t in body["tags"])
    path = _artifact_path(body)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 5  # only the nm_r2 edges of the action's runs


def test_export_to_project_video_ego_scope(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={
            "project_id": "p_netmerge",
            "format": "edgelist",
            "video_ids": ["a"],
        },
    )
    body = resp.json()
    path = _artifact_path(body)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 2  # a->b and b->a (ego edges touching 'a')


def test_export_to_project_rejects_unknown_format(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={"project_id": "p_netmerge", "format": "dot"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_export_to_project_unknown_project(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={"project_id": "p_missing", "format": "graphml"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_export_to_project_unknown_action(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={"project_id": "p_netmerge", "action_id": "nm_missing"},
    )
    assert resp.status_code == 400


def test_export_to_project_rejects_extra_fields(client):
    resp = client.post(
        f"{PREFIX}/network/export-to-project",
        json={"project_id": "p_netmerge", "extra": "nope"},
    )
    assert resp.status_code == 422
