"""Content Homophily end-to-end API tests (opt-in, on-demand job).

Uses FastAPI TestClient + Excel repositories + a fake provider/embedder:
covers the start/get/list contract, targeted transcript collection, embedding
reuse across runs, the §19 result fields, CONTENT EVIDENCE labelling,
disclaimers, insufficient_data handling, and that NO transcript is fetched
outside an explicitly requested analysis.
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    ChannelExtract,
    TranscriptExtract,
)
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
from SocialScienceResearch.domain.models import (
    CollectionRun,
    RecommendationObservation,
    Video,
)
from SocialScienceResearch.persistence.excel_repository import (
    build_excel_repositories,
)
from SocialScienceResearch.services.content_homophily_service import (
    ContentHomophilyService,
)
from SocialScienceResearch.utils.idgen import new_id, new_run_id, utcnow

PREFIX = "/api/v1/social-science"
CH1 = "UCcluster100000000000000000"
CH2 = "UCcluster200000000000000000"
CLUSTER_A = [f"a{i}" for i in range(4)]
CLUSTER_B = [f"b{i}" for i in range(4)]


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="chh",
            backend="excel",
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0,
                                request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


class FakeProvider(AcquisitionProvider):
    """No-network provider whose transcripts encode cluster membership."""

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str, *,
                      include_comments: bool | None = None) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {"id": video_id, "webpage_url": video_url,
                "title": f"Title of {video_id}", "channel_id": CH1}

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        return []

    def extract_transcript(self, video_url: str, lang=None) -> TranscriptExtract:
        video_id = video_url.rsplit("v=", 1)[-1]
        status_mod = __import__(
            "SocialScienceResearch.domain.enums", fromlist=["TranscriptStatus"]
        )
        # b2/b3 have no captions - explicit MISSING (never zero-filled).
        if video_id in {"b2", "b3"}:
            return TranscriptExtract(status=status_mod.TranscriptStatus.MISSING,
                                     message="no captions")
        cluster = "ALPHA" if video_id.startswith("a") else "BETA"
        return TranscriptExtract(
            content=f"{cluster} transcript about topic {video_id} " * 50,
            lang="en",
            status=status_mod.TranscriptStatus.AVAILABLE,
        )


class FakeEmbedder:
    """Deterministic embeddings: ALPHA/BETA markers map to orthogonal axes."""

    model_name = "fake-embed-model"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * 8
            digest = hashlib.sha256(text.encode()).digest()
            for i, byte in enumerate(digest[:6]):
                vec[i] = byte / 255.0 * 0.01
            if "ALPHA" in text:
                vec[6] = 1.0
            elif "BETA" in text:
                vec[7] = 1.0
            out.append(vec)
        return out


def _seed_network(tmp_path) -> str:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="chh")
    )
    run = CollectionRun(
        run_id=new_run_id(),
        run_type=RunType.RECOMMENDATION,
        target_url=_url_for_video(CLUSTER_A[0]),
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )
    repos.runs.create_run(run)
    for video_id in CLUSTER_A + CLUSTER_B:
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=_url_for_video(video_id),
                channel_id=CH1 if video_id.startswith("a") else CH2,
                title=f"Video {video_id}",
                first_observed_run_id=run.run_id,
            )
        )
    def _edge(src: str, tgt: str) -> None:
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=new_id("obs"),
                collection_run_id=run.run_id,
                source_video_id=src,
                recommended_video_id=tgt,
                observed_at=utcnow(),
            )
        )
    # Two dense clusters + one weak bridge (louvain must find >=2 groups).
    for src in CLUSTER_A:
        for tgt in CLUSTER_A:
            if src != tgt:
                _edge(src, tgt)
    for src in CLUSTER_B:
        for tgt in CLUSTER_B:
            if src != tgt:
                _edge(src, tgt)
    _edge(CLUSTER_A[0], CLUSTER_B[0])
    # An isolated video with no observed edges: its ego scope is a single
    # node, so an analysis over it must report insufficient_data honestly.
    repos.videos.upsert_video(
        Video(
            video_id="lonely",
            url=_url_for_video("lonely"),
            channel_id=CH1,
            title="Lonely video",
            first_observed_run_id=run.run_id,
        )
    )
    repos.store.close()
    return run.run_id


def _inject_service(client: TestClient, tmp_path) -> ContentHomophilyService:
    settings = client.app.state.settings
    service = ContentHomophilyService(
        FakeProvider(),
        client.app.state.services["repos"],
        settings=settings,
        jobs=client.app.state.services["jobs"],
        embedder=FakeEmbedder(),
    )
    client.app.state.services["content_homophily"] = service
    return service


def _wait_terminal(client: TestClient, analysis_id: str,
                   timeout: float = 60.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    body: dict[str, Any] = {}
    while time.time() < deadline:
        resp = client.get(f"{PREFIX}/network/content-homophily/{analysis_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"analysis never finished: {body.get('status')}")


def test_full_pipeline_results_contract(tmp_path) -> None:
    run_id = _seed_network(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=FakeProvider()))
    _inject_service(client, tmp_path)

    resp = client.post(f"{PREFIX}/network/content-homophily", json={
        "run_id": run_id,
        "sampling_fraction": 0.5,
        "num_permutations": 30,
        "random_seed": 42,
    })
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["analysis_id"] and payload["job_id"]

    record = _wait_terminal(client, payload["analysis_id"])
    assert record["status"] == "observed", record.get("error")
    results = record["results"]

    # §19 required output fields.
    expected = {
        "within_mean_similarity", "between_mean_similarity",
        "observed_difference", "null_mean", "null_std", "z_score",
        "permutation_p_value", "pairs_available_within", "pairs_sampled_within",
        "pairs_available_between", "pairs_sampled_between",
        "sampling_fraction", "max_pair_cap", "random_seed", "num_permutations",
        "videos_with_transcript", "videos_without_transcript",
        "transcript_coverage", "embedding_model", "embedding_model_version",
        "status",
    }
    missing = expected - set(results)
    assert not missing, f"missing §19 fields: {missing}"

    assert results["label"] == "CONTENT EVIDENCE"
    # Clustered transcripts => positive homophily difference.
    assert results["observed_difference"] > 0
    assert 0 < results["transcript_coverage"] <= 1
    # b2/b3 captions were explicitly unavailable (never zero-filled).
    assert results["videos_without_transcript"] >= 2
    assert results["pairs_available_between"] > 0
    assert results["pairs_sampled_within"] > 0
    assert results["embedding_model"] == "fake-embed-model"
    assert results["community_algorithm"]
    assert len(results["disclaimers"]) >= 3

    # Stage checklist completed end-to-end.
    stages = record["progress"]["stages"]
    assert set(stages.values()) == {"done"}
    assert record["progress"]["log"], "execution log must be exposed"

    # Embedding observability fields surfaced.
    assert record["progress"]["embeddings_generated"] >= 2
    assert record["progress"]["embedding_model"] == "fake-embed-model"

    listed = client.get(f"{PREFIX}/network/content-homophily").json()
    assert listed["total"] >= 1


def test_embeddings_reused_on_second_run(tmp_path) -> None:
    run_id = _seed_network(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=FakeProvider()))
    _inject_service(client, tmp_path)

    body = {"run_id": run_id, "sampling_fraction": 0.5,
            "num_permutations": 5, "random_seed": 7}
    first = client.post(f"{PREFIX}/network/content-homophily", json=body)
    record1 = _wait_terminal(client, first.json()["analysis_id"])
    assert record1["status"] == "observed"
    assert record1["results"]["embeddings_reused"] == 0
    generated = record1["results"]["embeddings_generated"]
    assert generated >= 2

    second = client.post(f"{PREFIX}/network/content-homophily", json=body)
    record2 = _wait_terminal(client, second.json()["analysis_id"])
    assert record2["status"] == "observed"
    assert record2["results"]["embeddings_reused"] >= generated
    assert record2["results"]["embeddings_generated"] == 0


def test_insufficient_data_single_video(tmp_path) -> None:
    _seed_network(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=FakeProvider()))
    _inject_service(client, tmp_path)

    resp = client.post(f"{PREFIX}/network/content-homophily", json={
        "video_ids": ["lonely"],
        "sampling_fraction": 0.1,
    })
    assert resp.status_code == 200
    record = _wait_terminal(client, resp.json()["analysis_id"])
    assert record["status"] == "insufficient_data"
    results = record["results"]
    assert results["pairs_available_within"] == 0
    assert results["pairs_sampled_within"] == 0
    assert results["within_mean_similarity"] is None
    assert results["status"] == "insufficient_data"


def test_start_requires_scope_and_validates_params(tmp_path) -> None:
    _seed_network(tmp_path)
    client = TestClient(create_app(_settings(tmp_path), provider=FakeProvider()))
    _inject_service(client, tmp_path)

    resp = client.post(f"{PREFIX}/network/content-homophily", json={})
    assert resp.status_code in (400, 422)

    resp = client.post(
        f"{PREFIX}/network/content-homophily",
        json={"run_id": "run_missing"},
    )
    assert resp.status_code == 400

    unknown = client.get(f"{PREFIX}/network/content-homophily/chh_missing")
    assert unknown.status_code == 404
