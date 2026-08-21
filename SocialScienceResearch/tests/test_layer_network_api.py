"""API tests for the layer-crawl endpoints (docs/analysis_next_layer_scrape.md §6).

Bootstraps layer 0 from a seeded run, runs the job-backed ``/network/layer/scrape``
crawl, then exercises the layer list/detail/relations/graph/frontier reads plus
the 400/404 error paths.
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

SEED_RUN = "run_layer_seed"
SEED_A = "seed_a"
SEED_B = "seed_b"


class LayerApiProvider(AcquisitionProvider):
    """In-memory provider: seed recs point to two brand-new target videos."""

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {
            "id": video_id,
            "webpage_url": video_url,
            "title": f"Layer target {video_id}",
            "description": "from the layer crawl",
            "channel_id": f"UC{video_id}channel",
            "channel": f"Channel {video_id}",
            "view_count": 100,
            "like_count": 10,
            "comment_count": 0,
        }

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        targets = {
            SEED_A: [{"id": "t1", "channel_id": "UCt1channel"}],
            SEED_B: [{"id": "t2", "channel_id": "UCt2channel"}],
        }
        return targets.get(video_id, [])


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="layer_api"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="layer_api"))
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
    return TestClient(create_app(_settings(tmp_path), provider=LayerApiProvider()))


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


def test_layer_bootstrap_and_scrape_lifecycle(client) -> None:
    # Bootstrap layer 0 from the seed run.
    resp = client.post(f"{PREFIX}/network/layer", json={"run_id": SEED_RUN})
    assert resp.status_code == 200, resp.text
    layer0 = resp.json()
    assert layer0["layer_index"] == 0
    assert layer0["parent_run_id"] == SEED_RUN
    assert layer0["status"] == "success"
    assert set(layer0["frontier_video_ids"]) == {SEED_A, SEED_B}

    # Scrape layer 1 (job-backed).
    resp = client.post(
        f"{PREFIX}/network/layer/scrape",
        json={"parent_layer_run_id": layer0["layer_run_id"], "collect_comments": True},
    )
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]
    job = _wait_for_terminal(client, job_id)
    assert job["status"] == "succeeded"

    # Layer list exposes the new layer first.
    layers = client.get(f"{PREFIX}/network/layers").json()
    assert layers["total"] == 2
    layer1 = layers["items"][0]
    assert layer1["layer_index"] == 1
    assert layer1["parent_layer_run_id"] == layer0["layer_run_id"]
    assert set(layer1["discovered_video_ids"]) == {"t1", "t2"}

    # Detail endpoint.
    detail = client.get(f"{PREFIX}/network/layer/{layer1['layer_run_id']}").json()
    assert detail["layer_index"] == 1
    assert detail["summary"]["new_videos"] == 2

    # Relations report.
    relations = client.get(
        f"{PREFIX}/network/layer/{layer1['layer_run_id']}/relations"
    ).json()
    assert relations["counts"]["new_videos"] == 2
    assert relations["counts"]["new_edges"] == 2
    assert relations["counts"]["new_components"] == 2  # {seed_a,t1} and {seed_b,t2}

    # Graph projections.
    video_graph = client.get(
        f"{PREFIX}/network/layer/{layer1['layer_run_id']}/graph"
    ).json()
    assert video_graph["edge_count"] == 2

    channel_graph = client.get(
        f"{PREFIX}/network/layer/{layer1['layer_run_id']}/graph",
        params={"projection": "channel"},
    ).json()
    assert channel_graph["projection"] == "channel"
    assert channel_graph["unattributed_edges"] == 0
    assert channel_graph["node_count"] >= 2

    # Frontier for the stepper.
    frontier = client.get(
        f"{PREFIX}/network/layer/{layer1['layer_run_id']}/frontier"
    ).json()
    assert frontier["layer_index"] == 1
    assert set(frontier["video_ids"]) == {"t1", "t2"}


def test_layer_errors(client) -> None:
    # Unknown seed run -> 400 (invalid_argument).
    resp = client.post(f"{PREFIX}/network/layer", json={"run_id": "run_missing"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"

    # Unknown layer -> 404.
    assert client.get(f"{PREFIX}/network/layer/nope").status_code == 404
    assert client.get(f"{PREFIX}/network/layer/nope/relations").status_code == 404
    assert client.get(f"{PREFIX}/network/layer/nope/frontier").status_code == 404

    # Invalid projection -> 400.
    assert client.get(
        f"{PREFIX}/network/layer/nope/graph", params={"projection": "bogus"}
    ).status_code == 400
    assert (
        client.post(f"{PREFIX}/network/layer", json={"run_id": SEED_RUN, "projection": "bogus"})
        .status_code
        == 400
    )


def test_scrape_unknown_layer_is_404(client) -> None:
    resp = client.post(
        f"{PREFIX}/network/layer/scrape",
        json={"parent_layer_run_id": "lyr_missing"},
    )
    assert resp.status_code == 404


def test_layer_0_graph_is_seed_scoped(client) -> None:
    resp = client.post(f"{PREFIX}/network/layer", json={"run_id": SEED_RUN})
    layer0 = resp.json()
    graph = client.get(f"{PREFIX}/network/layer/{layer0['layer_run_id']}/graph").json()
    # Layer 0 has no scraped edges; it serves the seed run slice (no edges).
    assert graph["edge_count"] == 0
