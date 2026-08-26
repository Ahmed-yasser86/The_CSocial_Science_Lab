"""Echo-chamber detector service tests (echo plan phases E1/E2 acceptance).

Uses a fake acquisition provider (no network), mirroring
``tests/test_layer_scrape_service.py``. Covers: layered chain with early
natural stops (exhausted / unsupported_stop), exact signal values on a
hand-built corpus, availability flags when comments are absent, continue
appending layers without mutating earlier rows, cooperative stop, and the
plan-J1 assertion that every run created under a detection carries the
job_id.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from SocialScienceResearch.acquisition.base import AcquisitionProvider, ChannelExtract
from SocialScienceResearch.acquisition.errors import InvalidURLError
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import CollectionRun, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.echo_chamber_service import EchoChamberService
from SocialScienceResearch.services.echo_scoring import compute_score, score_band
from SocialScienceResearch.services.jobs import JobManager
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

CH1 = "UCsource0000000000000000000"
CH2 = "UCtarget0000000000000000000"
SEED_A = "seed_a"
SEED_B = "seed_b"


def _video_payload(
    video_id: str,
    *,
    channel_id: str | None = CH1,
) -> dict[str, Any]:
    return {
        "id": video_id,
        "webpage_url": _url_for_video(video_id),
        "title": f"Title of {video_id}",
        "description": "echo target",
        "duration": 120,
        "channel_id": channel_id,
        "channel": "Some Channel",
        "view_count": 1000,
        "like_count": 50,
        "comment_count": 5,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "upload_date": "20250101",
        "timestamp": 1735689600,
    }


def _rec(rec_id: str, *, channel_id: str | None = CH1) -> dict[str, Any]:
    return {"id": rec_id, "channel_id": channel_id, "title": f"Rec {rec_id}"}


class EchoFakeProvider(AcquisitionProvider):
    """In-memory provider: returns configured payloads, never hits the network."""

    def __init__(
        self,
        *,
        videos: dict[str, dict[str, Any]] | None = None,
        recs: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.videos = videos or {}
        self.recs = recs or {}
        self.gate: threading.Event | None = None
        self.block_video_id: str | None = None
        self.block_started = threading.Event()

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise InvalidURLError("not used in echo tests")

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return dict(self.videos.get(video_id, _video_payload(video_id)))

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        if (
            self.gate is not None
            and self.block_video_id is not None
            and video_id == self.block_video_id
        ):
            self.block_started.set()
            if not self.gate.wait(timeout=10):
                raise RuntimeError("gate never opened")
        if video_id not in self.recs:
            return []
        return self.recs[video_id]


def _build_service(tmp_path, provider):
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="echo"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
    )
    repos = build_excel_repositories(settings.repository)
    jobs = JobManager(max_workers=2, max_stall_seconds=0)
    service = EchoChamberService(provider, repos, settings=settings, jobs=jobs)
    return service, repos, jobs


def _seed_channel_run(repos) -> CollectionRun:
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
    return run


def _wait_terminal(service, detection_id: str, timeout: float = 25.0):
    deadline = time.time() + timeout
    detection = None
    while time.time() < deadline:
        detection = service.get_detection(detection_id)
        assert detection is not None
        if detection.status not in ("pending", "running"):
            return detection
        time.sleep(0.05)
    raise AssertionError(
        f"detection did not finish in {timeout}s (status={detection.status})"
    )


# ----------------------------------------------------------------------
# Scoring primitives (pure functions; plan §2.2 band edges + weights)
# ----------------------------------------------------------------------
def test_score_band_edges() -> None:
    assert score_band(None) is None
    assert score_band(0.0) == "no_chamber_yet"
    assert score_band(0.399) == "no_chamber_yet"
    assert score_band(0.40) == "weak"
    assert score_band(0.60) == "weak"
    assert score_band(0.601) == "moderate"
    assert score_band(0.75) == "moderate"
    assert score_band(0.751) == "strong"


def test_score_renormalizes_over_available_components() -> None:
    # Only s1 + s4 available: their raw weights renormalize over the 0.50 sum.
    result = compute_score({"s1": 0.65, "s2": None, "s3": None, "s4": 0.0})
    by_key = {c["key"]: c for c in result["components"]}
    assert by_key["s1"]["weight_effective"] == pytest.approx(0.35 / 0.50, abs=1e-5)
    assert by_key["s4"]["weight_effective"] == pytest.approx(0.15 / 0.50, abs=1e-5)
    assert by_key["s2"]["status"] == "unavailable"
    # Missing CORE components => indicative score shown, labelled inconclusive.
    assert result["verdict"] == "inconclusive"
    assert result["value"] == pytest.approx(0.35 * 0.65 / 0.50, abs=1e-5)


def test_score_uses_all_components_when_all_available() -> None:
    result = compute_score({"s1": 0.5, "s2": 0.6, "s3": 0.7, "s4": 0.2, "s5": 0.4})
    assert result["verdict"] == "weak"  # 0.525
    total = sum(c["weight_effective"] for c in result["components"])
    assert total == pytest.approx(1.0, abs=1e-5)


def test_score_inconclusive_when_core_missing() -> None:
    result = compute_score({"s1": None, "s2": 0.9, "s3": 0.9, "s4": 0.9})
    assert result["verdict"] == "inconclusive"
    assert result["value"] is not None  # indicative score still shown


# ----------------------------------------------------------------------
# Full detection chain on a hand-built corpus
# ----------------------------------------------------------------------
def _corpus_provider() -> EchoFakeProvider:
    """3 crawl layers: L2 collapses 1-of-2 edges back onto known content."""
    return EchoFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH1),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2), _rec("t2", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH1), _rec("t2", channel_id=CH2)],
            "t2": [],
            "t3": [],
        },
    )


def test_chain_stops_early_with_exact_signals(tmp_path) -> None:
    """max_layers=5 stops naturally at the zero-edge layer; S1/S3 exact."""
    provider = _corpus_provider()
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        detection = service.start(seed_run_id=run.run_id, max_layers=5)
        detection = _wait_terminal(service, detection.detection_id)

        assert detection.status == "unsupported_stop"
        indexes = [snap["layer_index"] for snap in detection.layers]
        assert indexes == [0, 1, 2, 3]

        # Append-only snapshots frozen at computation time.
        layer2 = detection.layers[2]["signals"]
        assert layer2["s1"]["status"] == "available"
        # L2 edges: t1->t3 (new) and t1->t2 (target already known) => 1/2.
        assert layer2["s1"]["value"] == pytest.approx(0.5)
        assert layer2["s1"]["detail"]["per_layer"] == pytest.approx(0.5)

        final = detection.layers[-1]["signals"]
        # Cumulative S1 over layers >=2: only L2 contributed edges
        # (t1->t3 new, t1->t2 collapsed) => 1/2.
        assert final["s1"]["value"] == pytest.approx(0.5)
        # S3 channel projection: CH2 collects 4 of the 5 weighted in-edges.
        assert final["s3"]["detail"]["top1"] == pytest.approx(0.8)
        assert final["s3"]["detail"]["top3"] == pytest.approx(1.0)
        # Full share distribution: present, sorted desc, sums to ~1.0.
        shares = final["s3"]["detail"]["channel_shares"]
        assert shares
        weights = [entry["weight"] for entry in shares]
        assert weights == sorted(weights, reverse=True)
        assert sum(e["share"] for e in shares) == pytest.approx(1.0)
        assert all("channel_id" in e for e in shares)
        top_entry = shares[0]
        assert top_entry["weight"] == 4
        assert top_entry["share"] == pytest.approx(0.8)
        # S4 honest zero: no pair observed in >=2 layers on this corpus.
        assert final["s4"]["status"] == "available"
        assert final["s4"]["value"] == 0.0
        # S2 observed with the seeded louvain engine (raw share + modularity).
        assert final["s2"]["status"] == "available"
        assert 0.0 <= final["s2"]["value"] <= 1.0
        assert final["s2"]["detail"]["modularity"] is not None
        assert final["s2"]["detail"]["community_share"] <= 1.0

        # Verdict: core signals present -> a real band (never inconclusive).
        assert detection.score is not None
        assert detection.score["verdict"] in (
            "no_chamber_yet",
            "weak",
            "moderate",
            "strong",
        )
        keys = [c["key"] for c in detection.score["components"]]
        assert keys == ["s1", "s2", "s3", "s4", "s5"]
    finally:
        jobs.shutdown()


def test_s5_unavailable_when_comments_not_collected(tmp_path) -> None:
    provider = _corpus_provider()
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        detection = service.start(
            seed_run_id=run.run_id, max_layers=2, collect_comments=False
        )
        detection = _wait_terminal(service, detection.detection_id)
        final = detection.layers[-1]["signals"]
        assert final["s5"]["status"] == "unavailable"
        assert final["s5"]["value"] is None
        assert final["s5"]["detail"]["reason"] == (
            "comments were not collected during the crawl"
        )
    finally:
        jobs.shutdown()


def test_exhausted_frontier_is_a_distinct_natural_stop(tmp_path) -> None:
    provider = EchoFakeProvider(recs={SEED_A: [_rec("t1", channel_id=CH2)]})
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        # Mark every seed feed already observed -> frontier mode exhausts.
        for video in repos.videos.list_videos():
            repos.videos.mark_recommendations_scraped(video.video_id)
        detection = service.start(seed_run_id=run.run_id, max_layers=3)
        detection = _wait_terminal(service, detection.detection_id)
        assert detection.status == "exhausted"
        assert [s["layer_index"] for s in detection.layers] == [0]
    finally:
        jobs.shutdown()


def test_continue_appends_layers_without_mutating_earlier_rows(tmp_path) -> None:
    provider = EchoFakeProvider(
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2), _rec("t4", channel_id=CH2)],
            "t2": [_rec("t5", channel_id=CH2), _rec("t6", channel_id=CH2)],
            "t3": [],
            "t4": [],
            "t5": [],
            "t6": [],
        }
    )
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        detection = service.start(seed_run_id=run.run_id, max_layers=2)
        detection = _wait_terminal(service, detection.detection_id)
        assert detection.status == "completed"
        before = [dict(snap) for snap in detection.layers]

        continued = service.continue_detection(detection.detection_id, 2)
        continued = _wait_terminal(service, continued.detection_id)
        assert continued.status in ("completed", "unsupported_stop")
        after = continued.layers

        assert len(after) > len(before)
        for old, new in zip(before, after):
            assert old == new, "timeline mutated retroactively"
    finally:
        jobs.shutdown()


def test_stop_terminates_between_layers(tmp_path) -> None:
    provider = _corpus_provider()
    provider.gate = threading.Event()
    provider.block_video_id = "t1"  # blocks the layer-2 crawl mid-flight
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        detection = service.start(seed_run_id=run.run_id, max_layers=5)
        assert provider.block_started.wait(timeout=10), "crawl never reached layer 2"

        stopped = service.stop(detection.detection_id)
        assert stopped.status == "stopped"

        provider.gate.set()
        detection = _wait_terminal(service, detection.detection_id)
        assert detection.status == "stopped"
    finally:
        jobs.shutdown()


def test_runs_created_under_detection_carry_job_id(tmp_path) -> None:
    """Plan-J1 linkage: every run spawned by the echo job stamps job_id."""
    provider = _corpus_provider()
    service, repos, jobs = _build_service(tmp_path, provider)
    try:
        run = _seed_channel_run(repos)
        detection = service.start(seed_run_id=run.run_id, max_layers=2)
        detection = _wait_terminal(service, detection.detection_id)
        assert detection.job_id

        linked = [
            r
            for r in repos.runs.list_runs()
            if r.job_id == detection.job_id
        ]
        assert linked, "no runs were linked to the detection job"
        # The per-video recommendation sub-runs of the layer crawls register
        # under the seed run; they must carry the job id too (J1: no unparented
        # or unlinked child runs for new jobs).
        child_ids = {
            sub.run_id for sub in repos.runs.list_sub_runs(run.run_id)
        }
        assert child_ids, "expected nested per-video sub-runs under the seed run"
        for sub_id in child_ids:
            sub = repos.runs.get_run(sub_id)
            assert sub.job_id == detection.job_id
    finally:
        jobs.shutdown()
