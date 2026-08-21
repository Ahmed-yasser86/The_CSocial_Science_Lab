"""Tests for the async job endpoints, coverage/quality and corpus extras."""

from __future__ import annotations

import threading
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
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    RecommendationStatus,
    TranscriptStatus,
)
from SocialScienceResearch.domain.models import (
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    TranscriptRecord,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"
VIDEO_URL = "https://www.youtube.com/watch?v=v1example0000000000000000001"


class InstantProvider(AcquisitionProvider):
    """Synchronous in-memory provider (no network, no blocking)."""

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str) -> dict[str, Any]:
        return {
            "id": "v1example0000000000000000001",
            "channel_id": "UCexample00000000000000000",
            "title": "Instant video",
        }

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        return []


class BlockingProvider(InstantProvider):
    """Provider that blocks inside extract_video until a gate opens."""

    def __init__(self, started: threading.Event, gate: threading.Event) -> None:
        self.started = started
        self.gate = gate

    def extract_video(self, video_url: str) -> dict[str, Any]:
        self.started.set()
        if not self.gate.wait(timeout=10):
            raise RuntimeError("gate never opened")
        return super().extract_video(video_url)


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="api2"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed_repos(tmp_path) -> None:
    repos = build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="api2"))
    repos.runs.create_run(
        CollectionRun(
            run_id="run_api2_1",
            run_type="video",
            target_url=VIDEO_URL,
            target_video_id="v1example0000000000000000001",
            started_at=utcnow(),
            status="success",
        )
    )
    repos.videos.upsert_video(
        Video(
            video_id="v1example0000000000000000001",
            url=VIDEO_URL,
            channel_id="UCexample00000000000000000",
            title="Seeded video",
            duration=600,
            first_observed_run_id="run_api2_1",
            raw_json={"id": "v1example0000000000000000001", "title": "raw title"},
        )
    )
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id="obs_v1_a",
            collection_run_id="run_api2_1",
            video_id="v1example0000000000000000001",
            observed_at=utcnow(),
            view_count=1000,
            like_count=50,
            comment_count=5,
        )
    )
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id="obs_v1_b",
            collection_run_id="run_api2_1",
            video_id="v1example0000000000000000001",
            observed_at=utcnow(),
            view_count=2000,
            like_count=99,
            comment_count=8,
        )
    )
    root = Comment(
        comment_id="root_1",
        video_id="v1example0000000000000000001",
        author_name="Rooter",
        comment_text="I am the root comment.",
        first_observed_run_id="run_api2_1",
        is_reply=False,
    )
    repos.comments.upsert_comment(root)
    repos.comments.save_comment_observation(
        CommentObservation(
            observation_id="obs_c1",
            collection_run_id="run_api2_1",
            comment_id="root_1",
            observed_at=utcnow(),
            like_count=3,
        )
    )
    repos.comments.upsert_comment(
        Comment(
            comment_id="reply_1",
            video_id="v1example0000000000000000001",
            author_name="Replier",
            comment_text="A reply.",
            first_observed_run_id="run_api2_1",
            is_reply=True,
            parent_comment_id="root_1",
            root_comment_id="root_1",
        )
    )
    repos.recommendations.save_recommendation(
        RecommendationObservation(
            observation_id="rec_api2_1",
            collection_run_id="run_api2_1",
            source_video_id="v1example0000000000000000001",
            recommended_video_id="target_2",
            position=0,
            status=RecommendationStatus.OBSERVED,
        )
    )
    repos.transcripts.save_transcript(
        TranscriptRecord(
            transcript_id="tx_1",
            video_id="v1example0000000000000000001",
            collection_run_id="run_api2_1",
            path="transcripts/v1example0000000000000000001.txt",
            lang="en",
            status=TranscriptStatus.AVAILABLE,
            message=None,
            observed_at=utcnow(),
        )
    )
    repos.store.close()


@pytest.fixture
def client(tmp_path):
    _seed_repos(tmp_path)
    return TestClient(create_app(_settings(tmp_path)))


def _wait_for_terminal(client, job_id: str, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"{PREFIX}/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


# ----------------------------------------------------------------------
# Corpus extras
# ----------------------------------------------------------------------
def test_video_observations_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/videos/v1example0000000000000000001/observations")
    assert resp.status_code == 200
    observations = resp.json()["items"]
    assert len(observations) == 2
    assert {o["view_count"] for o in observations} == {1000, 2000}


def test_video_raw_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/videos/v1example0000000000000000001/raw")
    assert resp.status_code == 200
    assert resp.json()["raw_json"]["title"] == "raw title"


def test_video_raw_404(client) -> None:
    resp = client.get(f"{PREFIX}/videos/does_not_exist/raw")
    assert resp.status_code == 404


def test_comment_threads_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/videos/v1example0000000000000000001/comments/threads")
    assert resp.status_code == 200
    threads = resp.json()["items"]
    assert len(threads) == 1
    assert threads[0]["comment"]["comment_id"] == "root_1"
    assert [r["comment_id"] for r in threads[0]["replies"]] == ["reply_1"]


def test_channel_top_videos_endpoint(client) -> None:
    resp = client.get(
        f"{PREFIX}/channels/UCexample00000000000000000/videos/top",
        params={"metric": "views", "n": 5},
    )
    assert resp.status_code == 200
    top = resp.json()["top"]
    assert len(top) == 1
    assert top[0]["views"] == 2000  # latest observation wins


# ----------------------------------------------------------------------
# Quality / coverage
# ----------------------------------------------------------------------
def test_coverage_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_videos"] == 1
    assert body["transcripts_available"] == 1
    assert body["transcript_coverage"] == 1.0
    assert body["total_runs"] == 1


def test_dataset_summary_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/dataset/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["videos"] == 1
    assert body["transcripts_available"] == 1


# ----------------------------------------------------------------------
# Async job lifecycle
# ----------------------------------------------------------------------
def _spec_payload() -> dict[str, Any]:
    return {
        "targets": [{"kind": "video", "url": VIDEO_URL}],
        "collect_comments": False,
        "collect_transcripts": False,
    }


def test_collect_job_succeeds_and_returns_results(tmp_path) -> None:
    app = create_app(_settings(tmp_path), provider=InstantProvider())
    client = TestClient(app)

    resp = client.post(f"{PREFIX}/collect", json=_spec_payload())
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    job = _wait_for_terminal(client, job_id)
    assert job["status"] == "succeeded"

    result_resp = client.get(f"{PREFIX}/jobs/{job_id}/result")
    assert result_resp.status_code == 200
    body = result_resp.json()
    assert body["target_count"] == 1
    assert body["results"][0]["status"] == CollectionStatus.SUCCESS.value


def test_collect_job_cancel_while_running(tmp_path) -> None:
    started = threading.Event()
    gate = threading.Event()
    provider = BlockingProvider(started, gate)
    app = create_app(_settings(tmp_path), provider=provider)
    client = TestClient(app)

    resp = client.post(f"{PREFIX}/collect", json=_spec_payload())
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    assert started.wait(timeout=10), "worker never started"
    cancel_resp = client.post(f"{PREFIX}/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled"] is True

    gate.set()
    job = _wait_for_terminal(client, job_id)
    assert job["status"] == "cancelled"


def test_cancel_finished_job_returns_409(tmp_path) -> None:
    app = create_app(_settings(tmp_path), provider=InstantProvider())
    client = TestClient(app)

    resp = client.post(f"{PREFIX}/collect", json=_spec_payload())
    job_id = resp.json()["job_id"]
    _wait_for_terminal(client, job_id)

    cancel_resp = client.post(f"{PREFIX}/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 409


def test_job_result_404(tmp_path) -> None:
    app = create_app(_settings(tmp_path), provider=InstantProvider())
    client = TestClient(app)
    resp = client.get(f"{PREFIX}/jobs/nope/result")
    assert resp.status_code == 404


def test_job_stream_emits_terminal_snapshot(tmp_path) -> None:
    """SSE stream pushes the final (succeeded) snapshot and closes."""
    app = create_app(_settings(tmp_path), provider=InstantProvider())
    client = TestClient(app)

    resp = client.post(f"{PREFIX}/collect", json=_spec_payload())
    job_id = resp.json()["job_id"]

    with client.stream("GET", f"{PREFIX}/jobs/{job_id}/stream") as stream:
        events = _parse_sse(stream.iter_lines())
    assert stream.status_code == 200
    assert events, "stream closed without any events"
    last = events[-1]
    assert last["job_id"] == job_id
    assert last["status"] == "succeeded"


def test_job_stream_404_unknown_job(tmp_path) -> None:
    app = create_app(_settings(tmp_path), provider=InstantProvider())
    client = TestClient(app)
    resp = client.get(f"{PREFIX}/jobs/nope/stream")
    assert resp.status_code == 404


def _parse_sse(lines) -> list[dict[str, Any]]:
    """Collect ``data:`` payloads from an SSE line iterator into JSON dicts."""
    events: list[dict[str, Any]] = []
    current: list[str] = []
    for line in lines:
        if line == "":
            if current:
                data = "\n".join(current)
                if data.startswith("data: "):
                    import json as _json

                    events.append(_json.loads(data[len("data: "):]))
                current = []
        elif line.startswith("data: "):
            current.append(line)
        elif line.startswith(":"):
            continue  # keep-alive comment
        else:
            current.append(line)
    return events
