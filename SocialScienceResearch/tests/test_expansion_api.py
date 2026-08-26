"""API tests for the network-expansion endpoints
(docs/network_expansion_scrape_all.md §6/§8).

Bootstraps a seeded channel run, submits job-backed ``scrape-video`` /
``scrape-all`` expansions, then exercises the action list/detail/stats/graph
reads plus the 400/404/422 error paths.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    ChannelExtract,
)
from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.models import CollectionRun, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"

SEED_RUN = "run_exp_seed"
SEED_A = "seed_a"
SEED_B = "seed_b"
T1 = "t1"
T2 = "t2"


class ExpansionApiProvider(AcquisitionProvider):
    """In-memory provider: seed recs point to brand-new target videos."""

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {
            "id": video_id,
            "webpage_url": video_url,
            "title": f"Expansion target {video_id}",
            "description": "from the expansion crawl",
            "channel_id": f"UC{video_id}channel",
            "channel": f"Channel {video_id}",
            "view_count": 100,
            "like_count": 10,
            "comment_count": 0,
        }

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        targets = {
            SEED_A: [{"id": T1, "channel_id": "UCt1channel"}],
            SEED_B: [{"id": T2, "channel_id": "UCt2channel"}],
        }
        return targets.get(video_id, [])


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="exp_api"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="exp_api")
    )
    repos.runs.create_run(
        CollectionRun(
            run_id=SEED_RUN,
            run_type="channel",
            target_url="https://www.youtube.com/@seed",
            started_at=utcnow(),
            status="success",
        )
    )
    for video_id in (SEED_A, SEED_B):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id="UCseedchannel",
                title=f"Seed {video_id}",
                first_observed_run_id=SEED_RUN,
            )
        )
    repos.store.close()


@pytest.fixture
def client(tmp_path):
    _seed(tmp_path)
    return TestClient(create_app(_settings(tmp_path), provider=ExpansionApiProvider()))


def _wait_for_terminal(client, job_id: str, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"{PREFIX}/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached a terminal state")


def test_expansion_scrape_video_lifecycle(client) -> None:
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-video",
        json={"video_id": SEED_A},
    )
    assert resp.status_code == 200, resp.text
    job = _wait_for_terminal(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"

    # Action list exposes the new action.
    actions = client.get(f"{PREFIX}/network/expansion").json()
    assert actions["total"] == 1
    action = actions["items"][0]
    assert action["kind"] == "video"
    assert action["video_ids"] == [SEED_A]
    assert action["status"] == "success"
    assert action["projection"] == "video"
    assert action["project_id"] is not None
    assert set(action["discovered_video_ids"]) == {T1}
    assert set(action["run_ids"])

    # Detail endpoint mirrors the list payload.
    detail = client.get(f"{PREFIX}/network/expansion/{action['action_id']}").json()
    assert detail == action

    # Stats: overall + per-video rows.
    stats = client.get(f"{PREFIX}/network/expansion/{action['action_id']}/stats").json()
    assert stats["action"]["action_id"] == action["action_id"]
    assert stats["overall"]["edge_count"] == 1
    assert stats["overall"]["source_count"] == 1
    assert stats["overall"]["node_count"] == 2
    assert stats["videos"][0]["video_id"] == SEED_A
    assert stats["videos"][0]["recommendation_count"] == 1

    # Graph projections.
    video_graph = client.get(
        f"{PREFIX}/network/expansion/{action['action_id']}/graph"
    ).json()
    assert video_graph["edge_count"] == 1

    channel_graph = client.get(
        f"{PREFIX}/network/expansion/{action['action_id']}/graph",
        params={"projection": "channel"},
    ).json()
    assert channel_graph["projection"] == "channel"
    assert channel_graph["node_count"] >= 1


def test_expansion_scrape_all_with_run_id(client) -> None:
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-all",
        json={"run_id": SEED_RUN},
    )
    assert resp.status_code == 200, resp.text
    job = _wait_for_terminal(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"

    actions = client.get(f"{PREFIX}/network/expansion").json()
    action = actions["items"][0]
    assert action["kind"] == "all"
    assert set(action["video_ids"]) == {SEED_A, SEED_B}
    assert set(action["discovered_video_ids"]) == {T1, T2}
    assert len(action["run_ids"]) == 2

    stats = client.get(f"{PREFIX}/network/expansion/{action['action_id']}/stats").json()
    assert stats["overall"]["edge_count"] == 2
    assert stats["overall"]["source_count"] == 2


def test_expansion_scrape_all_with_video_ids(client) -> None:
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-all",
        json={"video_ids": [SEED_B], "filters": {"max_recommendations_per_video": 1}},
    )
    assert resp.status_code == 200, resp.text
    job = _wait_for_terminal(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"

    actions = client.get(f"{PREFIX}/network/expansion").json()
    action = actions["items"][0]
    assert action["video_ids"] == [SEED_B]
    assert action["filters"]["max_recommendations_per_video"] == 1


def test_expansion_errors(client) -> None:
    # A video that is only a graph node (not yet a Video row) is queued and
    # extracted on the fly instead of 404ing.
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-video", json={"video_id": "missing"}
    )
    assert resp.status_code == 200, resp.text
    job = _wait_for_terminal(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"

    # Missing scope -> 400.
    resp = client.post(f"{PREFIX}/network/expansion/scrape-all", json={})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"

    # Unknown run -> 404.
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-all", json={"run_id": "run_nope"}
    )
    assert resp.status_code == 404

    # Bad projection on a job -> 400 (invalid_argument).
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-video",
        json={"video_id": SEED_A, "filters": {"projection": "bogus"}},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"

    # Unknown action -> 404.
    assert client.get(f"{PREFIX}/network/expansion/nope").status_code == 404
    assert client.get(f"{PREFIX}/network/expansion/nope/stats").status_code == 404
    assert client.get(f"{PREFIX}/network/expansion/nope/graph").status_code == 404

    # Bad projection on graph -> 400.
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-video", json={"video_id": SEED_A}
    )
    job = _wait_for_terminal(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"
    action_id = client.get(f"{PREFIX}/network/expansion").json()["items"][0]["action_id"]
    assert (
        client.get(
            f"{PREFIX}/network/expansion/{action_id}/graph", params={"projection": "bogus"}
        ).status_code
        == 400
    )


def test_expansion_filters_reject_unknown_keys(client) -> None:
    resp = client.post(
        f"{PREFIX}/network/expansion/scrape-video",
        json={"video_id": SEED_A, "filters": {"nonsense": True}},
    )
    assert resp.status_code == 422


def test_expansion_options_returns_defaults(client) -> None:
    opts = client.get(f"{PREFIX}/network/expansion/options").json()
    assert opts["projection"] == "video"
    assert opts["collect_comments"] is True
    assert opts["dedupe"] is True
    assert opts["only_new_targets"] is True