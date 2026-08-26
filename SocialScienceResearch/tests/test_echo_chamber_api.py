"""Echo-chamber detector API tests (echo plan E1 + plan-J1 linkage).

Uses the FastAPI TestClient with a fake acquisition provider (no network):
covers POST /echo-chamber/detect, GET status/timeline, continue/stop, error
envelopes, and the J1 contract that a detection job exposes nested run
summaries and survives an application restart via the persisted rows.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.acquisition.base import AcquisitionProvider, ChannelExtract
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import CollectionRun, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

PREFIX = "/api/v1/social-science"
CH1 = "UCsource0000000000000000000"
CH2 = "UCtarget0000000000000000000"
SEED_A = "seed_a"
SEED_B = "seed_b"


def _rec(rec_id: str) -> dict[str, Any]:
    return {"id": rec_id, "channel_id": CH2, "title": f"Rec {rec_id}"}


class EchoApiProvider(AcquisitionProvider):
    """In-memory provider; optional blocking gate for one video's feed."""

    def __init__(self) -> None:
        self.gate: threading.Event | None = None
        self.block_video_id: str | None = None
        self.block_started = threading.Event()

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {
            "id": video_id,
            "webpage_url": video_url,
            "title": f"Title of {video_id}",
            "channel_id": CH2 if video_id.startswith("t") else CH1,
            "view_count": 100,
            "like_count": 5,
            "comment_count": 1,
        }

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        if self.gate is not None and video_id == self.block_video_id:
            self.block_started.set()
            if not self.gate.wait(timeout=10):
                raise RuntimeError("gate never opened")
        return {
            SEED_A: [_rec("t1"), _rec("t2")],
            SEED_B: [_rec("t2")],
            "t1": [_rec("t3"), _rec("t2")],
            "t2": [],
            "t3": [],
        }.get(video_id, [])


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="api_echo"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed_run(tmp_path) -> str:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="api_echo")
    )
    run = CollectionRun(
        run_id=new_run_id(),
        run_type=RunType.CHANNEL,
        target_url="https://www.youtube.com/@example",
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )
    repos.runs.create_run(run)
    for video_id in (SEED_A, SEED_B):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=_url_for_video(video_id),
                channel_id=CH1,
                title=f"Seed {video_id}",
                first_observed_run_id=run.run_id,
            )
        )
    repos.store.close()
    return run.run_id


def _wait_terminal(client, detection_id: str, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    body: dict[str, Any] = {}
    while time.time() < deadline:
        resp = client.get(f"{PREFIX}/echo-chamber/{detection_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"detection never finished: {body.get('status')}")


def test_detect_status_and_job_children_linkage(tmp_path) -> None:
    run_id = _seed_run(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))

    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={"seed_run_id": run_id, "max_layers": 3},
    )
    assert resp.status_code == 200
    payload = resp.json()
    detection_id, job_id = payload["detection_id"], payload["job_id"]
    assert detection_id and job_id

    detection = _wait_terminal(client, detection_id)
    assert detection["status"] in ("completed", "unsupported_stop")
    assert [snap["layer_index"] for snap in detection["layers"]]
    signals = detection["layers"][-1]["signals"]
    assert set(signals) == {"s1", "s2", "s3", "s4", "s5"}
    assert set(detection["score"]) >= {"value", "band", "verdict", "components"}

    # Plan-J1 linkage surfaced additively on the job detail: nested summaries
    # of every run stamped with this job id.
    job = client.get(f"{PREFIX}/jobs/{job_id}")
    assert job.status_code == 200
    job_body = job.json()
    assert job_body["runs"], "job detail carries no nested run summaries"

    # Restart simulation: flush the workbook (what a server shutdown does),
    # then boot a fresh app over the same workspace - the job must still be
    # listed from its persisted row.
    client.app.state.services["repos"].store.close()
    client2 = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))
    listed = client2.get(f"{PREFIX}/jobs").json()["items"]
    match = next(item for item in listed if item["job_id"] == job_id)
    assert match["status"] not in ("pending", "running")
    detected = client2.get(f"{PREFIX}/echo-chamber/{detection_id}")
    assert detected.status_code == 200


def test_detect_from_video_url_and_list_endpoint(tmp_path) -> None:
    client = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))
    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={
            "video_url": _url_for_video(SEED_A),
            "max_layers": 2,
            "collect_comments": False,
        },
    )
    assert resp.status_code == 200
    detection_id = resp.json()["detection_id"]

    detection = _wait_terminal(client, detection_id)
    assert detection["seed_video_id"] == SEED_A

    listed = client.get(f"{PREFIX}/echo-chamber").json()
    assert listed["total"] >= 1
    assert any(item["detection_id"] == detection_id for item in listed["items"])


def test_continue_appends_layers(tmp_path) -> None:
    run_id = _seed_run(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))

    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={"seed_run_id": run_id, "max_layers": 1},
    )
    detection_id = resp.json()["detection_id"]
    first = _wait_terminal(client, detection_id)
    count_before = len(first["layers"])

    cont = client.post(
        f"{PREFIX}/echo-chamber/{detection_id}/continue",
        json={"extra_layers": 2},
    )
    assert cont.status_code == 200
    assert cont.json()["job_id"]

    second = _wait_terminal(client, detection_id)
    assert len(second["layers"]) > count_before
    # Append-only guarantee: earlier rows identical.
    assert first["layers"] == second["layers"][:count_before]


def test_stop_terminates_running_detection(tmp_path) -> None:
    run_id = _seed_run(tmp_path)
    provider = EchoApiProvider()
    provider.gate = threading.Event()
    provider.block_video_id = "t1"  # blocks the layer-2 crawl mid-flight
    client = TestClient(create_app(_settings(tmp_path), provider=provider))

    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={"seed_run_id": run_id, "max_layers": 5},
    )
    detection_id = resp.json()["detection_id"]
    assert provider.block_started.wait(timeout=10)

    stop = client.post(f"{PREFIX}/echo-chamber/{detection_id}/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"

    provider.gate.set()
    detection = _wait_terminal(client, detection_id)
    assert detection["status"] == "stopped"


def test_unknown_detection_returns_404_envelope(tmp_path) -> None:
    client = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))
    resp = client.get(f"{PREFIX}/echo-chamber/ech_missing")
    assert resp.status_code == 404
    assert resp.json()["code"] == "http_404"

    resp = client.post(
        f"{PREFIX}/echo-chamber/ech_missing/continue", json={"extra_layers": 1}
    )
    assert resp.status_code == 404


def test_detect_requires_a_seed(tmp_path) -> None:
    client = TestClient(create_app(_settings(tmp_path), provider=EchoApiProvider()))
    resp = client.post(f"{PREFIX}/echo-chamber/detect", json={"max_layers": 2})
    assert resp.status_code == 400
    assert resp.json()["code"] == "http_400"

    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={"seed_run_id": "run_missing", "max_layers": 2},
    )
    assert resp.status_code == 404
