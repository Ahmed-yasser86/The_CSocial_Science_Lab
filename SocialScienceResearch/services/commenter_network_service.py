"""Commenter (audience) network analytics -- WS7 graph family (N2).

Builds the *audience* network family from the same persisted comment scan the
overlap service uses, then projects it into research-grade graphs:

* ``commenter``          - commenter<->commenter co-comment graph, weighted by the
                           chosen ``co_comment`` metric (Jaccard / overlap /
                           intersection) over shared videos.
* ``co_comment_video``   - bipartite commenter<->video graph, edge weight = comment
                           count on that video.
* ``co_comment_channel`` - bipartite commenter<->channel graph.
* ``heterogeneous``      - all three node kinds plus structural video->channel
                           containment edges (weight fixed at 1, never weighted).

Community detection reuses ``louvain_communities(seed=42)`` (the same seed and
algorithm as every other community surface in the Lab) and centralities reuse
``centrality_battery`` from :mod:`network_analytics_service` so the two families
compute identical math. Export reuses the recommendation serializers (the
``relationship_type`` attribute carries ``co_comment`` so downloaded files are
not mislabelled "recommendation").

All data is observed-only (never fabricated); anonymous comments are excluded
via :func:`resolve_author`, exactly like the overlap service.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Literal

import networkx as nx
from networkx.algorithms.community import louvain_communities, modularity
from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.commenter_overlap_service import resolve_author
from SocialScienceResearch.services.network_analytics_service import (
    GraphEdge,
    GraphNode,
    NetworkAnalyticsService,
    NetworkGraph,
    _percentile_threshold,
    centrality_battery,
)
from SocialScienceResearch.services.weight_spec import (
    WeightSpec,
    normalize_weights,
    parse_weight_spec,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Base(BaseModel):
    """``extra="allow"`` response-model base (matches network analytics)."""

    model_config = ConfigDict(extra="allow")


class CommenterGraphNode(_Base):
    id: str
    kind: str = "commenter"  # commenter | video | channel
    label: str | None = None
    degree: int = 0
    community_id: int | None = None
    identity_kind: str | None = None
    comment_count: int = 0


class CommenterGraphEdge(_Base):
    source: str
    target: str
    kind: str = "co_comment"  # co_comment | co_comment_video | co_comment_channel | containment
    weight: float = 1.0
    relationship_type: str = "co_comment"
    shared_count: int | None = None


class CommenterNetworkGraph(_Base):
    projection: str = "commenter"
    nodes: list[CommenterGraphNode] = Field(default_factory=list)
    edges: list[CommenterGraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    weight_spec: dict | None = None
    community_count: int = 0
    modularity: float | None = None
    computed_at: str | None = None


class CommenterCentrality(_Base):
    degree: float = 0.0
    closeness: float = 0.0
    eigenvector: float = 0.0
    betweenness: float = 0.0
    pagerank: float = 0.0
    harmonic: float = 0.0
    constraint: float = 0.0
    effective_size: float = 0.0
    bridging: float = 0.0
    clustering: float = 0.0
    community_id: float = -1.0


class CommenterNetworkCentralities(_Base):
    nodes: dict[str, CommenterCentrality] = Field(default_factory=dict)
    weight_spec: dict | None = None
    algorithm: str = "networkx"
    computed_at: str | None = None


class BridgeRank(_Base):
    id: str
    label: str | None = None
    betweenness: float = 0.0


class CommenterNetworkMetrics(_Base):
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    community_count: int = 0
    modularity: float | None = None
    weakly_connected_components: int = 0
    avg_clustering: float = 0.0
    top_bridges: list[BridgeRank] = Field(default_factory=list)
    top_core: list[BridgeRank] = Field(default_factory=list)
    top_prolific: list[BridgeRank] = Field(default_factory=list)
    weight_spec: dict | None = None


def _co_comment_weight(mode: str, inter: int, size_a: int, size_b: int) -> float | None:
    """Raw (pre-normalization) co-comment weight between two commenters."""
    if mode in ("intersection", "counts"):
        return float(inter)
    if mode == "jaccard":
        union = size_a + size_b - inter
        return inter / union if union else None
    if mode == "overlap_coefficient":
        denom = min(size_a, size_b)
        return inter / denom if denom else None
    return float(inter)


@dataclass
class _BuiltGraph:
    G: Any
    node_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    edge_records: list[tuple[str, str, str, float, int | None]] = field(
        default_factory=list
    )
    ws: WeightSpec | None = None
    communities: list = field(default_factory=list)
    node_community: dict[str, int] = field(default_factory=dict)
    modularity: float | None = None
    weighted: bool = True


class CommenterNetworkService:
    """Audience-family network analytics over persisted comments.

    Pure reads; no writes. Memoizes the heavy scan per scope (short TTL, bounded
    entry count) -- writers must call :meth:`clear_commenter_network_cache` after
    any comment write, mirroring the overlap service's invalidation rule.
    """

    _cache: dict[tuple, tuple[float, "_BuiltGraph"]] = {}
    _TTL_SECONDS = 60.0
    _CACHE_MAX_ENTRIES = 128
    _CHUNK_SIZE = 5000

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    @classmethod
    def clear_commenter_network_cache(cls) -> None:
        """Invalidate cached audience graphs (call after any comment write)."""
        cls._cache.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def graph(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
    ) -> CommenterNetworkGraph:
        """Interactive audience graph for the requested projection/scope."""
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        nodes = [
            CommenterGraphNode(
                id=nid,
                kind=built.node_meta.get(nid, {}).get("kind", "other"),
                label=built.node_meta.get(nid, {}).get("label"),
                degree=int(built.G.degree(nid)),
                community_id=built.node_community.get(nid),
                identity_kind=built.node_meta.get(nid, {}).get("identity_kind"),
                comment_count=built.node_meta.get(nid, {}).get("comment_count", 0),
            )
            for nid in built.G.nodes
        ]
        edges = [
            CommenterGraphEdge(
                source=s,
                target=t,
                kind=k,
                weight=w,
                relationship_type=k,
                shared_count=sc,
            )
            for (s, t, k, w, sc) in built.edge_records
        ]
        return CommenterNetworkGraph(
            projection=projection,
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            weight_spec=built.ws.to_dict() if built.ws else None,
            community_count=len(built.communities),
            modularity=built.modularity,
            computed_at=_now(),
        )

    def metrics(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
    ) -> CommenterNetworkMetrics:
        """Aggregate audience-network statistics + bridge/core/prolific ranks."""
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        G = built.G
        metrics = CommenterNetworkMetrics(
            node_count=G.number_of_nodes(),
            edge_count=G.number_of_edges(),
            weight_spec=built.ws.to_dict() if built.ws else None,
        )
        if G.number_of_edges() == 0:
            return metrics
        battery = centrality_battery(G, weighted=built.weighted)
        metrics.density = float(nx.density(G))
        metrics.weakly_connected_components = len(list(nx.connected_components(G)))
        metrics.avg_clustering = float(nx.average_clustering(G))
        metrics.community_count = len(built.communities)
        metrics.modularity = built.modularity

        # Bridge audiences = high betweenness; core audiences = high eigenvector;
        # prolific commenters = highest observed comment volume (commenter nodes).
        bridges = sorted(battery.items(), key=lambda kv: -kv[1]["betweenness"])[:10]
        core = sorted(battery.items(), key=lambda kv: -kv[1]["eigenvector"])[:10]
        prolific = sorted(
            (
                (nid, built.node_meta.get(nid, {}).get("comment_count", 0))
                for nid in built.node_meta
                if built.node_meta[nid].get("kind") == "commenter"
            ),
            key=lambda x: -x[1],
        )[:10]
        metrics.top_bridges = [
            BridgeRank(
                id=n,
                label=built.node_meta.get(n, {}).get("label"),
                betweenness=v["betweenness"],
            )
            for n, v in bridges
        ]
        metrics.top_core = [
            BridgeRank(
                id=n,
                label=built.node_meta.get(n, {}).get("label"),
                betweenness=v["eigenvector"],
            )
            for n, v in core
        ]
        metrics.top_prolific = [
            BridgeRank(
                id=n,
                label=built.node_meta.get(n, {}).get("label"),
                betweenness=float(c),
            )
            for n, c in prolific
        ]
        return metrics

    def centralities(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
    ) -> CommenterNetworkCentralities:
        """Full per-node centrality battery for the audience graph (N0/N3)."""
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        battery = centrality_battery(built.G, weighted=built.weighted)
        nodes = {
            nid: CommenterCentrality(
                degree=vals["degree"],
                closeness=vals["closeness"],
                eigenvector=vals["eigenvector"],
                betweenness=vals["betweenness"],
                pagerank=vals["pagerank"],
                harmonic=vals["harmonic"],
                constraint=vals["constraint"],
                effective_size=vals["effective_size"],
                bridging=vals["bridging"],
                clustering=vals["clustering"],
                community_id=float(built.node_community.get(nid, -1)),
            )
            for nid, vals in battery.items()
        }
        return CommenterNetworkCentralities(
            nodes=nodes,
            weight_spec=built.ws.to_dict() if built.ws else None,
            algorithm="networkx",
            computed_at=_now(),
        )

    def roles(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
        role_model: str = "core_broker_periphery_bridge",
    ) -> dict[str, Any]:
        """Structural roles for the audience graph (N3).

        Mirrors ``NetworkAnalyticsService.roles``: eigenvector top-quartile →
        ``core`` (core audiences), betweenness top-decile → ``broker`` (bridge
        audiences), degree bottom-quartile → ``periphery``, else ``bridge``.
        """
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        if built.G.number_of_nodes() == 0:
            return {
                "nodes": {},
                "role_model": role_model,
                "algorithm": "networkx",
                "computed_at": _now(),
            }
        approximate = built.G.number_of_nodes() > 5000
        battery = centrality_battery(built.G, weighted=built.weighted, approximate=approximate)
        ev_vals = [c["eigenvector"] for c in battery.values()]
        bt_vals = [c["betweenness"] for c in battery.values()]
        deg_vals = [c["degree"] for c in battery.values()]
        ev_q = _percentile_threshold(ev_vals, 0.75)
        bt_q = _percentile_threshold(bt_vals, 0.90)
        deg_low = _percentile_threshold(deg_vals, 0.25)
        nodes: dict[str, dict[str, Any]] = {}
        for nid, c in battery.items():
            if c["eigenvector"] >= ev_q:
                role = "core"
            elif c["betweenness"] >= bt_q:
                role = "broker"
            elif c["degree"] <= deg_low:
                role = "periphery"
            else:
                role = "bridge"
            nodes[nid] = {
                "role": role,
                "community_id": float(built.node_community.get(nid, -1)),
            }
        return {
            "nodes": nodes,
            "role_model": role_model,
            "approximate": approximate,
            "algorithm": "networkx",
            "computed_at": _now(),
        }

    def community_insights(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
    ) -> dict[str, Any]:
        """Per-community composition for the audience graph (N3).

        For each community reports its size, the dominant node *kinds*
        (commenter/video/channel counts) and the top bridge audiences
        (highest betweenness commenter nodes) observed in that community.
        """
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        if built.G.number_of_nodes() == 0:
            return {"communities": [], "algorithm": "networkx", "computed_at": _now()}
        battery = centrality_battery(built.G, weighted=built.weighted)
        by_community: dict[int, list[str]] = {}
        for nid in built.G.nodes:
            cid = int(built.node_community.get(nid, -1))
            by_community.setdefault(cid, []).append(nid)
        communities = []
        for cid, members in by_community.items():
            kind_counts: Counter = Counter(
                built.node_meta.get(m, {}).get("kind", "other") for m in members
            )
            top_bt = sorted(
                (m for m in members if built.node_meta.get(m, {}).get("kind") == "commenter"),
                key=lambda m: battery[m]["betweenness"],
                reverse=True,
            )[:10]
            communities.append(
                {
                    "community_id": cid,
                    "size": len(members),
                    "dominant_kinds": dict(kind_counts),
                    "top_bridges": [
                        {
                            "id": m,
                            "label": built.node_meta.get(m, {}).get("label"),
                            "betweenness": battery[m]["betweenness"],
                        }
                        for m in top_bt
                    ],
                }
            )
        communities.sort(key=lambda c: c["size"], reverse=True)
        return {"communities": communities, "algorithm": "networkx", "computed_at": _now()}

    def communities(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
        min_size: int = 1,
    ) -> dict[str, Any]:
        """Communities as first-class graph entities for the audience network (N4).

        Returns one entry per detected community with its ``node_ids`` (member
        list) so the UI can highlight or isolate a community as a sub-graph.
        ``id`` is a stable string of the louvain community id; ``label`` is a
        size-ranked human label; ``top_node_ids`` lists the highest-degree
        members for quick legend rendering.
        """
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        if built.G.number_of_nodes() == 0:
            return {
                "communities": [],
                "algorithm": "networkx",
                "seed": 42,
                "computed_at": _now(),
            }
        by_community: dict[int, list[str]] = {}
        for nid in built.G.nodes:
            cid = int(built.node_community.get(nid, -1))
            by_community.setdefault(cid, []).append(nid)
        communities = []
        for idx, (cid, members) in enumerate(
            sorted(by_community.items(), key=lambda kv: len(kv[1]), reverse=True)
        ):
            if len(members) < min_size:
                continue
            top = sorted(members, key=lambda m: built.G.degree(m), reverse=True)[:10]
            communities.append(
                {
                    "id": str(cid),
                    "community_id": cid,
                    "label": f"Community {idx + 1}",
                    "size": len(members),
                    "node_ids": members,
                    "top_node_ids": top,
                }
            )
        return {
            "communities": communities,
            "algorithm": "networkx",
            "seed": 42,
            "computed_at": _now(),
        }

    def export_network(
        self,
        format: str = "graphml",
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        run_ids: list[str] | None = None,
        projection: str = "commenter",
        weight: str = "co_comment:jaccard",
        weighted: bool = True,
    ) -> tuple[str, str | bytes, str]:
        """Serialize the audience graph via the recommendation serializers.

        Builds a :class:`NetworkGraph`-shaped payload (commenter/video/channel
        nodes mapped onto the same node/edge models) so the downloaded file
        mirrors the rendered graph and reuses the single serializer -- no second
        writer. ``relationship_type`` carries ``co_comment``/``containment``.
        """
        built = self._compute(
            video_ids=video_ids,
            channel_ids=channel_ids,
            run_ids=run_ids,
            projection=projection,
            weight=weight,
            weighted=weighted,
        )
        gnodes = [
            GraphNode(
                video_id=nid,
                title=built.node_meta.get(nid, {}).get("label"),
                kind=built.node_meta.get(nid, {}).get("kind", "other"),
                in_degree=int(built.G.degree(nid)),
                out_degree=0,
                community_id=built.node_community.get(nid),
                recommendations_scraped=False,
            )
            for nid in built.G.nodes
        ]
        gedges = [
            GraphEdge(source=s, target=t, weight=w, relationship_type=k)
            for (s, t, k, w, sc) in built.edge_records
        ]
        payload = NetworkGraph(nodes=gnodes, edges=gedges)
        return NetworkAnalyticsService(self._repos)._serialize_video_graph(
            payload, format, built.ws.to_dict() if built.ws else None
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _scope_sets(
        self,
        video_ids: list[str] | None,
        channel_ids: list[str] | None,
        run_ids: list[str] | None,
    ) -> tuple[set[str], set[str], dict[str, str]]:
        video_set = set(video_ids or [])
        channel_set = set(channel_ids or [])
        if run_ids:
            for rid in run_ids:
                for v in self._repos.videos.list_videos_by_run(rid):
                    video_set.add(v.video_id)
            # Derived runs (recommendation / layer / echo-chamber) do not own any
            # video as ``first_observed_run_id`` -- their scope is defined by the
            # recommendation edges they produced (collection_run_id == run_id),
            # exactly like the video network graph. Fold those edge endpoints in
            # so the audience network resolves for every run kind, not just raw
            # collection runs.
            for e in self._repos.recommendations.list_recommendation_edges(
                run_ids=run_ids
            ):
                video_set.add(e.source_video_id)
                video_set.add(e.recommended_video_id)
        videos = {v.video_id: v for v in self._repos.videos.list_videos()}
        video_channel = {vid: v.channel_id for vid, v in videos.items()}
        for vid in video_set:
            ch = video_channel.get(vid)
            if ch:
                channel_set.add(ch)
        return video_set, channel_set, video_channel

    def _scan(
        self,
        video_set: set[str],
        channel_set: set[str],
        video_channel: dict[str, str],
    ) -> tuple[
        dict[str, dict[str, int]],
        dict[str, dict[str, int]],
        dict[str, dict[str, Any]],
        dict[str, set[str]],
        dict[str, set[str]],
        Counter,
    ]:
        video_commenters: dict[str, dict[str, int]] = defaultdict(dict)
        channel_commenters: dict[str, dict[str, int]] = defaultdict(dict)
        commenter_meta: dict[str, dict[str, Any]] = {}
        commenter_videos: dict[str, set[str]] = defaultdict(set)
        commenter_channels: dict[str, set[str]] = defaultdict(set)
        comment_counts: Counter = Counter()
        columns = ["author_id", "author_name", "is_author", "published_at"]
        for chunk in self._repos.comments.iter_comments(
            chunk_size=self._CHUNK_SIZE, columns=columns
        ):
            for c in chunk:
                vid = c.video_id
                ch = video_channel.get(vid)
                in_v = vid in video_set
                in_ch = ch is not None and ch in channel_set
                if not (in_v or in_ch):
                    continue
                kind, key, display = resolve_author(c)
                if key is None:
                    continue
                meta = commenter_meta.setdefault(
                    key, {"kind": kind or "name", "label": display}
                )
                if display:
                    meta["label"] = display
                comment_counts[key] += 1
                if in_v:
                    video_commenters[vid][key] = video_commenters[vid].get(key, 0) + 1
                    commenter_videos[key].add(vid)
                if in_ch:
                    channel_commenters[ch][key] = (
                        channel_commenters[ch].get(key, 0) + 1
                    )
                    commenter_channels[key].add(ch)
        return (
            video_commenters,
            channel_commenters,
            commenter_meta,
            commenter_videos,
            commenter_channels,
            comment_counts,
        )

    def _compute(
        self,
        *,
        video_ids: list[str] | None,
        channel_ids: list[str] | None,
        run_ids: list[str] | None,
        projection: str,
        weight: str | None,
        weighted: bool,
    ) -> _BuiltGraph:
        ws = parse_weight_spec(weight) if weight else parse_weight_spec("co_comment:jaccard")
        cache_key = (
            id(self._repos),
            projection,
            ws.to_token(),
            tuple(sorted(video_ids or [])),
            tuple(sorted(channel_ids or [])),
            tuple(sorted(run_ids or [])),
            bool(weighted),
        )
        cached = self._cache.get(cache_key)
        if cached is not None and (time.time() - cached[0]) < self._TTL_SECONDS:
            return cached[1]
        built = self._build(projection, ws, weighted, video_ids, channel_ids, run_ids)
        self._cache[cache_key] = (time.time(), built)
        while len(self._cache) > self._CACHE_MAX_ENTRIES:
            self._cache.pop(next(iter(self._cache)))
        return built

    def _build(
        self,
        projection: str,
        ws: WeightSpec,
        weighted: bool,
        video_ids: list[str] | None,
        channel_ids: list[str] | None,
        run_ids: list[str] | None,
    ) -> _BuiltGraph:
        video_set, channel_set, video_channel = self._scope_sets(
            video_ids, channel_ids, run_ids
        )
        if not video_set and not channel_set:
            raise ValueError(
                "Provide at least one of video_ids, channel_ids, or run_ids"
            )
        (
            video_commenters,
            channel_commenters,
            commenter_meta,
            commenter_videos,
            _commenter_channels,
            comment_counts,
        ) = self._scan(video_set, channel_set, video_channel)

        video_titles = {
            v.video_id: v.title for v in self._repos.videos.list_videos()
        }
        channel_titles = {
            c.channel_id: c.title for c in self._repos.channels.list_channels()
        }

        G = nx.Graph()
        node_meta: dict[str, dict[str, Any]] = {}
        edge_records: list[tuple[str, str, str, float, int | None]] = []
        min_shared = int(ws.params.get("min_shared", 1))
        top_n = int(ws.params.get("top_n", 200))

        if projection == "commenter":
            self._add_commenter_projection(
                G,
                node_meta,
                edge_records,
                video_commenters,
                commenter_videos,
                commenter_meta,
                comment_counts,
                ws,
                min_shared,
            )
        elif projection == "co_comment_video":
            self._add_bipartite(
                G,
                node_meta,
                edge_records,
                video_commenters,
                commenter_meta,
                comment_counts,
                ws,
                min_shared,
                top_n,
                kind="video",
                label_map=video_titles,
            )
        elif projection == "co_comment_channel":
            self._add_bipartite(
                G,
                node_meta,
                edge_records,
                channel_commenters,
                commenter_meta,
                comment_counts,
                ws,
                min_shared,
                top_n,
                kind="channel",
                label_map=channel_titles,
            )
        elif projection == "heterogeneous":
            self._add_bipartite(
                G,
                node_meta,
                edge_records,
                video_commenters,
                commenter_meta,
                comment_counts,
                ws,
                min_shared,
                top_n,
                kind="video",
                label_map=video_titles,
            )
            self._add_bipartite(
                G,
                node_meta,
                edge_records,
                channel_commenters,
                commenter_meta,
                comment_counts,
                ws,
                min_shared,
                top_n,
                kind="channel",
                label_map=channel_titles,
            )
            for vid in video_set:
                ch = video_channel.get(vid)
                if ch is not None and (vid in G.nodes or ch in G.nodes):
                    edge_records.append((vid, ch, "containment", 1.0, None))
                    G.add_edge(vid, ch, weight=1.0)
        else:
            raise ValueError(
                f"Unknown projection '{projection}' (expected commenter | "
                "co_comment_video | co_comment_channel | heterogeneous)"
            )

        if G.number_of_edges() > 0:
            communities = list(louvain_communities(G, seed=42))
            node_community = {
                nid: idx
                for idx, comm in enumerate(communities)
                for nid in comm
            }
            try:
                mod = float(modularity(G, communities))
            except Exception:
                mod = None
        else:
            communities = []
            node_community = {}
            mod = None

        return _BuiltGraph(
            G=G,
            node_meta=node_meta,
            edge_records=edge_records,
            ws=ws,
            communities=communities,
            node_community=node_community,
            modularity=mod,
            weighted=weighted,
        )

    def _add_commenter_projection(
        self,
        G: "nx.Graph",
        node_meta: dict[str, dict[str, Any]],
        edge_records: list,
        video_commenters: dict[str, dict[str, int]],
        commenter_videos: dict[str, set[str]],
        commenter_meta: dict[str, dict[str, Any]],
        comment_counts: Counter,
        ws: WeightSpec,
        min_shared: int,
    ) -> None:
        co: Counter = Counter()
        for vid, authors in video_commenters.items():
            ks = list(authors)
            for a, b in combinations(ks, 2):
                co[(a, b)] += 1
        pairs: list[tuple[str, str, float, int]] = []
        raw: list[float] = []
        for (a, b), inter in co.items():
            if inter < min_shared:
                continue
            sa = len(commenter_videos[a])
            sb = len(commenter_videos[b])
            w = _co_comment_weight(ws.weight_mode, inter, sa, sb)
            if w is None:
                continue
            pairs.append((a, b, w, inter))
            raw.append(w)
        norm = normalize_weights(raw, ws.normalization)
        per_node: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
        for (a, b, w, inter), nw in zip(pairs, norm):
            per_node[a].append((b, nw, inter))
            per_node[b].append((a, nw, inter))
        top_n = int(ws.params.get("top_n", 200))
        for node, neigh in per_node.items():
            neigh.sort(key=lambda x: -x[1])
            for other, nw, inter in neigh[:top_n]:
                edge_records.append((node, other, "co_comment", nw, inter))
                G.add_edge(node, other, weight=nw)
            meta = commenter_meta.get(node, {})
            node_meta[node] = {
                "kind": "commenter",
                "label": meta.get("label"),
                "identity_kind": meta.get("kind"),
                "comment_count": comment_counts[node],
            }

    def _add_bipartite(
        self,
        G: "nx.Graph",
        node_meta: dict[str, dict[str, Any]],
        edge_records: list,
        entity_commenters: dict[str, dict[str, int]],
        commenter_meta: dict[str, dict[str, Any]],
        comment_counts: Counter,
        ws: WeightSpec,
        min_shared: int,
        top_n: int,
        kind: str,
        label_map: dict[str, str | None],
    ) -> None:
        cands: list[tuple[str, str, float]] = []
        for eid, authors in entity_commenters.items():
            for key, cnt in authors.items():
                if cnt < min_shared:
                    continue
                cands.append((key, eid, float(cnt)))
        by_commenter: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for key, eid, w in cands:
            by_commenter[key].append((eid, w))
        for key, edges in by_commenter.items():
            edges.sort(key=lambda x: -x[1])
            for eid, w in edges[:top_n]:
                edge_records.append((key, eid, f"co_comment_{kind}", w, None))
                G.add_edge(key, eid, weight=w)
                meta = commenter_meta.get(key, {})
                node_meta.setdefault(
                    key,
                    {
                        "kind": "commenter",
                        "label": meta.get("label"),
                        "identity_kind": meta.get("kind"),
                        "comment_count": comment_counts[key],
                    },
                )
        for eid in entity_commenters:
            node_meta.setdefault(
                eid,
                {
                    "kind": kind,
                    "label": label_map.get(eid),
                    "identity_kind": None,
                    "comment_count": 0,
                },
            )
