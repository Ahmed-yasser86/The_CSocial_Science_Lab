"""Unit tests for CommunityExportService (Content Homophily §24 export)."""

from __future__ import annotations

import io
import zipfile

import numpy as np

from SocialScienceResearch.services.network_analytics_service import (
    GraphEdge,
    GraphNode,
    NetworkGraph,
)
from SocialScienceResearch.services.community_export_service import (
    CommunityExportService,
    _cosine,
)


def _make_service():
    class FakeSettings:
        class Repository:
            data_dir = None

        repository = Repository()

    class FakeRepos:
        pass

    return CommunityExportService(FakeRepos(), FakeSettings())


def _fake_graph():
    nodes = [
        GraphNode(video_id="a1", title="A1", channel_id="c1",
                  channel_name="C1", community_id=0, in_degree=2, out_degree=1),
        GraphNode(video_id="a2", title="A2", channel_id="c1",
                  channel_name="C1", community_id=0, in_degree=1, out_degree=2),
        GraphNode(video_id="b1", title="B1", channel_id="c2",
                  channel_name="C2", community_id=1, in_degree=3, out_degree=0),
    ]
    edges = [
        GraphEdge(source="a1", target="a2", weight=1.0,
                  relationship_type="recommendation"),
        GraphEdge(source="a1", target="b1", weight=0.5,
                  relationship_type="recommendation"),
    ]
    return NetworkGraph(nodes=nodes, edges=edges, edge_count=2)


def _vectors():
    rng = np.random.default_rng(0)
    return {
        "a1": rng.normal(size=8),
        "a2": rng.normal(size=8),
        "b1": rng.normal(size=8),
    }


def test_cosine_basic():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(_cosine(a, b)) < 1e-9
    assert abs(_cosine(a, a) - 1.0) < 1e-9


def test_export_zip_contents():
    svc = _make_service()
    svc._graph = lambda run_id, video_ids: _fake_graph()  # type: ignore[assignment]
    svc._cached_vectors = lambda vids: _vectors()  # type: ignore[assignment]

    data = svc.export_zip(run_id="run_x", analysis_id=None)
    assert isinstance(data, bytes)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "communities_export/community_0_nodes.csv" in names
        assert "communities_export/community_0_edges.csv" in names
        assert "communities_export/community_1_nodes.csv" in names
        assert "communities_export/all_communities_edges.csv" in names
        assert "communities_export/content_analysis_per_community.csv" in names
        assert "communities_export/content_analysis_detailed.json" in names
        assert "communities_export/README.txt" in names

        # community 1 has no internal edge -> its edge file is header-only but exists
        edge1 = zf.read("communities_export/community_1_edges.csv").decode()
        assert "source" in edge1

        detailed = zf.read("communities_export/content_analysis_detailed.json").decode()
        payload = __import__("json").loads(detailed)
        assert payload["scope"]["community_count"] == 2
        # Within-community similarity for community 0 computed from a1/a2.
        comm0 = next(
            c for c in payload["per_community_content_analysis"]
            if c["community_id"] == 0
        )
        assert comm0["within_community_similarity"] is not None
        assert comm0["n_videos_with_embeddings"] == 2
        # Similarity to the other community recorded.
        assert any(
            o["community"] == 1 for o in comm0["similarity_to_other_communities"]
        )


def test_export_empty_scope_raises():
    svc = _make_service()
    svc._graph = lambda run_id, video_ids: NetworkGraph(nodes=[], edges=[])  # type: ignore[assignment]
    svc._cached_vectors = lambda vids: {}  # type: ignore[assignment]
    try:
        svc.export_zip(run_id="empty")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
