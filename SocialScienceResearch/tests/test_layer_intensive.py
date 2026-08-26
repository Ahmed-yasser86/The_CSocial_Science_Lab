"""Intensive Layer-crawl integration tests.

Drives the full bootstrap -> crawl -> relations -> graph pipeline with a fake
provider (no network) to verify the Layer tab behaves correctly end to end:

* Seed (Layer 0) frontier is NON-ZERO for a channel run and for a
  recommendation run that has edges.
* "Seed is always zero" only happens for a run that genuinely has no
  videos/edges - that case is documented here so the UI can warn about it.
* Crawling Layer 0 -> Layer 1 -> Layer 2 increments layers and adds edges.
* The NewRelationsReport and the served layer graph reflect the crawl.

Run with: pytest tests/test_layer_intensive.py -v
"""

from __future__ import annotations

from typing import Any

from SocialScienceResearch.acquisition.base import AcquisitionProvider
from SocialScienceResearch.acquisition.errors import InvalidURLError
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.models import (
    CollectionRun,
    RecommendationObservation,
    Video,
)
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

    def extract_channel(self, channel_url: str):
        raise InvalidURLError("not used in layer tests")

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
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
            raise InvalidURLError("no recs")
        return self.recs[video_id]


def _build_service(tmp_path, provider):
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="layer"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
    )
    repos = build_excel_repositories(settings.repository)
    return LayerScrapeService(provider, repos, settings=settings), repos


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


def _seed_recommendation_run(repos, *, with_edges: bool) -> CollectionRun:
    run = CollectionRun(
        run_id=new_run_id(),
        run_type=RunType.RECOMMENDATION,
        target_url=f"https://www.youtube.com/watch?v={SEED_A}",
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )
    repos.runs.create_run(run)
    if with_edges:
        for target in ("t1", "t2"):
            repos.recommendations.save_recommendation(
                RecommendationObservation(
                    observation_id=f"rec_{SEED_A}_{target}_{run.run_id}",
                    collection_run_id=run.run_id,
                    source_video_id=SEED_A,
                    recommended_video_id=target,
                    position=0,
                    status=RecommendationStatus.OBSERVED,
                )
            )
    return run


def _analytics(repos):
    return NetworkAnalyticsService(repos)


# ----------------------------------------------------------------------
# Seed frontier must be non-zero for a real run
# ----------------------------------------------------------------------
def test_channel_seed_frontier_is_nonzero(tmp_path) -> None:
    provider = LayerFakeProvider()
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    layer = service.bootstrap_layer(run.run_id)

    assert layer.layer_index == 0
    assert layer.frontier_video_ids == [SEED_A, SEED_B]
    assert len(layer.frontier_video_ids) > 0

    analytics = _analytics(repos)
    graph = analytics.graph(run_id=run.run_id)
    node_ids = {n.video_id for n in graph.nodes}
    assert SEED_A in node_ids and SEED_B in node_ids


def test_recommendation_seed_with_edges_is_nonzero(tmp_path) -> None:
    provider = LayerFakeProvider()
    service, repos = _build_service(tmp_path, provider)
    run = _seed_recommendation_run(repos, with_edges=True)

    layer = service.bootstrap_layer(run.run_id)

    assert layer.frontier_video_ids == [SEED_A]
    assert len(layer.frontier_video_ids) > 0


def test_recommendation_seed_without_edges_is_empty(tmp_path) -> None:
    """Documents the 'seed is always zero' case: a run with no content."""
    provider = LayerFakeProvider()
    service, repos = _build_service(tmp_path, provider)
    run = _seed_recommendation_run(repos, with_edges=False)

    layer = service.bootstrap_layer(run.run_id)

    assert layer.frontier_video_ids == []
    assert len(layer.frontier_video_ids) == 0  # <-- this is the user's "zero"


# ----------------------------------------------------------------------
# Full crawl pipeline L0 -> L1 -> L2
# ----------------------------------------------------------------------
def test_full_crawl_pipeline_increments_layers_and_edges(tmp_path) -> None:
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH1),
            "t2": _video_payload("t2", channel_id=CH2),
            "t3": _video_payload("t3", channel_id=CH2),
            "t4": _video_payload("t4", channel_id=CH1),
        },
        recs={
            SEED_A: [_rec("t1"), _rec("t2", channel_id=CH2)],
            SEED_B: [_rec("t1"), _rec("t3", channel_id=CH2)],
            "t1": [_rec("t4")],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    seed_run = _seed_channel_run(repos)
    layer0 = service.bootstrap_layer(seed_run.run_id)
    assert layer0.layer_index == 0
    assert len(layer0.frontier_video_ids) == 2

    service.scrape_next_layer(parent_layer_run_id=layer0.layer_run_id)
    layers = service.list_layers()
    layer1 = [l for l in layers if l.layer_index == 1][0]
    report1 = service.relation_report(layer1.layer_run_id)
    assert report1.counts["new_edges"] > 0
    assert len(layer1.frontier_video_ids) > 0

    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    layers = service.list_layers()
    layer2 = [l for l in layers if l.layer_index == 2]
    assert len(layer2) == 1
    assert len(layer2[0].run_ids) > 0

    indices = [l.layer_index for l in layers]
    assert sorted(indices) == sorted(set(indices))


def test_relation_report_counts_reflect_crawl(tmp_path) -> None:
    provider = LayerFakeProvider(
        videos={
            "t1": _video_payload("t1", channel_id=CH1),
            "t2": _video_payload("t2", channel_id=CH2),
        },
        recs={
            SEED_A: [_rec("t1"), _rec("t2", channel_id=CH2)],
            SEED_B: [_rec("t1")],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    seed_run = _seed_channel_run(repos)
    layer0 = service.bootstrap_layer(seed_run.run_id)
    service.scrape_next_layer(parent_layer_run_id=layer0.layer_run_id)
    layer1 = [l for l in service.list_layers() if l.layer_index == 1][0]
    report = service.relation_report(layer1.layer_run_id)

    assert report.counts["new_edges"] == 3
    assert report.counts["new_videos"] == 2
    assert len(report.new_videos) == 2


def test_relation_report_stable_after_future_layer_crawled(tmp_path) -> None:
    """Regression: a layer's "what was added" report must not change once a
    later layer in the same family is crawled.

    Layer 1 produces a single disconnected component {SEED_A, SEED_B, X, Y}.
    Layer 2 then scrapes X and discovers a brand-new node t9 (edge X->t9).
    Before the fix, layer 1's baseline snapshot included layer 2's edges/nodes,
    so t9 (and X) leaked into layer 1's ``old_nodes`` and flipped layer 1's
    component to "connected" - making layer 1 vs layer 2 matrices contradict.
    """
    provider = LayerFakeProvider(
        videos={
            "X": _video_payload("X", channel_id=CH1),
            "Y": _video_payload("Y", channel_id=CH2),
            "t9": _video_payload("t9", channel_id=CH1),
        },
        recs={
            SEED_A: [_rec("X"), _rec("Y", channel_id=CH2)],
            SEED_B: [_rec("X", channel_id=CH1), _rec("Y", channel_id=CH2)],
            "X": [_rec("t9", channel_id=CH1)],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    seed_run = _seed_channel_run(repos)
    layer0 = service.bootstrap_layer(seed_run.run_id)
    service.scrape_next_layer(parent_layer_run_id=layer0.layer_run_id)
    layer1 = [l for l in service.list_layers() if l.layer_index == 1][0]

    # Capture layer 1's report with no later layers present.
    report_before = service.relation_report(layer1.layer_run_id)
    assert report_before.counts["new_components"] == 1
    assert report_before.counts["connected_components"] == 0

    # Crawl the future layer (layer 2). It discovers t9 via X->t9.
    service.scrape_next_layer(parent_layer_run_id=layer1.layer_run_id)
    report_after = service.relation_report(layer1.layer_run_id)

    # Layer 1's contribution must be identical regardless of layer 2's existence.
    assert report_after.counts["new_components"] == report_before.counts["new_components"]
    assert report_after.counts["connected_components"] == report_before.counts["connected_components"]
    assert report_after.counts["new_components"] == 1
    assert report_after.counts["connected_components"] == 0
