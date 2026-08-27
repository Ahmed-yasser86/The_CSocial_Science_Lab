"""Tests for the audience (commenter) network family -- N2 / WS7.

Covers the commenter projection's co-comment weights, parity with the existing
:class:`CommenterOverlapService` commenter counts, louvain communities +
centralities, the export serializers (reused from the recommendation engine),
and the three WS7 endpoints (graph / metrics / export) including 400 contract
paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.models import Channel, Comment, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.commenter_network_service import (
    CommenterNetworkService,
)
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapService,
)
from SocialScienceResearch.services.weight_spec import WeightSpecError

PREFIX = "/api/v1/social-science"
T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="cn"),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="cn")
    )
    for vid, cid in (("v1", "UC1"), ("v2", "UC2")):
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id=cid,
                title=f"Video {vid}",
                first_observed_run_id="r_cn",
            )
        )
    for cid in ("UC1", "UC2"):
        repos.channels.upsert_channel(
            Channel(
                channel_id=cid,
                url=f"https://www.youtube.com/channel/{cid}",
                title=f"Channel {cid}",
                first_observed_run_id="r_cn",
            )
        )
    comments = [
        Comment(comment_id="a1", video_id="v1", author_id="UCid_alice",
                author_name="Alice", comment_text="on v1", published_at=T0,
                first_observed_run_id="r_cn"),
        Comment(comment_id="a2", video_id="v2", author_id="UCid_alice",
                author_name="Alice", comment_text="on v2", published_at=T0,
                first_observed_run_id="r_cn"),
        Comment(comment_id="b1", video_id="v1", author_id="UCid_bob",
                author_name="Bob", comment_text="bob v1", published_at=T0,
                first_observed_run_id="r_cn"),
        Comment(comment_id="c1", video_id="v1", author_name="Carol",
                comment_text="carol v1", published_at=T0,
                first_observed_run_id="r_cn"),
    ]
    for c in comments:
        repos.comments.upsert_comment(c)
    repos.store.close()


def _repos(tmp_path):
    _seed(tmp_path)
    return build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="cn")
    )


@pytest.fixture
def client(tmp_path):
    _seed(tmp_path)
    return TestClient(create_app(_settings(tmp_path)))


# ----------------------------------------------------------------------
# Service: commenter projection weights
# ----------------------------------------------------------------------
def test_commenter_projection_jaccard_weights(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    g = svc.graph(video_ids=["v1", "v2"], projection="commenter")
    # alice={v1,v2}, bob={v1}, carol={v1}
    #   alice-bob: shared 1 / union 2 = 0.5
    #   alice-carol: shared 1 / union 2 = 0.5
    #   bob-carol: shared 1 / union 1 = 1.0
    pairs = {(min(e.source, e.target), max(e.source, e.target)): e.weight for e in g.edges}
    assert pairs[tuple(sorted(("UCid_alice", "UCid_bob")))] == pytest.approx(0.5)
    assert pairs[tuple(sorted(("UCid_alice", "Carol")))] == pytest.approx(0.5)
    assert pairs[tuple(sorted(("UCid_bob", "Carol")))] == pytest.approx(1.0)
    # Every commenter node carries a community assignment + degree.
    for n in g.nodes:
        assert n.kind == "commenter"
        assert n.community_id is not None
        assert n.degree >= 1


def test_commenter_projection_min_shared_filters(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    g = svc.graph(video_ids=["v1", "v2"], weight="co_comment:jaccard:min_shared=2")
    assert g.edge_count == 0  # every pair shares exactly 1 video


def test_overlap_parity_commenter_counts(tmp_path):
    """The co_comment_video projection must reproduce the overlap service's
    per-video commenter counts (single source of truth for identities)."""
    repos = _repos(tmp_path)
    overlap = CommenterOverlapService(repos).overlap(video_ids=["v1", "v2"])
    v1_count = next(
        e.commenter_count for e in overlap.videos.entities if e.entity_id == "v1"
    )
    assert v1_count == 3  # alice, bob, carol

    g = CommenterNetworkService(repos).graph(
        video_ids=["v1", "v2"], projection="co_comment_video"
    )
    v1 = next(n for n in g.nodes if n.id == "v1")
    assert v1.kind == "video"
    assert v1.degree == 3
    neighbours = {e.target if e.source == "v1" else e.source for e in g.edges if e.source == "v1" or e.target == "v1"}
    assert neighbours == {"UCid_alice", "UCid_bob", "Carol"}


def test_communities_and_modularity(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    g = svc.graph(video_ids=["v1", "v2"], projection="commenter")
    assert g.community_count >= 1
    assert g.modularity is not None
    # louvain seed=42 is deterministic
    g2 = svc.graph(video_ids=["v1", "v2"], projection="commenter")
    assert g2.modularity == g.modularity


def test_metrics_ranks(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    m = svc.metrics(video_ids=["v1", "v2"], projection="commenter")
    assert m.node_count == 3
    assert m.community_count >= 1
    assert m.modularity is not None
    assert m.top_bridges and m.top_core and m.top_prolific
    # alice commented on 2 videos -> most prolific
    assert m.top_prolific[0].id == "UCid_alice"


def test_centralities_battery(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    c = svc.centralities(video_ids=["v1", "v2"], projection="commenter")
    assert set(c.nodes) == {"UCid_alice", "UCid_bob", "Carol"}
    for vals in c.nodes.values():
        assert 0.0 <= vals.degree <= 1.0
        assert 0.0 <= vals.closeness <= 1.0
        assert 0.0 <= vals.eigenvector <= 1.0
        assert 0.0 <= vals.betweenness <= 1.0
        assert vals.community_id >= 0


def test_export_reuses_recommendation_serializers(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    fname, content, media = svc.export_network("json", video_ids=["v1", "v2"], projection="commenter")
    assert media == "application/json"
    obj = json.loads(content)
    assert len(obj["nodes"]) == 3
    assert any(e["data"]["relationship_type"] == "co_comment" for e in obj["links"])

    fname, content, media = svc.export_network("graphml", video_ids=["v1", "v2"], projection="commenter")
    assert "co_comment" in content

    fname, content, media = svc.export_network("csv", video_ids=["v1", "v2"], projection="commenter")
    assert "co_comment" in content

    fname, content, media = svc.export_network("xlsx", video_ids=["v1", "v2"], projection="commenter")
    assert media.endswith("spreadsheetml.sheet")
    assert isinstance(content, bytes)


def test_invalid_weight_raises(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    with pytest.raises(WeightSpecError):
        svc.graph(video_ids=["v1", "v2"], weight="co_comment:bogus_mode")


def test_heterogeneous_includes_containment(tmp_path):
    svc = CommenterNetworkService(_repos(tmp_path))
    g = svc.graph(video_ids=["v1", "v2"], projection="heterogeneous")
    kinds = {n.kind for n in g.nodes}
    assert kinds == {"commenter", "video", "channel"}
    assert any(e.kind == "containment" for e in g.edges)


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
def test_graph_endpoint_200(client):
    resp = client.get(f"{PREFIX}/network/commenters/graph?video_ids=v1,v2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["projection"] == "commenter"
    assert body["node_count"] == 3
    assert body["weight_spec"]["edge_type"] == "co_comment"


def test_graph_invalid_projection_400(client):
    resp = client.get(f"{PREFIX}/network/commenters/graph?video_ids=v1,v2&projection=bogus")
    assert resp.status_code == 400


def test_graph_empty_scope_400(client):
    resp = client.get(f"{PREFIX}/network/commenters/graph")
    assert resp.status_code == 400


def test_metrics_endpoint_200(client):
    resp = client.get(f"{PREFIX}/network/commenters/metrics?video_ids=v1,v2")
    assert resp.status_code == 200, resp.text
    assert resp.json()["community_count"] >= 1
    assert resp.json()["modularity"] is not None


def test_export_endpoint_200(client):
    resp = client.get(f"{PREFIX}/network/commenters/export?video_ids=v1,v2&format=json")
    assert resp.status_code == 200, resp.text
    assert "co_comment" in resp.text


def test_export_invalid_format_400(client):
    resp = client.get(f"{PREFIX}/network/commenters/export?video_ids=v1,v2&format=bogus")
    assert resp.status_code == 400


def test_roles_endpoint_200(client):
    resp = client.get(f"{PREFIX}/network/commenters/roles?video_ids=v1,v2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role_model"] == "core_broker_periphery_bridge"
    assert set(body["nodes"]) == {"UCid_alice", "UCid_bob", "Carol"}
    roles = {n: d["role"] for n, d in body["nodes"].items()}
    assert set(roles.values()) <= {"core", "broker", "bridge", "periphery"}


def test_community_insights_endpoint_200(client):
    resp = client.get(f"{PREFIX}/network/commenters/community-insights?video_ids=v1,v2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "communities" in body
    assert len(body["communities"]) >= 1
    comm = body["communities"][0]
    assert "dominant_kinds" in comm
    assert "top_bridges" in comm
