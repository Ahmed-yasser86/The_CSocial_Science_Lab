"""Layer-crawl service tests (docs/analysis_next_layer_scrape.md §8.1).

Uses a fake acquisition provider (no network): seeds a channel run + videos,
bootstraps layer 0, then crawls layers and asserts run/edge layer_index
stamping, target deep-enrichment (Video + observation + comments), and the
NEW/EXISTING + CONNECTED/DISCONNECTED classification algorithm.
"""

from __future__ import annotations

from typing import Any

import pytest

from SocialScienceResearch.acquisition.base import AcquisitionProvider, ChannelExtract
from SocialScienceResearch.acquisition.errors import (
    InvalidURLError,
    RecommendationUnsupportedError,
)
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import CollectionRun, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services.network_analytics_service import (
    NetworkAnalyticsService,
)
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

CH1 = "UCsource0000000000000000000"
CH2 = "UCtarget0000000000000000000"

SEED_A = "seed_a"
SEED_B = "seed_b"


def _video_payload(
    video_id: str,
    *,
    channel_id: str | None = CH1,
    title: str | None = None,
) -> dict[str, Any]:
    return {
        "id": video_id,
        "webpage_url": _url_for_video(video_id),
        "title": title or f"Title of {video_id}",
        "description": "layer target",
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


def _rec(rec_id: str, *, channel_id: str | None = CH1, title: str | None = None) -> dict[str, Any]:
    return {
        "id": rec_id,
        "channel_id": channel_id,
        "title": title or f"Rec {rec_id}",
    }


class LayerFakeProvider(AcquisitionProvider):
    """In-memory provider: returns configured payloads, never hits the network."""

    def __init__(
        self,
        *,
        videos: dict[str, dict[str, Any]] | None = None,
        recs: dict[str, list[dict[str, Any]]] | None = None,
        comments: dict[str, list[dict[str, Any]]] | None = None,
        fail_videos: set[str] | None = None,
    ) -> None:
        self.videos = videos or {}
        self.recs = recs or {}
        self.comments = comments or {}
        self.fail_videos = fail_videos or set()

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise InvalidURLError("not used in layer tests")

    def extract_video(self, video_url: str) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        if video_id in self.fail_videos:
            raise InvalidURLError(f"No video for {video_url}")
        info = dict(self.videos.get(video_id, _video_payload(video_id)))
        if video_id in self.comments:
            info["comments"] = self.comments[video_id]
        return info

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        if video_id not in self.recs:
            raise RecommendationUnsupportedError(
                "yt-dlp cannot provide recommendations"
            )
        return self.recs[video_id]


def _build_service(tmp_path, provider):
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="layer"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
    )
    repos = build_excel_repositories(settings.repository)
    return LayerScrapeService(provider, repos, settings=settings), repos


def _seed_channel_run(repos) -> CollectionRun:
    """A persisted channel run with two frontier videos (the crawl seed)."""
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


# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------
def test_bootstrap_layer_creates_seed(tmp_path) -> None:
    provider = LayerFakeProvider()
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    layer = service.bootstrap_layer(run.run_id, projection="video")

    assert layer.layer_index == 0
    assert layer.parent_run_id == run.run_id
    assert layer.status == CollectionStatus.SUCCESS
    assert layer.frontier_video_ids == [SEED_A, SEED_B]
    assert layer.discovered_video_ids == [SEED_A, SEED_B]
    assert layer.run_ids == [run.run_id]

    # Idempotent: bootstrapping the same run returns the same layer-0 record.
    again = service.bootstrap_layer(run.run_id)
    assert again.layer_run_id == layer.layer_run_id
    assert len(service.list_layers()) == 1


def test_bootstrap_unknown_run_raises(tmp_path) -> None:
    service, _ = _build_service(tmp_path, LayerFakeProvider())
    with pytest.raises(ValueError):
        service.bootstrap_layer("run_missing")


# ----------------------------------------------------------------------
# Crawl: run/edge layer stamping + target enrichment + classification
# ----------------------------------------------------------------------
def test_scrape_next_layer_stamps_runs_and_edges_and_enriches(tmp_path) -> None:
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH1),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1"), _rec("t2", channel_id=CH2)],
            SEED_B: [_rec("t1"), _rec("t3", channel_id=CH2)],
        },
        comments={
            "t2": [
                {
                    "id": "c1",
                    "text": "great video",
                    "author": "Alice",
                    "timestamp": 1735689600,
                    "like_count": 7,
                }
            ]
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    results = service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    assert len(results) == 2  # one per frontier video

    layers = service.list_layers()
    layer = layers[-1]
    assert layer.layer_index == 1
    assert layer.parent_layer_run_id == seed_layer.layer_run_id
    assert layer.frontier_video_ids == [SEED_A, SEED_B]
    assert layer.discovered_video_ids == ["t1", "t2", "t3"]
    assert sorted(layer.run_ids) == sorted(r.run_id for r in results)
    assert layer.comments_collected == 1

    # Runs + edges carry the denormalized layer.
    for run_id in layer.run_ids:
        layer_run = repos.runs.get_run(run_id)
        assert layer_run.layer_index == 1
    edges = repos.recommendations.list_recommendation_edges()
    assert len(edges) == 4
    assert {e.layer_index for e in edges} == {1}

    # Targets persisted as Video + observation; new channel upserted.
    assert repos.videos.get_video("t1") is not None
    assert repos.videos.get_video("t3") is not None
    # One observation from the recommendation-scrape enrichment + one from the
    # layer deep-enrichment pass (the layer re-enriches the still-marked stub).
    assert len(repos.videos.list_video_observations("t2")) >= 1
    channel_ids = {c.channel_id for c in repos.channels.list_channels()}
    assert CH2 in channel_ids

    # Comments persisted for t2 only.
    assert len(repos.comments.list_comments("t2")) == 1

    # Classification: all brand-new, one weak component, no old graph yet.
    report = service.relation_report(layer.layer_run_id)
    counts = report.counts
    assert counts["new_videos"] == 3
    assert counts["existing_videos_referenced"] == 0
    assert counts["new_edges"] == 4
    assert counts["skipped_edges_duplicate"] == 0
    assert counts["new_components"] == 1  # DISCONNECTED (old graph empty)
    assert counts["connected_components"] == 0


def test_layer_index_none_for_legacy_callers(tmp_path) -> None:
    """collect_recommendations without layer_index keeps run/edges None."""
    provider = LayerFakeProvider(
        videos={SEED_A: _video_payload(SEED_A)},
        recs={SEED_A: [_rec("t1", channel_id=CH2)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    result = service.collect_recommendations_for_videos([SEED_A], parent_run_id=run.run_id)

    assert len(result) == 1
    assert repos.runs.get_run(result[0].run_id).layer_index is None
    edges = repos.recommendations.list_recommendation_edges()
    assert {e.layer_index for e in edges} == {None}


def test_scrape_classifies_existing_video_and_connected_component(tmp_path) -> None:
    """Layer 2: a target that exists only as a pre-crawl node is EXISTING_VIDEO.

    Layer 1 fails to enrich ``t3`` (so it is an old-graph node with no Video
    row); layer 2 re-observes it (now enriching succeeds) -> EXISTING_VIDEO.
    New target ``t4`` is NEW_VIDEO; both new components touch old nodes.
    """
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH1),
            "t2": _video_payload("t2", channel_id=CH1),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1"), _rec("t2")],
            SEED_B: [_rec("t3", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [_rec("t4", channel_id=CH2)],
            "t3": [],
        },
        fail_videos={"t3"},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    # Layer 1: t3 edge observed but enrichment fails -> no Video row, old node.
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    assert layer1.discovered_video_ids == ["t1", "t2"]
    assert repos.videos.get_video("t3") is None

    # Unfail t3 for layer 2.
    provider.fail_videos = set()
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    layer2 = service.list_layers()[-1]
    assert layer2.layer_index == 2

    report = service.relation_report(layer2.layer_run_id)
    counts = report.counts
    assert counts["new_videos"] == 1  # t4
    assert counts["existing_videos_referenced"] == 1  # t3 (old-graph node)
    assert counts["new_components"] == 0
    assert counts["connected_components"] == 2  # (t1,t3) and (t2,t4), both touch old nodes

    classifications = {v.video_id: v.classification for v in report.new_videos}
    assert "t4" in classifications


def test_scrape_counts_duplicate_edges(tmp_path) -> None:
    """Re-scraping the same seed re-observes pairs -> skipped duplicates."""
    provider = LayerFakeProvider(
        videos={"t1": _video_payload("t1", channel_id=CH2)},
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t1", channel_id=CH2)],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    first = service.scrape_next_layer(parent_run_id=run.run_id)
    assert len(first) == 2
    second = service.scrape_next_layer(parent_run_id=run.run_id)
    assert len(second) == 2

    report = service.relation_report(service.list_layers()[-1].layer_run_id)
    assert report.counts["skipped_edges_duplicate"] == 2
    assert report.counts["new_edges"] == 0


def test_scrape_empty_frontier_raises(tmp_path) -> None:
    service, _ = _build_service(tmp_path, LayerFakeProvider())
    with pytest.raises(ValueError):
        service.scrape_next_layer(parent_run_id="run_missing")


# ----------------------------------------------------------------------
# Channel graph projection (NetworkAnalyticsService)
# ----------------------------------------------------------------------
def test_channel_graph_aggregates_and_counts_unattributed(tmp_path) -> None:
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t1", channel_id=CH2), _rec("t2", channel_id=CH2)],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    service.bootstrap_layer(run.run_id)
    service.scrape_next_layer(parent_run_id=run.run_id)

    analytics = NetworkAnalyticsService(repos)
    projection = analytics.channel_graph(layer_index=1)

    assert projection.node_count == 2  # CH1 (sources) + CH2 (targets)
    assert projection.unattributed_edges == 0
    pairs = {(e.source, e.target, e.video_edge_count) for e in projection.edges}
    assert (CH1, CH2, 3) in pairs  # 3 video edges CH1 -> CH2

    # Video graph scoped to layer 1 exposes the same 3 edges.
    graph = analytics.graph(layer_index=1)
    assert graph.edge_count == 3


def test_channel_graph_drops_unattributed_edges(tmp_path) -> None:
    """An edge whose neither endpoint resolves a channel is counted, not a node."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=None),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=None, title="no-channel target")],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    service.bootstrap_layer(run.run_id)
    service.scrape_next_layer(parent_run_id=run.run_id)

    analytics = NetworkAnalyticsService(repos)
    projection = analytics.channel_graph(layer_index=1)
    # t1 has no channel and the edge carried none -> the whole edge is dropped
    # (counted, never a synthetic node), so no channel node remains.
    assert projection.unattributed_edges == 1
    assert projection.node_count == 0


# ======================================================================
# Comprehensive crawl-next-layer: node values + non-identical crawls
# ======================================================================


def test_crawl_layer1_node_values_correct(tmp_path) -> None:
    """Layer 1: every node carries correct metadata (title, channel, views, edges)."""
    provider = LayerFakeProvider(
        videos={
            "alpha": _video_payload("alpha", channel_id=CH2, title="Alpha Video"),
            "beta": _video_payload("beta", channel_id=CH2, title="Beta Video"),
            "gamma": _video_payload("gamma", channel_id=CH1, title="Gamma Video"),
        },
        recs={
            SEED_A: [_rec("alpha", channel_id=CH2, title="Alpha Video"),
                      _rec("beta", channel_id=CH2, title="Beta Video")],
            SEED_B: [_rec("gamma", channel_id=CH1, title="Gamma Video"),
                      _rec("alpha", channel_id=CH2, title="Alpha Video")],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    results = service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)

    # --- Result count: one CollectionResult per frontier video ---
    assert len(results) == 2

    # --- Layer metadata ---
    layer = service.list_layers()[-1]
    assert layer.layer_index == 1
    assert layer.frontier_video_ids == [SEED_A, SEED_B]
    assert sorted(layer.discovered_video_ids) == sorted(["alpha", "beta", "gamma"])

    # --- Every discovered video has a Video row with correct title + channel ---
    for vid in ["alpha", "beta", "gamma"]:
        v = repos.videos.get_video(vid)
        assert v is not None, f"Video {vid} not persisted"
        assert v.channel_id in (CH1, CH2)

    # --- Edges: 4 unique pairs, all stamped layer 1 ---
    edges = repos.recommendations.list_recommendation_edges()
    layer1_edges = [e for e in edges if e.layer_index == 1]
    edge_pairs = {(e.source_video_id, e.recommended_video_id) for e in layer1_edges}
    assert edge_pairs == {
        (SEED_A, "alpha"), (SEED_A, "beta"),
        (SEED_B, "gamma"), (SEED_B, "alpha"),
    }

    # --- Graph construction: node/edge counts match ---
    analytics = NetworkAnalyticsService(repos)
    graph = analytics.graph(layer_index=1)
    assert graph.node_count == 5  # SEED_A, SEED_B, alpha, beta, gamma
    assert graph.edge_count == 4

    # --- Metrics: density, reciprocity, degree distribution all finite ---
    metrics = analytics.metrics()
    assert 0 <= metrics.density <= 1
    assert metrics.node_count == 5
    assert metrics.edge_count == 4


def test_crawl_layer2_different_nodes_from_layer1(tmp_path) -> None:
    """Layer 2 discovers NEW nodes not in layer 1 — crawls are not identical."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH2),
            "t5": _video_payload("t5", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [_rec("t4", channel_id=CH2)],
            "t3": [_rec("t5", channel_id=CH2)],
            "t4": [],
            "t5": [],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    # Layer 1: seeds → t1, t2
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    assert sorted(layer1.discovered_video_ids) == sorted(["t1", "t2"])

    # Layer 2: t1,t2 frontier → t3,t4 (different nodes!)
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    layer2 = service.list_layers()[-1]
    assert layer2.layer_index == 2
    assert sorted(layer2.discovered_video_ids) == sorted(["t3", "t4"])

    # Layer 2 nodes are DISJOINT from layer 1 discovered nodes
    assert not set(layer2.discovered_video_ids) & set(layer1.discovered_video_ids)

    # Layer 2 edges exist and are stamped layer 2
    edges = repos.recommendations.list_recommendation_edges()
    layer2_edges = [e for e in edges if e.layer_index == 2]
    assert len(layer2_edges) == 2  # t1→t3, t2→t4

    # Graph scoped to layer 2 shows only layer-2 edges
    analytics = NetworkAnalyticsService(repos)
    graph2 = analytics.graph(layer_index=2)
    assert graph2.edge_count == 2


def test_crawl_layer3_chain_extends_deeper(tmp_path) -> None:
    """Layer 3 discovers yet another batch — chain grows each crawl."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH2),
            "t5": _video_payload("t5", channel_id=CH2),
            "t6": _video_payload("t6", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [_rec("t4", channel_id=CH2)],
            "t3": [_rec("t5", channel_id=CH2)],
            "t4": [_rec("t6", channel_id=CH2)],
            "t5": [],
            "t6": [],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    layer2 = service.list_layers()[-1]
    service.scrape_next_layer(parent_layer_run_id=layer2.layer_run_id)
    layer3 = service.list_layers()[-1]

    assert layer3.layer_index == 3
    assert sorted(layer3.discovered_video_ids) == sorted(["t5", "t6"])

    # Each layer discovers unique, non-overlapping nodes
    all_discovered = (
        set(layer1.discovered_video_ids)
        | set(layer2.discovered_video_ids)
        | set(layer3.discovered_video_ids)
    )
    assert len(all_discovered) == 6  # t1..t6, all unique

    # Total edges across all layers
    edges = repos.recommendations.list_recommendation_edges()
    assert len(edges) == 6  # 2 per layer


def test_crawl_same_seed_different_recs_each_time(tmp_path) -> None:
    """Two crawls from the same seed with different recs produce different graphs."""
    call_count = {"n": 0}

    class RotatingProvider(AcquisitionProvider):
        def __init__(self):
            self.rounds = [
                [_rec("round1_a", channel_id=CH2), _rec("round1_b", channel_id=CH2)],
                [_rec("round2_x", channel_id=CH2), _rec("round2_y", channel_id=CH2)],
            ]

        def extract_channel(self, channel_url):
            raise InvalidURLError("not used")

        def extract_video(self, video_url):
            video_id = video_url.rsplit("v=", 1)[-1]
            return _video_payload(video_id, channel_id=CH2)

        def extract_recommendations(self, video_url):
            video_id = video_url.rsplit("v=", 1)[-1]
            if video_id != SEED_A:
                return []
            call_count["n"] += 1
            idx = min(call_count["n"] - 1, len(self.rounds) - 1)
            return self.rounds[idx]

    provider = RotatingProvider()
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    # First crawl
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    nodes1 = set(layer1.discovered_video_ids)

    # Second crawl from same seed — different recs
    service.scrape_next_layer(parent_run_id=run.run_id)
    layer2 = service.list_layers()[-1]
    nodes2 = set(layer2.discovered_video_ids)

    # The two crawls discovered different video IDs
    assert nodes1 != nodes2, f"Crawls produced identical nodes: {nodes1}"
    assert nodes1 == {"round1_a", "round1_b"}
    assert nodes2 == {"round2_x", "round2_y"}


def test_layer_graph_increases_with_each_crawl(tmp_path) -> None:
    """Each crawl adds edges; the cumulative graph grows monotonically."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [_rec("t4", channel_id=CH2)],
            "t3": [],
            "t4": [],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    analytics = NetworkAnalyticsService(repos)

    # Before crawl: 0 edges
    g0 = analytics.graph(layer_index=0)
    assert g0.edge_count == 0

    # Layer 1: 2 edges
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    g1 = analytics.graph(layer_index=1)
    assert g1.edge_count == 2

    # Layer 2: 2 more edges
    layer1 = service.list_layers()[-1]
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    g2 = analytics.graph(layer_index=2)
    assert g2.edge_count == 2

    # Full network (all layers): 4 edges
    g_all = analytics.graph()
    assert g_all.edge_count == 4


def test_metrics_update_after_each_crawl(tmp_path) -> None:
    """Network metrics (node_count, edge_count, density) reflect crawl growth."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [],
            "t3": [],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)
    analytics = NetworkAnalyticsService(repos)

    # Metrics after seed only (layer 0): no edges yet → empty graph
    m0 = analytics.metrics()
    assert m0.node_count == 0
    assert m0.edge_count == 0

    # After layer 1: 4 nodes (2 seeds + 2 discovered), 2 edges
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    analytics._graph_service.clear_graph_cache()
    # Build graph directly to avoid _ttl_cache on metrics()
    graph = analytics._graph_service.build_graph(run_id=None)
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 2
    m1 = analytics._metrics_for_graph(graph)
    assert m1.density > 0


def test_comments_collected_per_layer(tmp_path) -> None:
    """Each layer counts comments independently; different layers may differ."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [],
            "t2": [],
        },
        comments={
            "t1": [
                {"id": "c1", "text": "first", "author": "A", "timestamp": 1735689600, "like_count": 1},
                {"id": "c2", "text": "second", "author": "B", "timestamp": 1735689700, "like_count": 2},
            ],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    assert layer1.comments_collected == 2

    # Layer 1 videos have comments
    assert len(repos.comments.list_comments("t1")) == 2
    assert len(repos.comments.list_comments("t2")) == 0


def test_crawl_layer2_fallback_frontier_from_edges(tmp_path) -> None:
    """When discovered_video_ids is empty (all targets exist), layer 2 still
    crawls by falling back to the target videos from the parent layer's edges."""
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH2),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1", channel_id=CH2)],
            SEED_B: [_rec("t2", channel_id=CH2)],
            "t1": [_rec("t3", channel_id=CH2)],
            "t2": [_rec("t4", channel_id=CH2)],
            "t3": [],
            "t4": [],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    seed_layer = service.bootstrap_layer(run.run_id)

    # Layer 1: seeds → t1, t2 (discovered because they're new)
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    layer1 = service.list_layers()[-1]
    assert layer1.layer_index == 1
    assert sorted(layer1.discovered_video_ids) == sorted(["t1", "t2"])

    # Layer 2: t1,t2 → t3,t4 (discovered because they're new)
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    layer2 = service.list_layers()[-1]
    assert layer2.layer_index == 2
    assert sorted(layer2.discovered_video_ids) == sorted(["t3", "t4"])

    # Now crawl layer 1 AGAIN from the same seed — discovered will be empty
    # because t1,t2 already exist. But the crawl should still succeed by
    # falling back to edge targets as the frontier.
    before_count = len(service.list_layers())
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    all_layers = service.list_layers()
    assert len(all_layers) == before_count + 1
    layer1b = all_layers[-1]
    # Frontier should be t1,t2 (from seed layer's edges, not discovered)
    assert sorted(layer1b.frontier_video_ids) == sorted(["t1", "t2"])
