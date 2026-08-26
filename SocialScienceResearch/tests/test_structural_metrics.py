"""Deterministic structural-metrics tests (echo spec §40).

Every value is asserted against a hand-computed expectation on tiny fixed
graphs, including the §40 edge cases: empty graph, single node, no-edge,
one-community and zero-external-edge graphs. Also covers the §27/§28 lens
score contract (raw/normalized/weight/contribution/lens).
"""

from __future__ import annotations

import math

import networkx as nx

from SocialScienceResearch.services import structural_metrics as sm
from SocialScienceResearch.services.echo_scoring import compute_score


def _two_triangles() -> nx.DiGraph:
    """Deterministic 6-node/8-edge graph: {a,b,c}, {d,e}, bridge c->d.

    Edges: a<->b, a->c, b->c | d->e, e->f, f->d | c->d
    """
    g = nx.DiGraph()
    for u, v in [
        ("a", "b"),
        ("b", "a"),
        ("a", "c"),
        ("b", "c"),
        ("d", "e"),
        ("e", "f"),
        ("f", "d"),
        ("c", "d"),
    ]:
        g.add_edge(u, v)
    return g


def _by_metric(envelopes):
    return {m["metric"]: m for m in envelopes}


# ---------------------------------------------------------------------------
# §5/§6/§7/§8 standard statistics
# ---------------------------------------------------------------------------

def test_node_and_edge_counts_with_dedup():
    g = _two_triangles()
    stats = _by_metric(sm.standard_statistics(g))
    assert stats["node_count"]["value"] == 6
    assert stats["edge_count"]["value"] == 8
    # Dedup policy §5.2: repeated observations collapse to unique edges.
    deduped = sm.build_graph([("a", "b"), ("a", "b"), ("a", "b")])
    stats_d = _by_metric(sm.standard_statistics(deduped))
    assert stats_d["edge_count"]["value"] == 1
    assert stats_d["node_count"]["value"] == 2


def test_density_reciprocity_clustering_components():
    g = _two_triangles()
    stats = _by_metric(sm.standard_statistics(g))
    assert math.isclose(stats["density"]["value"], 8 / 30, abs_tol=1e-6)
    assert stats["density"]["numerator"] == 8
    assert stats["density"]["denominator"] == 30
    assert math.isclose(stats["reciprocity"]["value"], 0.25, abs_tol=1e-6)
    # Matches NetworkX on the same undirected projection (documented §7).
    assert math.isclose(
        stats["avg_clustering"]["value"],
        nx.average_clustering(g.to_undirected()),
        abs_tol=1e-6,
    )
    assert stats["weakly_connected_components"]["value"] == 1
    assert stats["largest_component_size"]["value"] == 6
    assert math.isclose(stats["largest_component_share"]["value"], 1.0)


def test_degree_percentiles_exact_values():
    dist = sm.degree_percentiles([1, 1, 1, 1, 2, 2])
    assert dist["min"] == 1.0 and dist["max"] == 2.0
    assert math.isclose(dist["p25"], 1.0, abs_tol=1e-9)
    assert math.isclose(dist["p75"], 1.75, abs_tol=1e-9)
    assert math.isclose(dist["p90"], 2.0, abs_tol=1e-9)
    assert math.isclose(dist["p95"], 2.0, abs_tol=1e-9)
    assert math.isclose(dist["p99"], 2.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# §40 edge cases for standard statistics
# ---------------------------------------------------------------------------

def test_empty_graph_standard_stats_unavailable_not_zero():
    envs = sm.standard_statistics(nx.DiGraph())
    by = _by_metric(envs)
    assert by["node_count"]["value"] == 0
    density = by["density"]
    assert density["status"] == "unavailable" and density["value"] is None


def test_single_node_and_no_edge_graphs():
    single = nx.DiGraph()
    single.add_node("x")
    stats = _by_metric(sm.standard_statistics(single))
    assert stats["node_count"]["value"] == 1
    assert stats["density"]["status"] == "unavailable"
    no_edge = nx.DiGraph()
    no_edge.add_nodes_from(["x", "y"])
    stats_ne = _by_metric(sm.standard_statistics(no_edge))
    assert stats_ne["reciprocity"]["status"] == "unavailable"
    assert stats_ne["weakly_connected_components"]["value"] == 2


# ---------------------------------------------------------------------------
# §9-§13 community structure
# ---------------------------------------------------------------------------

def test_community_detection_modularity_wcr():
    g = _two_triangles()
    cs = sm.community_structure(g, seed_video_id="a")
    assert cs["community_count"]["value"] == 2
    assert cs["modularity"]["value"] is not None
    assert cs["modularity"]["category"] == "community_structure"
    seed_comm = cs["seed_community"]
    assert seed_comm["contains_seed"] is True
    assert seed_comm["size"] == 3
    assert math.isclose(seed_comm["share"], 0.5)

    wcr = sm.within_community_rate(g)
    assert wcr["numerator"] == 7
    assert wcr["denominator"] == 8
    assert math.isclose(wcr["value"], 0.875)


def test_conductance_exact_undirected_volume_definition():
    g = _two_triangles()
    communities = sm.detect_communities(g)
    comm_c = next(c for c in communities if "c" in c)
    undirected = g.to_undirected()
    cond = sm.conductance(undirected, comm_c)
    # cut=1 (c-d), volumes 7 vs 7 -> 1/7
    assert cond["numerator"] == 1
    assert cond["denominator"] == 7
    assert math.isclose(cond["value"], 1 / 7, abs_tol=1e-6)
    assert cond["definition"].count("undirected projection") >= 1


def test_internal_external_ratio_and_zero_external_case():
    g = _two_triangles()
    communities = sm.detect_communities(g)
    comm_c = next(c for c in communities if "c" in c)
    ie = sm.internal_external_ratio(g, comm_c)
    assert ie["numerator"] == 4
    assert ie["denominator"] == 1
    assert math.isclose(ie["value"], 4.0)

    # Zero external edges: whole graph as one community -> explicit handling.
    ie_zero = sm.internal_external_ratio(g, set(g.nodes))
    assert ie_zero["status"] == "unavailable"
    assert ie_zero["value"] is None
    assert ie_zero["numerator"] == 8
    assert ie_zero["denominator"] == 0
    assert "zero external edges" in ie_zero["detail"]["reason"]


def test_one_community_graph_wcr_is_one():
    clique = nx.DiGraph()
    clique.add_edges_from([("x", "y"), ("y", "z"), ("z", "x")])
    cs = sm.community_structure(clique)
    assert cs["community_count"]["value"] == 1
    assert math.isclose(sm.within_community_rate(clique)["value"], 1.0)
    # Conductance undefined: no outside set.
    cond = cs["communities"][0]["conductance"]
    assert cond["status"] == "unavailable"


def test_empty_graph_community_structure_unavailable():
    cs = sm.community_structure(nx.DiGraph())
    assert cs["community_count"]["status"] == "unavailable"
    assert cs["modularity"]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# §14 null model
# ---------------------------------------------------------------------------

def test_null_model_deterministic_and_exposes_config():
    g = _two_triangles()
    first = sm.null_model_wcr(g, n_randomizations=5, seed=42)
    second = sm.null_model_wcr(g, n_randomizations=5, seed=42)
    assert first["status"] == "available"
    assert first == second, "same seed must reproduce identical nulls"
    assert first["n_randomizations"] == 5
    assert first["seed"] == 42
    assert len(first["null_values"]) == 5
    observed = sm.within_community_rate(g)["value"]
    expected_z = round(
        (observed - first["null_mean"]) / first["null_sd"], 6
    )
    assert first["z_score"] == expected_z
    assert first["preserves"] == [
        "node_count",
        "edge_count",
        "degree_sequence (undirected projection)",
    ]
    # Degree sequence actually preserved by the swap procedure itself.
    swapped = g.to_undirected().copy()
    import networkx.algorithms.swap as _swap

    _swap.double_edge_swap(swapped, nswap=swapped.number_of_edges(), max_tries=10000, seed=42)
    original = sorted(d for _, d in g.to_undirected().degree())
    after = sorted(d for _, d in swapped.degree())
    assert original == after


def test_null_model_too_small_graph_unavailable():
    tiny = nx.DiGraph()
    tiny.add_edges_from([("a", "b")])
    nm = sm.null_model_wcr(tiny)
    assert nm["status"] == "unavailable"
    assert "too small" in nm["detail"]["reason"]


# ---------------------------------------------------------------------------
# §15 community persistence
# ---------------------------------------------------------------------------

def test_community_persistence_deterministic_rows():
    layers = [
        (0, [("a", "b")]),
        (1, [("b", "c")]),
        (2, [("a", "b"), ("c", "a")]),  # re-observed edge dedups
    ]
    rows = sm.community_persistence(layers, seed_video_id="a")
    assert [r["layer_index"] for r in rows] == [0, 1, 2]
    assert rows[0]["node_count"] == 2 and rows[0]["edge_count"] == 1
    assert rows[1]["node_count"] == 3 and rows[1]["edge_count"] == 2
    # Re-observation collapses: still 3 edges, not 4.
    assert rows[2]["edge_count"] == 3
    assert rows[0]["persistence_jaccard_vs_previous"] is None
    for row in rows:
        assert row["dominant_community_share"] is not None
    assert rows[2]["within_community_recommendation_rate"] == 1.0


def test_community_persistence_no_edges_unavailable():
    rows = sm.community_persistence([(0, [])], seed_video_id="a")
    assert rows[0]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# §16/§17 centrality
# ---------------------------------------------------------------------------

def test_centrality_metrics_top_lists():
    cent = sm.centrality_metrics(_two_triangles())
    pr = cent["pagerank"]["detail"]["top"]
    hubs = cent["hits_hubs"]["detail"]["top"]
    auth = cent["hits_authorities"]["detail"]["top"]
    assert len(pr) == len(hubs) == len(auth) == 6
    assert pr[0]["id"] == "d"  # sink reached from both triangles
    assert cent["pagerank"]["category"] == "centrality"
    assert cent["pagerank"]["lens"] == "video"


def test_centrality_empty_graph_unavailable():
    cent = sm.centrality_metrics(nx.DiGraph())
    assert cent["pagerank"]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# §18/§19/§20 channel projection + concentration
# ---------------------------------------------------------------------------

def test_channel_projection_hhi_and_top_share():
    pairs = [
        ("X", "Y"),
        ("X", "Y"),
        ("X", "Z"),
        ("Z", "X"),
    ]
    weighted_in: dict[str, int] = {}
    for _s, t in pairs:
        weighted_in[t] = weighted_in.get(t, 0) + 1
    conc = sm.channel_concentration(weighted_in)
    # shares Y=.5 Z=.25 X=.25 -> HHI=.25+.0625+.0625=.375
    assert math.isclose(conc["hhi"]["value"], 0.375, abs_tol=1e-6)
    assert math.isclose(conc["top_channel_share"]["value"], 0.5)
    assert conc["unique_channel_count"]["value"] == 3
    assert conc["top_channel_share"]["numerator"] == 2
    assert conc["top_channel_share"]["denominator"] == 4
    ch_graph = sm.build_graph(pairs)
    assert ch_graph.number_of_edges() == 3  # duplicate X->Y collapsed


def test_channel_concentration_empty_unavailable():
    conc = sm.channel_concentration({})
    assert conc["hhi"]["status"] == "unavailable"
    assert conc["top_channel_share"]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# §36 metadata envelope contract
# ---------------------------------------------------------------------------

def test_envelopes_carry_required_metadata_fields():
    g = _two_triangles()
    for env in sm.standard_statistics(g):
        assert {"metric", "value", "status", "category", "lens"} <= set(env)
        assert env["category"] == "standard_statistic"
        assert env["lens"] == "video"
    wcr = sm.within_community_rate(g)
    assert {"metric", "value", "status", "category", "lens", "numerator", "denominator"} <= set(wcr)


# ---------------------------------------------------------------------------
# §27/§28 lens score normalization / weighting / final calculation
# ---------------------------------------------------------------------------

def test_lens_score_normalization_identity_on_unit_scale():
    result = compute_score({"s1": 0.5, "s2": 0.4, "s3": 0.2, "s4": None})
    comps = {c["key"]: c for c in result["components"]}
    assert comps["s1"]["value_raw"] == 0.5
    assert comps["s1"]["value_normalized"] == 0.5
    assert comps["s1"]["weight"] == 0.35
    assert comps["s1"]["lens"] == "video"
    assert comps["s2"]["lens"] == "video"
    assert comps["s3"]["lens"] == "channel"
    assert comps["s4"]["lens"] == "cross_lens"
    assert comps["s4"]["status"] == "unavailable"
    assert comps["s4"]["weighted_contribution"] == 0.0
    assert comps["s5"]["lens"] == "audience"


def test_lens_score_weighting_renormalized_over_available():
    result = compute_score({"s1": 0.5, "s2": 0.4, "s3": 0.2, "s4": None})
    # available weights .35/.30/.20 sum to .85
    expected = (0.35 * 0.5 + 0.30 * 0.4 + 0.20 * 0.2) / 0.85
    assert math.isclose(result["value"], round(expected, 6), abs_tol=1e-9)
    contributions = sum(
        c["weighted_contribution"] for c in result["components"]
    )
    # Effective weights renormalize to sum 1 over available components
    # (per-component rounding may differ by <= 1e-6 from the aggregate).
    assert math.isclose(contributions, result["value"], abs_tol=2e-6)


def test_lens_score_final_calculation_all_available():
    result = compute_score({"s1": 1.0, "s2": 1.0, "s3": 1.0, "s4": 1.0})
    assert math.isclose(result["value"], 1.0)
    assert result["verdict"] == "strong"
    result_mid = compute_score({"s1": 0.4, "s2": 0.4, "s3": 0.4, "s4": 0.4})
    assert math.isclose(result_mid["value"], 0.4)
    assert result_mid["verdict"] == "weak"  # band 0.40-0.60


def test_lens_score_out_of_range_value_is_clamped():
    result = compute_score({"s1": 1.5, "s2": 0.4, "s3": 0.2, "s4": 0.1})
    comps = {c["key"]: c for c in result["components"]}
    assert comps["s1"]["value_raw"] == 1.5
    assert comps["s1"]["value_normalized"] == 1.0


def test_lens_score_no_signals_inconclusive_not_zero():
    result = compute_score({"s1": None, "s2": None, "s3": None, "s4": None})
    assert result["value"] is None
    assert result["verdict"] == "inconclusive"
