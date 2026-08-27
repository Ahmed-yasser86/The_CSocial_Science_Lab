"""Replacement-sampling regression tests (spec §3).

These deliberately avoid importing ``SocialScienceResearch.api`` (whose
module-level app singleton opens the same workbook the running backend holds,
causing a collection-time collision). The full pipeline is exercised via the
service + an in-process ``JobManager`` instead.
"""

from __future__ import annotations

import hashlib
import random
import tempfile
import time

import numpy as np
import pytest

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    TranscriptExtract,
)
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType, TranscriptStatus
from SocialScienceResearch.domain.models import CollectionRun, RecommendationObservation, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.content_homophily_service import (
    ContentHomophilyService,
)
from SocialScienceResearch.services.jobs import JobManager
from SocialScienceResearch.utils.idgen import new_id, new_run_id, utcnow

CH1 = "UCcluster100000000000000000"
CH2 = "UCcluster200000000000000000"
CLUSTER_A = [f"a{i}" for i in range(4)]
CLUSTER_B = [f"b{i}" for i in range(4)]


class FakeProvider(AcquisitionProvider):
    def extract_channel(self, channel_url): raise NotImplementedError
    def extract_video(self, video_url, *, include_comments=None):
        video_id = video_url.rsplit("v=", 1)[-1]
        return {"id": video_id, "webpage_url": video_url, "title": f"Title {video_id}", "channel_id": CH1}
    def extract_recommendations(self, video_url): return []
    def extract_transcript(self, video_url, lang=None):
        video_id = video_url.rsplit("v=", 1)[-1]
        if video_id in {"b2", "b3"}:
            return TranscriptExtract(status=TranscriptStatus.MISSING, message="no captions")
        cluster = "ALPHA" if video_id.startswith("a") else "BETA"
        return TranscriptExtract(content=f"{cluster} transcript about topic {video_id} " * 50, lang="en",
                                 status=TranscriptStatus.AVAILABLE)


class FakeEmbedder:
    model_name = "fake-embed-model"
    def embed_documents(self, texts):
        out = []
        for text in texts:
            vec = [0.0] * 8
            digest = hashlib.sha256(text.encode()).digest()
            for i, byte in enumerate(digest[:6]):
                vec[i] = byte / 255.0 * 0.01
            if "ALPHA" in text: vec[6] = 1.0
            elif "BETA" in text: vec[7] = 1.0
            out.append(vec)
        return out


def _seed_network(d):
    repos = build_excel_repositories(RepositorySettings(data_dir=str(d), dataset_name="chh"))
    run = CollectionRun(run_id=new_run_id(), run_type=RunType.RECOMMENDATION,
                        target_url=_url_for_video(CLUSTER_A[0]), started_at=utcnow(),
                        status=CollectionStatus.SUCCESS)
    repos.runs.create_run(run)
    for vid in CLUSTER_A + CLUSTER_B:
        repos.videos.upsert_video(Video(video_id=vid, url=_url_for_video(vid),
                                        channel_id=CH1 if vid.startswith("a") else CH2,
                                        title=f"Video {vid}", first_observed_run_id=run.run_id))
    def edge(s, t):
        repos.recommendations.save_recommendation(RecommendationObservation(
            observation_id=new_id("obs"), collection_run_id=run.run_id,
            source_video_id=s, recommended_video_id=t, observed_at=utcnow()))
    for s in CLUSTER_A:
        for t in CLUSTER_A:
            if s != t: edge(s, t)
    for s in CLUSTER_B:
        for t in CLUSTER_B:
            if s != t: edge(s, t)
    edge(CLUSTER_A[0], CLUSTER_B[0])
    repos.store.close()
    return run.run_id


def _run_pipeline(d, **kwargs):
    run_id = _seed_network(d)
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(d), dataset_name="chh", backend="excel"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix="/api/v1/social-science"),
    )
    repos = build_excel_repositories(settings.repository)
    jobs = JobManager()
    svc = ContentHomophilyService(FakeProvider(), repos, settings=settings, jobs=jobs,
                                  embedder=FakeEmbedder())
    payload = svc.start(run_id=run_id, **kwargs)
    aid = payload["analysis_id"]
    deadline = time.time() + 60
    while time.time() < deadline:
        rec = svc.get(aid)
        if rec["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    return svc.get(aid)


# ---------------------------------------------------------------------------
# Unit-level: the replacement sampler itself
# ---------------------------------------------------------------------------
def _fake_record():
    return {"progress": {}, "analysis_id": "test"}


class _StubAdapter:
    model_name = "stub"
    def video_vector(self, video_id, text):
        return np.zeros(4)


def test_replacement_substitutes_missing_with_same_community_peer():
    svc = ContentHomophilyService.__new__(ContentHomophilyService)
    labels = {"m": 1, "1": 1, "2": 1, "3": 1, "x": 2}
    capped_groups = {1: ["1", "2", "3", "m"], 2: ["x"]}
    vectors = {"1": np.zeros(4), "2": np.zeros(4), "3": np.zeros(4), "x": np.zeros(4)}
    within_pairs = [["m", "1"], ["m", "2"]]
    between_pairs = [["m", "x"]]
    known_missing = {"m"}
    meta = svc._run_replacement_sampling(
        _fake_record(), "a", capped_groups, labels,
        within_pairs, between_pairs, _StubAdapter(), vectors,
        random.Random(1), known_missing)
    assert meta["pairs_dropped"] == 0
    assert meta["replacement_successes"] >= 1
    assert meta["replacement_fetches"] == 0
    for lst in (within_pairs, between_pairs):
        for a, b in lst:
            assert "m" not in (a, b)


def test_replacement_drops_pair_when_no_same_community_peer():
    svc = ContentHomophilyService.__new__(ContentHomophilyService)
    labels = {"m": 1, "m2": 1}
    capped_groups = {1: ["m", "m2"]}
    vectors: dict[str, np.ndarray] = {}
    within_pairs = [["m", "m2"]]
    between_pairs: list[list[str]] = []
    known_missing = {"m", "m2"}
    meta = svc._run_replacement_sampling(
        _fake_record(), "a", capped_groups, labels,
        within_pairs, between_pairs, _StubAdapter(), vectors,
        random.Random(1), known_missing)
    assert meta["pairs_dropped"] == 1
    assert meta["replacement_successes"] == 0


# ---------------------------------------------------------------------------
# Full pipeline: replacement keeps the target usable sample
# ---------------------------------------------------------------------------
def test_full_pipeline_replacement_keeps_target_sample():
    with tempfile.TemporaryDirectory() as td:
        rec = _run_pipeline(td, sampling_fraction=0.5, num_permutations=30, random_seed=42)
        assert rec["status"] == "observed", rec.get("error")
        r = rec["results"]
        assert r["videos_without_transcript"] >= 2
        assert r["observed_difference"] > 0
        assert r["pairs_dropped_after_replacement"] == 0
        assert r["replacement_successes"] >= 1
        assert r["videos_analyzed"] >= r["videos_with_transcript"]
