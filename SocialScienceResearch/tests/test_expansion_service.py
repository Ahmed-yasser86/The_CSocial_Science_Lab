"""Network-expansion service tests (docs/network_expansion_scrape_all.md §8).

Uses a fake acquisition provider (no network): seeds a channel run + videos,
then exercises one-hop expansion (per-video and scrape-all), the filter
semantics (top-N truncation, dedupe, comment criteria, only_new_targets), the
auto-created Project, per-video stats, and the expansion/crawl listing split.
"""

from __future__ import annotations

from typing import Any

import pytest

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    ChannelExtract,
)
from SocialScienceResearch.acquisition.errors import InvalidURLError
from SocialScienceResearch.acquisition.normalization import _url_for_video
from SocialScienceResearch.config.settings import (
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.layer_models import ScrapeFilters
from SocialScienceResearch.domain.models import CollectionRun, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services.project_service import ProjectService
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

CH1 = "UCsource0000000000000000000"
CH2 = "UCtarget0000000000000000000"

SEED_A = "seed_a"
SEED_B = "seed_b"

T1 = "t1"
T2 = "t2"
T3 = "t3"


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
        "description": "expansion target",
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


def _comment(comment_id: str, *, likes: int = 5, ts: int = 1735689600) -> dict[str, Any]:
    return {
        "id": comment_id,
        "text": f"comment {comment_id}",
        "author": "Alice",
        "timestamp": ts,
        "like_count": likes,
    }


class ExpansionFakeProvider(AcquisitionProvider):
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
        raise InvalidURLError("not used in expansion tests")

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
        return self.recs.get(video_id, [])


def _build_service(tmp_path, provider):
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="expansion"),
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


def _default_provider() -> ExpansionFakeProvider:
    return ExpansionFakeProvider(
        videos={
            T1: _video_payload(T1, channel_id=CH1),
            T2: _video_payload(T2, channel_id=CH2),
            T3: _video_payload(T3, channel_id=CH2),
        },
        recs={
            SEED_A: [_rec(T1), _rec(T2, channel_id=CH2)],
            SEED_B: [_rec(T1), _rec(T3, channel_id=CH2)],
        },
    )


# ----------------------------------------------------------------------
# Per-video expansion
# ----------------------------------------------------------------------
def test_expand_video_creates_anchor_run_and_project(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    run = _seed_channel_run(repos)

    layer = service.expand_video(SEED_A, filters=ScrapeFilters())

    assert layer.status == CollectionStatus.SUCCESS
    assert layer.layer_index == 0
    assert layer.frontier_video_ids == [SEED_A]
    assert layer.parent_run_id == run.run_id
    assert len(layer.run_ids) == 1
    assert layer.config_json["expansion"]["kind"] == "video"
    assert layer.config_json["expansion"]["filters"]["projection"] == "video"
    assert set(layer.discovered_video_ids) == {T1, T2}

    # Edges were persisted under the expansion run.
    edges = repos.recommendations.list_recommendation_edges()
    assert {e.collection_run_id for e in edges} == set(layer.run_ids)
    assert {e.source_video_id for e in edges} == {SEED_A}

    # Auto-created Project with a dataset-group item.
    projects = ProjectService(repos).list_projects()
    assert len(projects) == 1
    assert "Network expansion" in projects[0].name
    items = repos.project_items.list_items(projects[0].project_id)
    assert len(items) == 1
    assert items[0].item_type == "dataset_group"
    assert layer.config_json["expansion"]["project_id"] == projects[0].project_id

    # The anchor is NOT a crawl layer.
    assert service.get_layer(layer.layer_run_id) is None
    assert [a.layer_run_id for a in service.list_expansions()] == [layer.layer_run_id]


def test_expand_video_source_not_persisted_is_extracted(tmp_path) -> None:
    """A recommended target that exists only as a graph node (no Video row)
    is extracted + persisted by the single-video expansion instead of failing
    with 'Video not found' (the per-video scrape bug)."""
    provider = ExpansionFakeProvider(
        videos={
            T1: _video_payload(T1, channel_id=CH1),
            T2: _video_payload(T2, channel_id=CH2),
        },
        recs={T2: [_rec(T1, channel_id=CH1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    _seed_channel_run(repos)
    # T2 is a recommendation target in the graph but never a Video row.
    assert repos.videos.get_video(T2) is None

    layer = service.expand_video(T2, filters=ScrapeFilters())

    assert layer.status == CollectionStatus.SUCCESS
    assert repos.videos.get_video(T2) is not None
    edges = repos.recommendations.list_recommendation_edges()
    assert {e.source_video_id for e in edges} == {T2}
    assert {e.recommended_video_id for e in edges} == {T1}


# ----------------------------------------------------------------------
# Scrape-all expansion
# ----------------------------------------------------------------------
def test_expand_all_videos_expands_the_slice(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    run = _seed_channel_run(repos)

    layer = service.expand_all_videos(
        [SEED_A, SEED_B], filters=ScrapeFilters(), parent_run_id=run.run_id
    )

    assert layer.config_json["expansion"]["kind"] == "all"
    assert set(layer.frontier_video_ids) == {SEED_A, SEED_B}
    assert len(layer.run_ids) == 2
    assert set(layer.discovered_video_ids) == {T1, T2, T3}
    edges = repos.recommendations.list_recommendation_edges()
    assert len(edges) == 4

    projects = ProjectService(repos).list_projects()
    assert len(projects) == 1
    assert "2 videos" in projects[0].name


def test_expand_all_videos_resolves_channel_run_slice(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    run = _seed_channel_run(repos)

    layer = service.expand_all_videos([], filters=ScrapeFilters(), parent_run_id=run.run_id)

    assert set(layer.frontier_video_ids) == {SEED_A, SEED_B}
    assert len(layer.run_ids) == 2
    assert set(layer.discovered_video_ids) == {T1, T2, T3}


def test_expand_all_source_video_not_persisted_is_extracted(tmp_path) -> None:
    """A frontier video that exists only as a graph node (no Video row) is
    extracted + persisted by the bulk scrape instead of failing with
    'Source video is not persisted' (the channel-graph scrape-all bug)."""
    provider = ExpansionFakeProvider(
        videos={
            T1: _video_payload(T1, channel_id=CH1),
            T2: _video_payload(T2, channel_id=CH2),
        },
        recs={
            SEED_A: [_rec(T1), _rec(T2, channel_id=CH2)],
            SEED_B: [_rec(T2, channel_id=CH2)],
            T2: [_rec(T1, channel_id=CH1)],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    # A video that is a recommendation target (graph node) but never a Video row.
    assert repos.videos.get_video(T2) is None

    layer = service.expand_all_videos(
        [SEED_A, T2], filters=ScrapeFilters(), parent_run_id=run.run_id
    )

    assert layer.status == CollectionStatus.SUCCESS
    assert repos.videos.get_video(T2) is not None
    edges = repos.recommendations.list_recommendation_edges()
    assert {e.source_video_id for e in edges} == {SEED_A, T2}
    assert {e.recommended_video_id for e in edges} == {T1, T2}


def test_expand_all_requires_scope(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    _seed_channel_run(repos)
    with pytest.raises(ValueError):
        service.expand_all_videos([], filters=ScrapeFilters(), parent_run_id=None)


def test_expand_all_videos_unknown_run_raises(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    _seed_channel_run(repos)
    with pytest.raises(ValueError):
        service.expand_all_videos([], filters=ScrapeFilters(), parent_run_id="run_nope")


# ----------------------------------------------------------------------
# Filter semantics
# ----------------------------------------------------------------------
def test_max_recommendations_per_video_truncates_top_n(tmp_path) -> None:
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1), T2: _video_payload(T2), T3: _video_payload(T3)},
        recs={SEED_A: [_rec(T1), _rec(T2), _rec(T3)]},
    )
    service, repos = _build_service(tmp_path, provider)
    _seed_channel_run(repos)

    layer = service.expand_video(
        SEED_A, filters=ScrapeFilters(max_recommendations_per_video=2)
    )

    edges = repos.recommendations.list_recommendation_edges()
    assert len(edges) == 2
    assert sorted(e.recommended_video_id for e in edges) == [T1, T2]
    assert [e.position for e in edges] == [0, 1]
    assert len(layer.discovered_video_ids) == 2


def test_dedupe_skips_edges_observed_by_the_parent_run(tmp_path) -> None:
    """dedupe skips edges already observed in the parent run (the scope)."""
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    # The "slice" run already observed seed_a->t1.
    results = service.collect_recommendations_for_videos(
        [SEED_A], parent_run_id=run.run_id
    )
    slice_run_id = results[0].run_id
    assert len(repos.recommendations.list_recommendation_edges()) == 1

    layer = service.expand_all_videos(
        [SEED_A],
        filters=ScrapeFilters(dedupe=True),
        parent_run_id=slice_run_id,
    )

    # The edge is not re-persisted: the anchor run has zero new edges.
    assert len(repos.recommendations.list_recommendation_edges()) == 1
    edges = [
        e
        for e in repos.recommendations.list_recommendation_edges()
        if e.collection_run_id in layer.run_ids
    ]
    assert edges == []


def test_comment_filters_are_applied(tmp_path) -> None:
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
        comments={
            T1: [
                _comment("c_high", likes=50, ts=1735689600),
                _comment("c_low", likes=1, ts=1735689600),
                _comment("c_early", likes=10, ts=1735603200),
            ]
        },
    )
    service, repos = _build_service(tmp_path, provider)
    _seed_channel_run(repos)

    layer = service.expand_video(
        SEED_A,
        filters=ScrapeFilters(
            collect_comments=True,
            comment_min_likes=5,
            comment_date_from="2025-01-01T00:00:00",
        ),
    )

    stored = repos.comments.list_comments(T1)
    # c_high (2025-01-01, 50 likes) passes; c_early (2024-12-31) is before the
    # window; c_low (1 like) is below the min-likes threshold.
    assert {c.comment_id for c in stored} == {"c_high"}
    assert layer.comments_collected == 1


def test_max_comments_per_video_caps(tmp_path) -> None:
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
        comments={T1: [_comment("c1"), _comment("c2"), _comment("c3")]},
    )
    service, repos = _build_service(tmp_path, provider)
    _seed_channel_run(repos)

    layer = service.expand_video(
        SEED_A,
        filters=ScrapeFilters(collect_comments=True, max_comments_per_video=2),
    )

    assert len(repos.comments.list_comments(T1)) == 2
    assert layer.comments_collected == 2


def test_only_new_targets_skips_preexisting_videos(tmp_path) -> None:
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)
    # T1 already exists in the corpus before the expansion.
    repos.videos.upsert_video(
        Video(
            video_id=T1,
            url=_url_for_video(T1),
            channel_id=CH1,
            title="Existing T1",
            first_observed_run_id=run.run_id,
        )
    )

    layer = service.expand_video(
        SEED_A, filters=ScrapeFilters(only_new_targets=True)
    )

    assert layer.discovered_video_ids == []
    assert layer.comments_collected == 0

    layer2 = service.expand_video(
        SEED_A, filters=ScrapeFilters(only_new_targets=False)
    )
    assert set(layer2.discovered_video_ids) == {T1}


def test_concurrency_is_threaded(tmp_path) -> None:
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)], SEED_B: [_rec(T1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    layer = service.expand_all_videos(
        [SEED_A, SEED_B],
        filters=ScrapeFilters(concurrency=2),
        parent_run_id=run.run_id,
    )

    assert len(layer.run_ids) == 2
    assert set(layer.discovered_video_ids) == {T1}


# ----------------------------------------------------------------------
# Listings + stats
# ----------------------------------------------------------------------
def test_list_expansions_excludes_crawl_layers(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    run = _seed_channel_run(repos)

    seed_layer = service.bootstrap_layer(run.run_id)
    service.scrape_next_layer(parent_layer_run_id=seed_layer.layer_run_id)
    expansion = service.expand_video(SEED_A, filters=ScrapeFilters())

    actions = service.list_expansions()
    assert [a.layer_run_id for a in actions] == [expansion.layer_run_id]
    layers = service.list_layers()
    assert all(l.config_json.get("expansion") is None for l in layers)
    assert service.get_expansion(seed_layer.layer_run_id) is None


def test_expansion_stats_shape_and_sorting(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    _seed_channel_run(repos)

    layer = service.expand_all_videos(
        [SEED_A, SEED_B], filters=ScrapeFilters(), parent_run_id=None
    )
    stats = service.expansion_stats(layer)

    assert stats.action.action_id == layer.layer_run_id
    assert stats.action.project_id is not None
    assert stats.overall.node_count >= 3
    assert stats.overall.edge_count == 4
    assert stats.overall.source_count == 2
    assert stats.overall.channel_count == 2
    assert stats.overall.comment_count == 0

    # Per-video rows sorted by recommendation_count desc.
    counts = [row.recommendation_count for row in stats.videos]
    assert counts == sorted(counts, reverse=True)
    by_id = {row.video_id: row for row in stats.videos}
    assert by_id[SEED_A].new_targets == 2
    assert by_id[SEED_B].new_targets == 2
    assert stats.overall.avg_out_degree == pytest.approx(4 / stats.overall.node_count)


def test_expansion_action_payload_is_serializable(tmp_path) -> None:
    service, repos = _build_service(tmp_path, _default_provider())
    _seed_channel_run(repos)

    layer = service.expand_video(SEED_A, filters=ScrapeFilters())
    payload = service.expansion_payload(layer)

    assert payload.kind == "video"
    assert payload.status == "success"
    assert payload.projection == "video"
    assert payload.video_ids == [SEED_A]
    assert payload.run_ids == layer.run_ids
    assert payload.filters["projection"] == "video"
    assert payload.project_id is not None
    dump = payload.model_dump()
    assert dump["action_id"] == layer.layer_run_id


def test_resolve_slice_includes_target_only_nodes(tmp_path) -> None:
    """Scrape-all must expand target-only nodes, not just run sources.

    A node may appear in a run's graph snapshot only as a recommended target
    (connected from 2-3 sources) without ever having been scraped as a source.
    Expanding only the sources would leave it permanently un-scraped.
    """
    provider = ExpansionFakeProvider(
        videos={
            T1: _video_payload(T1),
            T2: _video_payload(T2),
            T3: _video_payload(T3),
        },
        recs={
            SEED_A: [_rec(T1)],
            SEED_B: [_rec(T2)],
            T1: [_rec(T3)],
        },
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    # Seed the slice run with edges seed_a->t1. T1 is a target in that edge but
    # its OWN recommendations (T1->T3) were never scraped, and T3 appears
    # nowhere as a source in this run.
    results = service.collect_recommendations_for_videos(
        [SEED_A, SEED_B], parent_run_id=run.run_id
    )
    slice_run_id = results[0].run_id
    slice_edges = [
        e
        for e in repos.recommendations.list_recommendation_edges()
        if e.collection_run_id == slice_run_id
    ]
    assert {(e.source_video_id, e.recommended_video_id) for e in slice_edges} == {
        (SEED_A, T1)
    }

    # Resolving the slice from the run's snapshot includes the TARGET node T1,
    # not just the source seed_a.
    scope = service._resolve_slice([], slice_run_id)
    assert set(scope) == {SEED_A, T1}

    layer = service.expand_all_videos(
        [],
        filters=ScrapeFilters(dedupe=True),
        parent_run_id=slice_run_id,
    )
    assert set(layer.frontier_video_ids) == {SEED_A, T1}
    # T1's feed (T1->T3) was scraped during the expansion: the target-only node
    # that was never a source in the snapshot still gets its recommendations.
    t1_edges = [
        e
        for e in repos.recommendations.list_recommendation_edges(source_video_id=T1)
    ]
    assert any(e.recommended_video_id == T3 for e in t1_edges)


def test_recommendations_scraped_flag_is_set(tmp_path) -> None:
    """After a scrape, the source video is flagged as recommendations-scraped."""
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    assert repos.videos.get_video(SEED_A).recommendations_scraped is False

    service.collect_recommendations_for_videos(
        [SEED_A], parent_run_id=run.run_id
    )

    assert repos.videos.get_video(SEED_A).recommendations_scraped is True


def test_dedupe_all_history_skips_edges_seen_in_any_run(tmp_path) -> None:
    """dedupe_all_history skips edges observed in ANY earlier run."""
    provider = ExpansionFakeProvider(
        videos={T1: _video_payload(T1)},
        recs={SEED_A: [_rec(T1)]},
    )
    service, repos = _build_service(tmp_path, provider)
    run = _seed_channel_run(repos)

    # First scrape persists seed_a->t1 under its own run.
    results = service.collect_recommendations_for_videos(
        [SEED_A], parent_run_id=run.run_id
    )
    assert len(repos.recommendations.list_recommendation_edges()) == 1

    # Re-scrape with dedupe_all_history: the edge already exists somewhere, so
    # it must NOT be re-persisted under a fresh run.
    results2 = service.collect_recommendations_for_videos(
        [SEED_A],
        parent_run_id=run.run_id,
        dedupe_all_history=True,
    )
    assert len(repos.recommendations.list_recommendation_edges()) == 1

    # Without dedupe_all_history the same edge is re-observed (temporal slice).
    service.collect_recommendations_for_videos(
        [SEED_A], parent_run_id=run.run_id
    )
    assert len(repos.recommendations.list_recommendation_edges()) == 2