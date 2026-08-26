"""API tests for the ``job_ids`` filter on ``GET /network/graph`` and
``GET /network/edges`` (Excel-backed, deterministic, no network).

Two jobs each own one run of edges:

* ``job_a`` -> run ``jf_r1``: ``a->b``, ``b->c``
* ``job_b`` -> run ``jf_r2``: ``d->e``
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.models import CollectionRun, RecommendationObservation
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="graph_jobs"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="graph_jobs")
    )
    for run_id, job_id in (("jf_r1", "job_a"), ("jf_r2", "job_b")):
        repos.runs.create_run(
            CollectionRun(
                run_id=run_id,
                run_type=RunType.VIDEO,
                target_url=f"https://www.youtube.com/watch?v={run_id}",
                started_at=utcnow(),
                status=CollectionStatus.SUCCESS,
                job_id=job_id,
            )
        )
    edges = [
        ("jf_obs_1", "jf_r1", "a", "b", 0),
        ("jf_obs_2", "jf_r1", "b", "c", 0),
        ("jf_obs_3", "jf_r2", "d", "e", 0),
    ]
    for obs_id, run_id, source, target, position in edges:
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=obs_id,
                collection_run_id=run_id,
                source_video_id=source,
                recommended_video_id=target,
                position=position,
                status=RecommendationStatus.OBSERVED,
            )
        )
    repos.store.close()


def _client(tmp_path):
    return TestClient(create_app(_settings(tmp_path)))


def test_graph_job_ids_filters_to_union_of_child_runs(tmp_path) -> None:
    _seed(tmp_path)
    client = _client(tmp_path)

    resp = client.get(f"{PREFIX}/network/graph", params={"job_ids": "job_a"})
    assert resp.status_code == 200
    nodes = {n["video_id"] for n in resp.json()["nodes"]}
    assert nodes == {"a", "b", "c"}

    # Multiple jobs -> union of their child runs.
    both = client.get(f"{PREFIX}/network/graph", params={"job_ids": "job_a,job_b"})
    assert both.status_code == 200
    assert {n["video_id"] for n in both.json()["nodes"]} == {"a", "b", "c", "d", "e"}

    # Unknown job id -> empty slice (never silently "all runs").
    empty = client.get(f"{PREFIX}/network/graph", params={"job_ids": "job_nope"})
    assert empty.status_code == 200
    assert empty.json()["node_count"] == 0


def test_graph_job_ids_intersects_with_run_scope(tmp_path) -> None:
    """AND semantics: a run scope outside the job's runs yields an EMPTY
    slice instead of widening to either scope alone."""
    _seed(tmp_path)
    client = _client(tmp_path)
    resp = client.get(
        f"{PREFIX}/network/graph",
        params={"run_id": "jf_r2", "job_ids": "job_a"},
    )
    assert resp.status_code == 200
    assert resp.json()["node_count"] == 0

    inside = client.get(
        f"{PREFIX}/network/graph",
        params={"run_id": "jf_r1", "job_ids": "job_a"},
    )
    assert inside.status_code == 200
    assert {n["video_id"] for n in inside.json()["nodes"]} == {"a", "b", "c"}


def test_edges_job_ids_filter(tmp_path) -> None:
    _seed(tmp_path)
    client = _client(tmp_path)
    resp = client.get(f"{PREFIX}/network/edges", params={"job_ids": "job_b"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["source_video_id"] for i in items] == ["d"]

    none = client.get(f"{PREFIX}/network/edges", params={"job_ids": "job_zzz"})
    assert none.status_code == 200
    assert none.json()["items"] == []
