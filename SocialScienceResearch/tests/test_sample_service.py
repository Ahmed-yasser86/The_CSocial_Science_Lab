"""B5: Tests for persisted research samples (service, Excel round-trip, API).

Covers save/get/list/delete, the Excel round-trip on a fresh repository over
the same store, the member-list overflow chunking path (deliberately large
list), sample comparison (overlap / Jaccard), and the HTTP endpoints via a
``TestClient``.
"""

from __future__ import annotations

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
from SocialScienceResearch.domain.sample_models import Sample
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.sample_repository import SampleRepository
from SocialScienceResearch.services.sample_service import SampleService

PREFIX = "/api/v1/social-science"


def _make_sample(sample_id: str = "s1", member_ids=None, **overrides) -> Sample:
    ids = member_ids if member_ids is not None else ["m1", "m2", "m3"]
    return Sample(
        sample_id=sample_id,
        entity_type=overrides.pop("entity_type", "video"),
        strategy=overrides.pop("strategy", "top_views"),
        population_query_hash=overrides.pop("population_query_hash", "hash_abc"),
        population_size=overrides.pop("population_size", 1000),
        sample_size=len(ids),
        seed=overrides.pop("seed", 42),
        criteria_json=overrides.pop(
            "criteria_json", {"strategy": "top_views", "size": len(ids)}
        ),
        member_ids=ids,
        created_by_run_id=overrides.pop("created_by_run_id", "run_1"),
        **overrides,
    )


# ----------------------------------------------------------------------
# Repository + service round-trip through Excel
# ----------------------------------------------------------------------
def test_save_get_list_round_trip(excel_repos) -> None:
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id="s_round"))
    assert saved.sample_id == "s_round"
    assert saved.overflow is False
    assert saved.sample_size == 3

    loaded = svc.get_sample("s_round")
    assert loaded == saved
    assert loaded.member_ids == ["m1", "m2", "m3"]
    assert loaded.criteria_json["strategy"] == "top_views"
    assert loaded.created_by_run_id == "run_1"

    listed = svc.list_samples()
    assert [s.sample_id for s in listed] == ["s_round"]


def test_round_trip_through_fresh_repo_on_same_store(excel_repos) -> None:
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id="s_reopen"))
    excel_repos.store.close()

    store = WorkbookStore(excel_repos.store.path)
    fresh = SampleRepository(store)
    reloaded = fresh.get(saved.sample_id)
    assert reloaded is not None
    assert reloaded.sample_id == saved.sample_id
    assert reloaded.member_ids == saved.member_ids
    assert reloaded.criteria_json == saved.criteria_json
    assert reloaded.population_size == saved.population_size
    assert reloaded.overflow is False
    assert [s.sample_id for s in fresh.list()] == ["s_reopen"]


def test_small_member_list_is_not_chunked(excel_repos) -> None:
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id="s_small"))
    assert saved.overflow is False
    rows = excel_repos.store.read_rows("sample_members", key_field="chunk_key")
    assert rows == []


# ----------------------------------------------------------------------
# Member-list overflow chunking
# ----------------------------------------------------------------------
def test_member_list_chunking_with_50k_ids(excel_repos) -> None:
    ids = [f"member_{i:06d}" for i in range(50_000)]
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id="s_big", member_ids=ids))
    assert saved.overflow is True

    chunks = SampleRepository._chunk_ids(ids)
    assert len(chunks) > 1

    loaded = svc.get_sample("s_big")
    assert loaded is not None
    assert loaded.overflow is True
    assert loaded.sample_size == 50_000
    assert len(loaded.member_ids) == 50_000
    assert loaded.member_ids == ids

    members = svc.list_members("s_big")
    assert members == ids
    # chunk rows actually exist in the sidecar sheet
    rows = excel_repos.store.read_rows("sample_members", key_field="chunk_key")
    chunk_rows = [r for r in rows if r.get("sample_id") == "s_big"]
    assert len(chunk_rows) == len(chunks)


def test_chunked_sample_round_trips_through_fresh_repo(excel_repos) -> None:
    ids = [f"big_{i:06d}" for i in range(40_000)]
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id="s_big_reopen", member_ids=ids))
    assert saved.overflow is True
    excel_repos.store.close()

    store = WorkbookStore(excel_repos.store.path)
    fresh = SampleRepository(store)
    reloaded = fresh.get(saved.sample_id)
    assert reloaded is not None
    assert reloaded.overflow is True
    assert reloaded.member_ids == ids
    assert fresh.list_members(saved.sample_id) == ids


# ----------------------------------------------------------------------
# Service validation + id generation
# ----------------------------------------------------------------------
def test_save_rejects_bad_entity_type(excel_repos) -> None:
    svc = SampleService(excel_repos)
    with pytest.raises(ValueError):
        svc.save(_make_sample(sample_id="s_bad", entity_type="playlist"))


def test_sample_id_generated_when_absent(excel_repos) -> None:
    svc = SampleService(excel_repos)
    saved = svc.save(_make_sample(sample_id=""))
    assert saved.sample_id.startswith("sample_")
    assert svc.get_sample(saved.sample_id) == saved


def test_compare_requires_two_samples(excel_repos) -> None:
    svc = SampleService(excel_repos)
    svc.save(_make_sample(sample_id="only"))
    with pytest.raises(ValueError):
        svc.compare_samples(["only"])
    with pytest.raises(ValueError):
        svc.compare_samples(["missing_a", "missing_b"])


# ----------------------------------------------------------------------
# Delete (tombstone) semantics
# ----------------------------------------------------------------------
def test_delete_tombstones_and_is_idempotent(excel_repos) -> None:
    svc = SampleService(excel_repos)
    svc.save(_make_sample(sample_id="s_del"))
    assert svc.delete_sample("s_del") is True
    assert svc.delete_sample("s_del") is False  # already deleted
    assert svc.delete_sample("nope") is False   # never existed
    assert svc.get_sample("s_del") is None
    assert svc.list_members("s_del") == []
    assert all(s.sample_id != "s_del" for s in svc.list_samples())


# ----------------------------------------------------------------------
# Comparison
# ----------------------------------------------------------------------
def test_compare_overlap_and_jaccard(excel_repos) -> None:
    svc = SampleService(excel_repos)
    svc.save(_make_sample(sample_id="s_a", member_ids=["x1", "x2", "x3"]))
    svc.save(_make_sample(sample_id="s_b", member_ids=["x2", "x3", "x4", "x5"]))

    result = svc.compare_samples(["s_a", "s_b"])
    assert result.counts == {"s_a": 3, "s_b": 4}
    assert result.union_size == 5
    assert result.intersection_size == 2
    pair = result.pairwise["s_a|s_b"]
    assert pair.intersection_size == 2
    assert pair.union_size == 5
    assert pair.jaccard == pytest.approx(2 / 5)


def test_compare_criteria_diff(excel_repos) -> None:
    svc = SampleService(excel_repos)
    svc.save(_make_sample(sample_id="s_a", strategy="top_views"))
    svc.save(
        _make_sample(
            sample_id="s_b",
            strategy="random",
            seed=7,
            criteria_json={"strategy": "random", "size": 10},
        )
    )
    result = svc.compare_samples(["s_a", "s_b"])
    assert result.criteria_diffs["s_a"] == []  # reference == itself
    assert "strategy" in result.criteria_diffs["s_b"]
    assert "seed" in result.criteria_diffs["s_b"]
    assert "criteria_json" in result.criteria_diffs["s_b"]


# ----------------------------------------------------------------------
# HTTP endpoints (TestClient)
# ----------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "samples_api")
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="samples_api")
    repos = build_excel_repositories(repo_settings)
    svc = SampleService(repos)
    for i in range(3):
        svc.save(_make_sample(sample_id=f"s{i}", member_ids=[f"m{i}_{j}" for j in range(3)]))
    repos.store.close()

    settings = SocialScienceSettings(
        repository=repo_settings,
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )
    yield TestClient(create_app(settings))


def test_create_sample_endpoint(client) -> None:
    resp = client.post(
        f"{PREFIX}/samples",
        json={
            "entity_type": "comment",
            "strategy": "random",
            "seed": 7,
            "criteria_json": {"strategy": "random", "size": 2},
            "population_size": 500,
            "member_ids": ["m1", "m2"],
            "created_by_run_id": "run_2",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_type"] == "comment"
    assert body["strategy"] == "random"
    assert body["member_ids"] == ["m1", "m2"]
    assert body["sample_size"] == 2
    assert body["overflow"] is False
    assert body["sample_id"].startswith("sample_")

    # unknown request field -> 422 (extra="forbid")
    bad = client.post(
        f"{PREFIX}/samples",
        json={"entity_type": "video", "strategy": "x", "population_size": 1, "mystery": 1},
    )
    assert bad.status_code == 422


def test_list_samples_paginated_envelope(client) -> None:
    resp = client.get(f"{PREFIX}/samples", params={"page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "next_cursor", "has_more", "total"}
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["has_more"] is True
    assert body["next_cursor"] is not None

    resp2 = client.get(
        f"{PREFIX}/samples", params={"page_size": 2, "cursor": body["next_cursor"]}
    )
    body2 = resp2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False
    assert body2["next_cursor"] is None
    ids = [item["sample_id"] for item in body["items"] + body2["items"]]
    assert sorted(ids) == ["s0", "s1", "s2"]


def test_get_sample_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/samples/s0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_id"] == "s0"
    assert body["member_ids"] == ["m0_0", "m0_1", "m0_2"]


def test_get_sample_missing_404(client) -> None:
    resp = client.get(f"{PREFIX}/samples/nope")
    assert resp.status_code == 404


def test_sample_members_paginated(client) -> None:
    resp = client.get(f"{PREFIX}/samples/s0/members", params={"page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "next_cursor", "has_more", "total"}
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["has_more"] is True

    resp = client.get(f"{PREFIX}/samples/nope/members")
    assert resp.status_code == 404


def test_delete_sample_endpoint(client) -> None:
    resp = client.delete(f"{PREFIX}/samples/s0")
    assert resp.status_code == 200
    assert resp.json() == {"sample_id": "s0", "deleted": True}

    missing = client.delete(f"{PREFIX}/samples/s0")
    assert missing.status_code == 404

    fetch = client.get(f"{PREFIX}/samples/s0")
    assert fetch.status_code == 404


def test_compare_endpoint(client) -> None:
    resp = client.post(
        f"{PREFIX}/samples/compare",
        json={"sample_ids": ["s0", "s1"], "metrics": ["likes"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"] == {"s0": 3, "s1": 3}
    assert body["union_size"] == 6
    assert body["intersection_size"] == 0
    assert "s0|s1" in body["pairwise"]
    assert body["pairwise"]["s0|s1"]["jaccard"] == 0.0
    assert body["metrics"] == ["likes"]

    bad = client.post(f"{PREFIX}/samples/compare", json={"sample_ids": ["s0"]})
    assert bad.status_code == 400  # ValueError -> invalid_argument envelope


def test_create_sample_with_large_list_chunks_through_api(client) -> None:
    ids = [f"api_member_{i:06d}" for i in range(20_000)]
    resp = client.post(
        f"{PREFIX}/samples",
        json={
            "entity_type": "video",
            "strategy": "random",
            "seed": 1,
            "population_size": 200_000,
            "population_query_hash": "hash_api",
            "member_ids": ids,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overflow"] is True
    assert body["sample_size"] == 20_000
    assert len(body["member_ids"]) == 20_000

    sample_id = body["sample_id"]
    fetched = client.get(f"{PREFIX}/samples/{sample_id}")
    assert fetched.status_code == 200
    assert fetched.json()["member_ids"] == ids

    members = client.get(f"{PREFIX}/samples/{sample_id}/members", params={"page_size": 500})
    assert members.status_code == 200
    assert members.json()["total"] == 20_000