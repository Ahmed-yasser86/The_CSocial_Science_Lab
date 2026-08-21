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
