"""Structural metrics for the echo-chamber spec (§5-§21) - pure functions.

Every function here computes REAL values from an ``nx.DiGraph`` built from
persisted recommendation edges. Nothing is estimated; when a metric cannot
be computed (empty graph, zero denominators, degenerate cases) the metric
envelope carries ``status="unavailable"`` with ``value=None`` - never a
silent 0 (spec §0).

Methodological contracts implemented here (spec references):

* **Edge dedup policy (§5.2)** - persisted observations may contain repeated
  ``(source, target)`` pairs across runs/layers. Graphs are ``nx.DiGraph``,
  so repeated observations collapse into ONE unique directed edge;
  ``edge_count`` therefore counts distinct observed recommendation pairs.
  Observation counts stay in persistence and are exposed separately where a
  weighted view is needed (channel projection). This is documented, never
  silently decided.
* **Clustering / community projection (§7, §9)** - clustering coefficients
  and community detection are undirected-only; both use ``G.to_undirected()``.
  A triangle does NOT imply social cohesion; communities are structural
  regions of the observed recommendation graph, not belief groups.
* **Conductance volume (§11)** - volume uses the UNDIRECTED projection:
  ``volume(C) = sum of degrees of C's nodes in G.to_undirected()``, cut is
  the number of undirected edges with exactly one endpoint in C. Definitions
  are never mixed (no directed degrees inside conductance).
* **Null model (§14)** - double-edge swaps on the undirected projection
  preserve node count, edge count AND the exact degree sequence; individual
  edge directions are not preserved (documented). Communities are re-detected
  on each randomized graph with the same seeded algorithm (louvain seed=42)
  and the null WCR is scored against the ORIGINAL directed edges, so only the
  community assignment is randomized. Exposes n_randomizations + seed.

Category/lens vocabulary (spec §3): every envelope carries exactly one
``category`` from {standard_statistic, community_structure,
structural_reinforcement, centrality, channel_concentration, audience,
custom_signal} and one ``lens`` from {video, channel, audience,
cross_lens}.
"""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev
from typing import Any, Iterable

import networkx as nx
from networkx.algorithms.community import louvain_communities, modularity

#: Seeded community detection everywhere -> deterministic partitions.
COMMUNITY_SEED = 42

#: Default null-model configuration (spec §14: expose these numbers).
DEFAULT_N_RANDOMIZATIONS = 10

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Metadata envelope helpers (spec §36)
# ---------------------------------------------------------------------------

def envelope(
    metric: str,
    value: float | int | None,
    *,
    status: str = STATUS_AVAILABLE,
    category: str,
    lens: str,
    numerator: float | int | None = None,
    denominator: float | int | None = None,
    definition: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One metric wrapped in the §36 metadata contract."""
    payload: dict[str, Any] = {
        "metric": metric,
        "value": value,
        "status": status if value is not None else STATUS_UNAVAILABLE,
        "category": category,
        "lens": lens,
        "numerator": numerator,
        "denominator": denominator,
    }
    if definition:
        payload["definition"] = definition
    if detail:
        payload["detail"] = detail
    return payload


def unavailable(
    metric: str,
    reason: str,
    *,
    category: str,
    lens: str,
) -> dict[str, Any]:
    return envelope(
        metric,
        None,
        status=STATUS_UNAVAILABLE,
        category=category,
        lens=lens,
        detail={"reason": reason},
    )


def build_graph(edge_pairs: Iterable[tuple[str, str]]) -> nx.DiGraph:
    """Directed graph of unique recommendation pairs (dedup policy §5.2)."""
    graph = nx.DiGraph()
    for source, target in edge_pairs:
        graph.add_edge(source, target)
    return graph


def ratio(numerator: float | int, denominator: float | int) -> float | None:
    """None-safe ratio (never fabricates a 0 for an undefined quotient)."""
    if not denominator:
        return None
    return round(numerator / denominator, 6)


# ---------------------------------------------------------------------------
# §5/§6/§7/§8 - Standard network statistics
# ---------------------------------------------------------------------------

def degree_percentiles(values: list[int]) -> dict[str, float | None]:
    """Min/max/mean/P25/P75/P90/P95/P99 of one degree distribution (§6)."""
    if not values:
        return {
            key: None
            for key in ("min", "max", "mean", "p25", "p75", "p90", "p95", "p99")
        }
    ordered = sorted(values)

    def pct(p: float) -> float:
        if not ordered:
            return 0.0
        k = (len(ordered) - 1) * p
        lo = math.floor(k)
        hi = math.ceil(k)
        if lo == hi:
            return float(ordered[lo])
        return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)

    return {
        "min": float(ordered[0]),
        "max": float(ordered[-1]),
        "mean": round(mean(ordered), 6),
        "p25": pct(0.25),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "p99": pct(0.99),
    }


def standard_statistics(graph: nx.DiGraph) -> list[dict[str, Any]]:
    """Category-A envelopes: nodes, edges, density, reciprocity, degrees,
    clustering (on ``G.to_undirected()``, documented), weak components."""
    lens, cat = "video", "standard_statistic"
    out: list[dict[str, Any]] = []
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    out.append(envelope("node_count", node_count, category=cat, lens=lens))
    out.append(
        envelope(
            "edge_count",
            edge_count,
            category=cat,
            lens=lens,
            definition=(
                "Distinct directed recommendation pairs after dedup "
                "(repeated observations collapse to one unique edge, §5.2)"
            ),
        )
    )
    if node_count < 2 or edge_count == 0:
        out.append(unavailable("density", "needs >= 2 nodes and >= 1 edge", category=cat, lens=lens))
        out.append(unavailable("reciprocity", "needs >= 1 edge", category=cat, lens=lens))
        out.append(unavailable("degree_statistics", "no nodes with edges", category=cat, lens=lens))
        out.append(unavailable("avg_clustering", "needs >= 1 edge on G.to_undirected()", category=cat, lens=lens))
        out.append(unavailable("global_clustering", "needs >= 1 edge on G.to_undirected()", category=cat, lens=lens))
        out.append(
            envelope("weakly_connected_components", node_count, category=cat, lens=lens)
        )
        out.append(
            envelope("largest_component_size", 1 if node_count else 0, category=cat, lens=lens)
        )
        share = 1.0 if node_count else None
        out.append(envelope("largest_component_share", share, category=cat, lens=lens))
        return out

    out.append(
        envelope(
            "density",
            round(float(nx.density(graph)), 6),
            category=cat,
            lens=lens,
            numerator=edge_count,
            denominator=node_count * (node_count - 1),
            definition="edges / possible directed edges (n*(n-1))",
        )
    )
    out.append(
        envelope(
            "reciprocity",
            round(float(nx.reciprocity(graph)), 6),
            category=cat,
            lens=lens,
            definition="share of edges with a reciprocal opposite edge",
            detail={"interpretation": "reciprocal observed recommendations; NOT mutual agreement"},
        )
    )
    in_dist = degree_percentiles([d for _, d in graph.in_degree()])
    out_dist = degree_percentiles([d for _, d in graph.out_degree()])
    out.append(
        envelope(
            "degree_statistics",
            1,
            category=cat,
            lens=lens,
            detail={"in_degree": in_dist, "out_degree": out_dist},
        )
    )
    undirected = graph.to_undirected()
    out.append(
        envelope(
            "avg_clustering",
            round(float(nx.average_clustering(undirected)), 6),
            category=cat,
            lens=lens,
            definition="average clustering coefficient on G.to_undirected()",
        )
    )
    out.append(
        envelope(
            "global_clustering",
            round(float(nx.transitivity(undirected)), 6),
            category=cat,
            lens=lens,
            definition="transitivity on G.to_undirected()",
        )
    )
    components = list(nx.weakly_connected_components(graph))
    largest = max((len(c) for c in components), default=0)
    out.append(envelope("weakly_connected_components", len(components), category=cat, lens=lens))
    out.append(envelope("largest_component_size", largest, category=cat, lens=lens))
    out.append(
        envelope(
            "largest_component_share",
            ratio(largest, node_count),
            category=cat,
            lens=lens,
            numerator=largest,
            denominator=node_count,
        )
    )
    return out


# ---------------------------------------------------------------------------
# §9-§13 - Community structure
# ---------------------------------------------------------------------------

def detect_communities(graph: nx.DiGraph) -> list[set[str]]:
    """Deterministic louvain communities on ``G.to_undirected()`` (§9)."""
    if graph.number_of_nodes() == 0:
        return []
    return [set(c) for c in louvain_communities(graph.to_undirected(), seed=COMMUNITY_SEED)]


def _cut_and_volumes(
    undirected: nx.Graph, community: set[str]
) -> tuple[int, int, int]:
    """(cut_edges, volume(C), volume(outside)) under the §11 undirected rule."""
    inside = set(community & set(undirected.nodes))
    outside = set(undirected.nodes) - inside
    cut = sum(
        1
        for u, v in undirected.edges
        if (u in inside) != (v in inside)
    )
    vol_inside = sum(dict(undirected.degree(inside)).values()) if inside else 0
    vol_outside = sum(dict(undirected.degree(outside)).values()) if outside else 0
    return cut, vol_inside, vol_outside


def conductance(undirected: nx.Graph, community: set[str]) -> dict[str, Any]:
    """conductance(C) = cut(C, outside) / min(vol(C), vol(outside)) (§11).

    Volume = degree sums on the undirected projection ONLY (never mixed with
    directed degrees). Undefined (unavailable) when the smaller side has
    zero volume or there is no outside.
    """
    cut, vol_in, vol_out = _cut_and_volumes(undirected, community)
    denom = min(vol_in, vol_out)
    value = ratio(cut, denom)
    result = envelope(
        "conductance",
        value,
        category="community_structure",
        lens="video",
        numerator=cut,
        denominator=denom,
        definition=(
            "cut(C, outside C) / min(volume(C), volume(outside)); volume = "
            "degree sums on the undirected projection"
        ),
        detail={
            "community_size": len(set(community) & set(undirected.nodes)),
            "interpretation": "lower conductance = stronger structural separation",
        },
    )
    if value is None:
        result["status"] = STATUS_UNAVAILABLE
        result["value"] = None
        result["detail"]["reason"] = (
            "undefined: empty outside set or zero volume on the smaller side"
        )
    return result


def internal_external_ratio(digraph: nx.DiGraph, community: set[str]) -> dict[str, Any]:
    """internal/external directed edge ratio with explicit zero handling (§12)."""
    nodes = set(community)
    internal = external = 0
    for u, v in digraph.edges:
        if u in nodes and v in nodes:
            internal += 1
        elif u in nodes or v in nodes:
            external += 1
    value = ratio(internal, external)
    result = envelope(
        "internal_external_edge_ratio",
        value,
        category="community_structure",
        lens="video",
        numerator=internal,
        denominator=external,
        definition="internal directed edges / boundary-crossing directed edges",
        detail={"internal_edges": internal, "external_edges": external},
    )
    if not external:
        result["status"] = STATUS_UNAVAILABLE
        result["value"] = None
        result["detail"]["reason"] = "zero external edges (ratio undefined; counts shown explicitly)"
    return result


def within_community_rate(digraph: nx.DiGraph, partition: list[set[str]] | None = None) -> dict[str, Any]:
    """WCR = within-community directed edges / all directed edges (§13)."""
    edge_total = digraph.number_of_edges()
    if partition is None:
        partition = detect_communities(digraph)
    node_community: dict[str, int] = {}
    for idx, comm in enumerate(partition):
        for node in comm:
            node_community[node] = idx
    internal = sum(
        1
        for u, v in digraph.edges
        if node_community.get(u) is not None and node_community.get(u) == node_community.get(v)
    )
    value = ratio(internal, edge_total)
    result = envelope(
        "within_community_recommendation_rate",
        value,
        category="structural_reinforcement",
        lens="video",
        numerator=internal,
        denominator=edge_total,
        definition=(
            "directed edges whose endpoints share a detected community / all "
            "directed edges"
        ),
        detail={
            "interpretation": (
                "structural recommendation reinforcement; NOT probability of "
                "an echo chamber and NOT 'users trapped'"
            )
        },
    )
    if value is None:
        result["status"] = STATUS_UNAVAILABLE
        result["detail"]["reason"] = "no observed edges"
    return result


def community_structure(
    graph: nx.DiGraph,
    *,
    seed_video_id: str | None = None,
    max_communities: int = 50,
) -> dict[str, Any]:
    """Full §9-§13 community block: count/sizes/modularity/per-community rows.

    Per-community conductance + internal/external ratio are computed for up
    to ``max_communities`` largest communities plus the seed's community.
    """
    nodes = graph.number_of_nodes()
    edges = graph.number_of_edges()
    communities = detect_communities(graph)
    sizes = sorted((len(c) for c in communities), reverse=True)
    summary: dict[str, Any] = {
        "community_count": envelope(
            "community_count",
            len(communities) if nodes else 0,
            category="community_structure",
            lens="video",
        ),
        "largest_community_size": envelope(
            "largest_community_size",
            sizes[0] if sizes else 0,
            category="community_structure",
            lens="video",
        ),
        "modularity": unavailable("modularity", "no detected partition (empty graph)", category="community_structure", lens="video"),
        "seed_community": None,
        "communities": [],
    }
    if not communities or edges == 0:
        summary["community_count"]["status"] = STATUS_UNAVAILABLE
        summary["community_count"]["detail"] = {"reason": "empty graph"}
        summary["largest_community_size"]["status"] = STATUS_UNAVAILABLE
        return summary

    undirected = graph.to_undirected()
    summary["modularity"] = envelope(
        "modularity",
        round(float(modularity(undirected, communities)), 6),
        category="community_structure",
        lens="video",
        definition=(
            "Newman modularity of the louvain partition on G.to_undirected(); "
            "separation relative to the modularity objective only"
        ),
        detail={"algorithm": f"louvain_communities(seed={COMMUNITY_SEED})"},
    )

    ranked = sorted(communities, key=len, reverse=True)
    seed_set: set[str] | None = None
    if seed_video_id is not None:
        seed_set = next((c for c in communities if seed_video_id in c), None)
    selected = ranked[:max_communities]
    if seed_set is not None and not any(seed_set == c for c in selected):
        selected.append(seed_set)

    rows: list[dict[str, Any]] = []
    for comm in selected:
        members = sorted(comm)
        rows.append(
            {
                "size": len(members),
                "is_seed_community": bool(seed_set is not None and comm == seed_set),
                "members": members[:200],
                "conductance": conductance(undirected, comm),
                "internal_external_edge_ratio": internal_external_ratio(graph, comm),
            }
        )
    summary["communities"] = rows

    if seed_set is not None:
        summary["seed_community"] = {
            "size": len(seed_set),
            "contains_seed": True,
            "share": ratio(len(seed_set), nodes),
            "members_sample": sorted(seed_set)[:200],
            "conductance": conductance(undirected, seed_set),
            "internal_external_edge_ratio": internal_external_ratio(graph, seed_set),
        }
    else:
        summary["seed_community"] = {
            "contains_seed": False,
            "status": STATUS_UNAVAILABLE,
            "reason": "seed video not present in this slice" if seed_video_id else "no seed given",
        }
    return summary


# ---------------------------------------------------------------------------
# §14 - Null model (degree-preserving double-edge swaps)
# ---------------------------------------------------------------------------

def null_model_wcr(
    digraph: nx.DiGraph,
    *,
    n_randomizations: int = DEFAULT_N_RANDOMIZATIONS,
    seed: int = COMMUNITY_SEED,
) -> dict[str, Any]:
    """Seeded null model for WCR (spec §14).

    Preserved properties (documented): node count, edge count and the EXACT
    degree sequence of the undirected projection (double_edge_swap rewires
    while keeping every node's degree). Edge DIRECTIONS are not preserved -
    randomized graphs are undirected, so the null WCR re-scores the ORIGINAL
    directed edges against communities re-detected on each randomized graph.
    """
    observed_env = within_community_rate(digraph)
    base: dict[str, Any] = {
        "metric": "within_community_recommendation_rate_null_model",
        "observed": observed_env,
        "n_randomizations": n_randomizations,
        "seed": seed,
        "preserves": ["node_count", "edge_count", "degree_sequence (undirected projection)"],
        "does_not_preserve": ["individual edge directions"],
        "null_mean": None,
        "null_sd": None,
        "z_score": None,
        "empirical_percentile": None,
        "null_values": [],
        "status": STATUS_UNAVAILABLE,
    }
    if observed_env["value"] is None:
        base["detail"] = {"reason": "observed WCR unavailable"}
        return base
    undirected = digraph.to_undirected()
    m = undirected.number_of_edges()
    if m < 2 or undirected.number_of_nodes() < 4:
        base["detail"] = {
            "reason": "graph too small for degree-preserving swaps (needs >= 4 nodes, >= 2 edges)"
        }
        return base

    rng = random.Random(seed)
    null_values: list[float] = []
    original_directed = list(digraph.edges())
    for i in range(n_randomizations):
        swapped = undirected.copy()
        try:
            nx.double_edge_swap(
                swapped,
                nswap=m,
                max_tries=m * 20,
                seed=rng,
            )
        except nx.NetworkXError:
            continue
        randomized_partition = louvain_communities(swapped, seed=COMMUNITY_SEED)
        assignment: dict[str, int] = {}
        for idx, comm in enumerate(randomized_partition):
            for node in comm:
                assignment[node] = idx
        internal = sum(
            1
            for u, v in original_directed
            if assignment.get(u) is not None and assignment.get(u) == assignment.get(v)
        )
        value = ratio(internal, len(original_directed))
        if value is not None:
            null_values.append(value)

    observed_value = float(observed_env["value"])
    if len(null_values) < 2:
        base["detail"] = {"reason": "fewer than 2 successful randomizations"}
        base["null_values"] = null_values
        return base

    null_mean = round(mean(null_values), 6)
    null_sd = round(pstdev(null_values), 6)
    z_score = (
        round((observed_value - null_mean) / null_sd, 6) if null_sd > 0 else None
    )
    percentile = round(sum(1 for v in null_values if v <= observed_value) / len(null_values), 6)
    base.update(
        {
            "null_mean": null_mean,
            "null_sd": null_sd,
            "z_score": z_score,
            "empirical_percentile": percentile,
            "null_values": null_values,
            "status": STATUS_AVAILABLE,
        }
    )
    if z_score is None:
        base["detail"] = {"reason": "zero null standard deviation; z-score undefined"}
    return base


# ---------------------------------------------------------------------------
# §15 - Community persistence across layers
# ---------------------------------------------------------------------------

def community_persistence(
    layer_edges: list[tuple[int, list[tuple[str, str]]]],
    *,
    seed_video_id: str | None = None,
) -> list[dict[str, Any]]:
    """Per-cumulative-layer community persistence (spec §15).

    ``layer_edges`` is [(layer_index, unique directed pairs observed IN that
    layer)], ordered ascending. For each layer k a cumulative graph over all
    edges of layers <= k is analysed:

    * node_count / edge_count of the cumulative graph;
    * seed-community share (seed's community size / node count);
    * dominant-community share;
    * WCR where meaningful;
    * persistence = Jaccard membership overlap of the seed community with
      the previous layer's seed community.

    This measures STRUCTURE persistence - it is NOT Cross-Layer Repetition
    (§25).
    """
    rows: list[dict[str, Any]] = []
    cumulative: nx.DiGraph = nx.DiGraph()
    previous_seed_members: set[str] | None = None
    for layer_index, pairs in sorted(layer_edges, key=lambda item: item[0]):
        cumulative.add_edges_from(pairs)
        row: dict[str, Any] = {
            "layer_index": layer_index,
            "node_count": cumulative.number_of_nodes(),
            "edge_count": cumulative.number_of_edges(),
            "seed_community_share": None,
            "dominant_community_share": None,
            "within_community_recommendation_rate": None,
            "persistence_jaccard_vs_previous": None,
            "status": STATUS_AVAILABLE,
        }
        if cumulative.number_of_edges() == 0:
            row["status"] = STATUS_UNAVAILABLE
            row["reason"] = "no edges observed up to this layer"
            rows.append(row)
            continue
        partition = detect_communities(cumulative)
        wcr = within_community_rate(cumulative, partition)
        row["within_community_recommendation_rate"] = wcr["value"]
        dominant = max((len(c) for c in partition), default=0)
        row["dominant_community_share"] = ratio(dominant, cumulative.number_of_nodes())
        if seed_video_id is not None and seed_video_id in cumulative.nodes:
            seed_members = next(
                (c for c in partition if seed_video_id in c), None
            )
            if seed_members:
                row["seed_community_share"] = ratio(
                    len(seed_members), cumulative.number_of_nodes()
                )
                if previous_seed_members is not None:
                    union = seed_members | previous_seed_members
                    row["persistence_jaccard_vs_previous"] = (
                        round(len(seed_members & previous_seed_members) / len(union), 6)
                        if union
                        else None
                    )
                previous_seed_members = set(seed_members)
        else:
            row["seed_community_share_status"] = STATUS_UNAVAILABLE
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# §16/§17 - Centrality
# ---------------------------------------------------------------------------

def centrality_metrics(graph: nx.DiGraph, top_n: int = 10, titles: dict[str, str | None] | None = None) -> dict[str, Any]:
    """PageRank + HITS top lists (§16/§17), strictly structural labels."""
    if titles is None:
        titles = {}
    out: dict[str, Any] = {
        "pagerank": unavailable("pagerank_top", "no edges", category="centrality", lens="video"),
        "hits_hubs": unavailable("hits_hubs_top", "no edges", category="centrality", lens="video"),
        "hits_authorities": unavailable("hits_authorities_top", "no edges", category="centrality", lens="video"),
    }
    if graph.number_of_edges() == 0:
        return out
    pagerank = nx.pagerank(graph, alpha=0.85)
    hubs, authorities = nx.hits(graph)

    def _top(scores: dict[str, float]) -> list[dict[str, Any]]:
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        return [
            {"id": node, "score": round(float(score), 8), "title": titles.get(node)}
            for node, score in ranked
        ]

    out["pagerank"] = envelope(
        "pagerank_top",
        1,
        category="centrality",
        lens="video",
        definition="directed PageRank; structural prominence only",
        detail={"top": _top(pagerank), "interpretation": "NOT ideological importance/influence"},
    )
    out["hits_hubs"] = envelope(
        "hits_hubs_top",
        1,
        category="centrality",
        lens="video",
        definition="HITS hub scores on the directed graph",
        detail={"top": _top(hubs)},
    )
    out["hits_authorities"] = envelope(
        "hits_authorities_top",
        1,
        category="centrality",
        lens="video",
        definition="HITS authority scores on the directed graph",
        detail={"top": _top(authorities)},
    )
    return out


# ---------------------------------------------------------------------------
# §19/§20 - Channel concentration (HHI etc.)
# ---------------------------------------------------------------------------

def hhi(shares: list[float]) -> float | None:
    """Herfindahl-Hirschman Index HHI = sum(s_i^2); shares need not sum to 1."""
    if not shares:
        return None
    return round(sum(s * s for s in shares), 6)


def channel_concentration(weighted_out_or_in: dict[str, int]) -> dict[str, Any]:
    """Top Channel Share + HHI + unique channels from weighted activity (§19/§20).

    ``weighted_out_or_in`` maps channel_id -> weight (e.g. attributed video
    edge count). Shares are each channel's weight / total weight.
    """
    total = sum(weighted_out_or_in.values())
    if not weighted_out_or_in or total == 0:
        return {
            "top_channel_share": unavailable("top_channel_share", "no channel-attributed activity", category="channel_concentration", lens="channel"),
            "hhi": unavailable("hhi", "no channel-attributed activity", category="channel_concentration", lens="channel"),
            "unique_channel_count": envelope("unique_channel_count", 0, status=STATUS_UNAVAILABLE, category="channel_concentration", lens="channel", detail={"reason": "no channel-attributed activity"}),
            "shares": [],
        }
    shares = {cid: w / total for cid, w in sorted(weighted_out_or_in.items())}
    top_share = max(shares.values())
    index = hhi(list(shares.values()))
    return {
        "top_channel_share": envelope(
            "top_channel_share",
            round(top_share, 6),
            category="channel_concentration",
            lens="channel",
            numerator=max(weighted_out_or_in.values()),
            denominator=total,
        ),
        "hhi": envelope(
            "hhi",
            index,
            category="channel_concentration",
            lens="channel",
            definition="HHI = sum(s_i^2), s_i = channel share of attributed activity",
        ),
        "unique_channel_count": envelope(
            "unique_channel_count",
            len(shares),
            category="channel_concentration",
            lens="channel",
        ),
        "shares": [
            {"channel_id": cid, "weight": weighted_out_or_in[cid], "share": round(s, 6)}
            for cid, s in shares.items()
        ],
    }
