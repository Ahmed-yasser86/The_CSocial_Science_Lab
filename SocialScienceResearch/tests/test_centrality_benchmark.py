"""Centrality / community benchmark against Zachary's Karate Club (Phase 2.2).

Seeds the canonical 34-node / 78-edge karate club as a directed recommendation
network (each undirected club edge stored in both directions so the directed
graph is strongly connected and eigenvector centrality is well defined) and
verifies :meth:`NetworkAnalyticsService.centralities` against networkx reference
values plus well-documented karate-club facts (the instructor node 0 is the
most central; the two faction leaders 0 and 33 sit in different communities).
"""

from __future__ import annotations

import networkx as nx
import pytest
from SocialScienceResearch.config.settings import RepositorySettings
from SocialScienceResearch.domain.enums import RecommendationStatus, RunType
from SocialScienceResearch.domain.models import Channel, CollectionRun, RecommendationObservation, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.network_analytics_service import NetworkAnalyticsService
from SocialScienceResearch.utils.idgen import utcnow

CHANNEL = "UC_KC"


def _seed_karate(repos) -> None:
    club = nx.karate_club_graph()
    repos.channels.upsert_channel(
        Channel(channel_id=CHANNEL, url="https://x", title="KC", first_observed_run_id="kc")
    )
    for i in club.nodes():
        repos.videos.upsert_video(
            Video(
                video_id=str(i),
                url=f"https://x/{i}",
                channel_id=CHANNEL,
                title=f"Node {i}",
                first_observed_run_id="kc",
            )
        )
    # Store each club edge in both directions so the directed slice is strongly
    # connected (stable eigenvector centrality) and degree is symmetric.
    for (u, v) in club.edges():
        for s, t in ((u, v), (v, u)):
            repos.recommendations.save_recommendation(
                RecommendationObservation(
                    observation_id=f"o_{s}_{t}",
                    collection_run_id="kc",
                    source_video_id=str(s),
                    recommended_video_id=str(t),
                    position=0,
                    status=RecommendationStatus.OBSERVED,
                    channel_id=CHANNEL,
                    title=f"{s}->{t}",
                )
            )
    repos.runs.create_run(
        CollectionRun(
            run_id="kc", run_type=RunType.VIDEO, target_url="https://x",
            started_at=utcnow(), status="success",
        )
    )


def _reference_digraph() -> nx.DiGraph:
    club = nx.karate_club_graph()
    G = nx.DiGraph()
    for (u, v) in club.edges():
        G.add_edge(str(u), str(v))
        G.add_edge(str(v), str(u))
    return G


def test_centrality_matches_networkx_reference(tmp_path) -> None:
    repos = build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="kc"))
    _seed_karate(repos)
    svc = NetworkAnalyticsService(repos)
    got = svc.centralities()

    G = _reference_digraph()
    ref_deg = nx.degree_centrality(G)
    ref_clo = nx.closeness_centrality(G)
    try:
        ref_eig = nx.eigenvector_centrality(G, max_iter=1000)
    except nx.PowerIterationFailedConvergence:
        ref_eig = {n: 0.0 for n in G.nodes}
    ref_bet = nx.betweenness_centrality(G)

    assert set(got) == set(G.nodes)
    for nid in G.nodes:
        assert got[nid]["degree"] == pytest.approx(ref_deg[nid], rel=1e-6), nid
        assert got[nid]["closeness"] == pytest.approx(ref_clo[nid], rel=1e-6), nid
        assert got[nid]["eigenvector"] == pytest.approx(ref_eig[nid], rel=1e-6), nid
        assert got[nid]["betweenness"] == pytest.approx(ref_bet[nid], rel=1e-9), nid


def test_karate_club_known_facts(tmp_path) -> None:
    repos = build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="kc"))
    _seed_karate(repos)
    svc = NetworkAnalyticsService(repos)
    got = svc.centralities()

    deg = {n: c["degree"] for n, c in got.items()}
    bet = {n: c["betweenness"] for n, c in got.items()}
    # The administrator (node 33) is the highest-degree actor; the instructor
    # (node 0) is the highest-betweenness actor - the two karate-club leaders.
    assert deg["33"] == max(deg.values())
    assert bet["0"] == max(bet.values())
    # The two faction leaders split the club into different communities.
    assert got["0"]["community_id"] != got["33"]["community_id"]
    communities = {c["community_id"] for c in got.values()}
    assert len(communities) >= 3


def test_community_count_matches_modularity_benchmark(tmp_path) -> None:
    repos = build_excel_repositories(RepositorySettings(data_dir=str(tmp_path), dataset_name="kc"))
    _seed_karate(repos)
    svc = NetworkAnalyticsService(repos)
    metrics = svc.metrics(run_id="kc")
    # Greedy modularity on the (connected) karate club yields 3-4 factions.
    assert metrics.community_count >= 3
    assert metrics.modularity is not None and metrics.modularity > 0.3


# ---------------------------------------------------------------------------
# N0: the /network/centralities endpoint exposes the same battery.
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402

from SocialScienceResearch.api import create_app  # noqa: E402
from SocialScienceResearch.config.settings import (  # noqa: E402
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)

PREFIX = "/api/v1/social-science"


def _settings(tmp_path):
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path), dataset_name="kc", backend="excel"
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _client_with_karate(tmp_path):
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="kc")
    )
    _seed_karate(repos)
    app = create_app(_settings(tmp_path))
    # Pin the app to the seeded excel repos and disable the active-workspace
    # sync middleware so the test slice is exactly what we seeded (the live
    # app would otherwise route to the persisted SQL workspace).
    app.state.services["repos"] = repos
    app.state.workspace_runtime.sync = lambda app: None
    return TestClient(app), repos


def test_centralities_endpoint_matches_service(tmp_path) -> None:
    client, repos = _client_with_karate(tmp_path)
    resp = client.get(f"{PREFIX}/network/centralities?run_id=kc")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) >= {"nodes", "algorithm", "computed_at"}
    assert body["algorithm"] == "networkx"
    assert set(body["nodes"]) == {str(i) for i in range(34)}

    # The endpoint must describe exactly what the service computes.
    svc = NetworkAnalyticsService(repos)
    assert body["nodes"] == svc.centralities(run_id="kc")


def test_centralities_endpoint_rejects_bad_projection(tmp_path) -> None:
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(f"{PREFIX}/network/centralities?run_id=kc&projection=bogus")
    assert resp.status_code == 400
