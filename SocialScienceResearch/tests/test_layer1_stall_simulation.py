"""Reproduce the echo-chamber layer-1 collapse exactly (no network).

Scenario under test (observed on job_20260827_105320_62eedb83):
  * seed run discovered 23 recommendation targets,
  * layer 1 scraped those 23 frontier videos,
  * every scrape stalled past the 120s per-task budget (`_FUTURE_TIMEOUT`),
  * `collect_recommendations_for_videos` returned [] -> 0 runs -> 0 edges,
  * the echo loop hit `edges_observed == 0` and stopped with `unsupported_stop`.

The real-world cause of the stall was YouTube throttling/blocking the host IP
(see the user note "my ip will get blocked"), which makes yt-dlp hang/stall far
longer than the per-task budget. To simulate that offline we make the fake
provider *block* longer than the budget and shrink the budget to 0.3s by
monkeypatching `concurrent.futures.wait` (the code calls it with
`timeout=_FUTURE_TIMEOUT`, a local literal we cannot patch directly).
"""

from __future__ import annotations

import concurrent.futures as _cf
import time

import pytest

from SocialScienceResearch.acquisition.base import AcquisitionProvider
from SocialScienceResearch.acquisition.errors import InvalidURLError
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RecommendationStatus, RunType
from SocialScienceResearch.domain.models import CollectionRun, RecommendationObservation, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.echo_chamber_service import EchoChamberService
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services.recommendation_service import RecommendationService
from SocialScienceResearch.services.jobs import JobManager
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

SEED = "Ca4fjWgPrwI"
FRONTIER = [
    "zpf_R4TU8YY", "gMFvRioj6TY", "1X66HPJM_Lc", "a3NW1v_YgwI", "moq_hFm9QlE",
    "p8OolG9TMZ0", "54fea7wuV6s", "5Y3a06rJjoU", "PG3hbjBNQSw", "M9Y78gudpmk",
    "biN5iq77Vw4", "kQNdke9P-X0", "d2SNX3bfYKw", "QLcGs-eosOE", "ja_HgVeIKpw",
    "5vvr7KXAfck", "CwCds31fBW8", "FSrZuLpyqz4", "Lo-zfHBhtuw", "rPEpagUO7LI",
    "6hGAtMFD6Cc", "1nJOku-FPV8",
]

_real_wait = _cf.wait


def _fast_wait(fs, timeout=None, return_when=_cf.ALL_COMPLETED):
    # Simulate the 120s per-task budget being exceeded: any scrape that blocks
    # longer than 0.3s is treated as a timeout (the real code cancels + breaks).
    return _real_wait(fs, timeout=0.3, return_when=return_when)


@pytest.fixture
def fast_budget(monkeypatch):
    monkeypatch.setattr(_cf, "wait", _fast_wait)


class StallProvider(AcquisitionProvider):
    """Fake provider that HANGS for the frontier videos (IP-block stall)."""

    def __init__(self, *, stall_for, stall_seconds: float = 1.0):
        self.stall_for = set(stall_for)
        self.stall_seconds = stall_seconds

    def extract_channel(self, channel_url: str):
        raise InvalidURLError("not used")

    def extract_video(self, video_url: str, *, include_comments=None):
        vid = video_url.rsplit("v=", 1)[-1]
        return {"id": vid, "title": f"v-{vid}"}

    def extract_recommendations(self, video_url: str) -> list[dict]:
        vid = video_url.rsplit("v=", 1)[-1]
        if vid in self.stall_for:
            # Block longer than the (patched) budget -> per-task timeout.
            time.sleep(self.stall_seconds)
            return []
        return []


def _settings(tmp_path):
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="stallsim"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
    )


def _seed_recommendation_run(repos, seed_id=SEED, target_ids=FRONTIER):
    run = CollectionRun(
        run_id=new_run_id(),
        run_type=RunType.RECOMMENDATION,
        target_url=_url_for_video(seed_id),
        target_video_id=seed_id,
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )
    repos.runs.create_run(run)
    repos.videos.upsert_video(Video(video_id=seed_id, url=_url_for_video(seed_id), title="seed", first_observed_run_id=run.run_id))
    for i, tid in enumerate(target_ids):
        repos.videos.upsert_video(Video(video_id=tid, url=_url_for_video(tid), title=f"t{i}", first_observed_run_id=run.run_id))
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=new_run_id(),
                collection_run_id=run.run_id,
                source_video_id=seed_id,
                recommended_video_id=tid,
                position=i,
                status=RecommendationStatus.OBSERVED,
            )
        )
    return run


# ---------------------------------------------------------------------------
# Test 1: the exact function that returned [] in the real job
# ---------------------------------------------------------------------------
def test_collect_returns_empty_when_extract_stalls(fast_budget, tmp_path):
    repos = build_excel_repositories(_settings(tmp_path).repository)
    provider = StallProvider(stall_for=set(FRONTIER))
    service = RecommendationService(provider, repos, settings=_settings(tmp_path))

    results = service.collect_recommendations_for_videos(list(FRONTIER))

    assert results == [], "collect must return [] when every scrape exceeds the budget"


# ---------------------------------------------------------------------------
# Test 2: scrape_next_layer records run_ids=[] / new_edges=0 (the observed row)
# ---------------------------------------------------------------------------
def test_scrape_next_layer_records_zero_edges_on_stall(fast_budget, tmp_path, monkeypatch):
    repos = build_excel_repositories(_settings(tmp_path).repository)
    provider = StallProvider(stall_for=set(FRONTIER))
    service = LayerScrapeService(provider, repos, settings=_settings(tmp_path))

    seed_run = _seed_recommendation_run(repos)
    layer0 = service.bootstrap_layer(seed_run.run_id)

    captured = []
    original_save = repos.layers.save_layer_run

    def _capture(layer):
        captured.append(layer)
        return original_save(layer)

    monkeypatch.setattr(repos.layers, "save_layer_run", _capture)

    service.scrape_next_layer(
        parent_layer_run_id=layer0.layer_run_id,
        discovery_mode="frontier",
    )

    layer1 = captured[-1]
    assert layer1.frontier_video_ids, "frontier must be resolved to the 23 targets"
    assert layer1.run_ids == [], "no recommendation runs should be created on a full stall"
    assert layer1.summary.get("new_edges", 0) == 0, "no edges observed"


# ---------------------------------------------------------------------------
# Test 3: end-to-end echo job stops with unsupported_stop after layer 1
# ---------------------------------------------------------------------------
def test_echo_chamber_stops_unsupported_on_layer1_stall(fast_budget, tmp_path):
    repos = build_excel_repositories(_settings(tmp_path).repository)
    provider = StallProvider(stall_for=set(FRONTIER))
    jobs = JobManager(max_workers=2, max_stall_seconds=0)
    service = EchoChamberService(provider, repos, settings=_settings(tmp_path), jobs=jobs)

    seed_run = _seed_recommendation_run(repos)
    try:
        detection = service.start(seed_run_id=seed_run.run_id, max_layers=2)
        detection = _wait_terminal(service, detection.detection_id)

        assert detection.status == "unsupported_stop"
        layer_indexes = [s["layer_index"] for s in detection.layers]
        assert layer_indexes == [0, 1], "must stop after layer 1"
        last = detection.layers[-1]
        assert last["edges_observed"] == 0, "layer 1 observed no edges"
    finally:
        jobs.shutdown()


def _wait_terminal(service, detection_id, timeout: float = 25.0):
    deadline = time.time() + timeout
    detection = None
    while time.time() < deadline:
        detection = service.get_detection(detection_id)
        assert detection is not None
        if detection.status not in ("pending", "running"):
            return detection
        time.sleep(0.05)
    raise AssertionError(f"detection not terminal in {timeout}s: {detection.status}")
