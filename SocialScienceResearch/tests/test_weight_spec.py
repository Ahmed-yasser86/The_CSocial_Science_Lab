import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api.app import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.network_analytics_service import (
    NetworkAnalyticsService,
)
from SocialScienceResearch.services.weight_spec import (
    WeightSpec,
    WeightSpecError,
    edge_weight_for_mode,
    normalize_weights,
    parse_weight_spec,
    weight_options_catalog,
)

PREFIX = "/api/v1/social-science"


def _settings(tmp_path: Path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path), dataset_name="kc", backend="excel"
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed_karate(repos):
    import networkx as nx
    from SocialScienceResearch.domain.models import (
        Channel,
        CollectionRun,
        RecommendationObservation,
        RecommendationStatus,
        RunType,
        Video,
    )
    from SocialScienceResearch.utils.idgen import utcnow

    CHANNEL = "UC_kc"
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
    for (u, v) in club.edges():
        for s, t in ((u, v), (v, u)):
            repos.recommendations.save_recommendation(
                RecommendationObservation(
                    observation_id=f"o_{s}_{t}",
                    collection_run_id="kc",
                    source_video_id=str(s),
                    recommended_video_id=str(t),
                    position=(s % 5) + 1,
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


def _client_with_karate(tmp_path):
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="kc")
    )
    _seed_karate(repos)
    app = create_app(_settings(tmp_path))
    app.state.services["repos"] = repos
    app.state.workspace_runtime.sync = lambda app: None
    return TestClient(app), repos


# --- parser / validator unit tests ---------------------------------------


def test_parse_token_default_roundtrip():
    spec = parse_weight_spec("recommendation:observation_count")
    assert isinstance(spec, WeightSpec)
    assert spec.edge_type == "recommendation"
    assert spec.weight_mode == "observation_count"
    assert spec.normalization == "none"
    assert spec.params == {}
    assert spec.to_token() == "recommendation:observation_count"


def test_parse_token_with_params_and_norm():
    spec = parse_weight_spec("co_comment:jaccard:min_shared=2:norm=min_max")
    assert spec.edge_type == "co_comment"
    assert spec.weight_mode == "jaccard"
    assert spec.params == {"min_shared": 2}
    assert spec.normalization == "min_max"
    assert spec.to_token() == "co_comment:jaccard:min_shared=2:norm=min_max"


def test_parse_bare_normalization_shorthand():
    # tolerance: a trailing known normalization without `norm=` prefix.
    spec = parse_weight_spec("recommendation:reciprocal_position:min_max")
    assert spec.normalization == "min_max"


def test_parse_from_dict():
    spec = parse_weight_spec(
        {
            "edge_type": "recommendation",
            "weight_mode": "reciprocal_position",
            "normalization": "log1p",
            "params": {"position_decay": 0.5},
        }
    )
    assert spec.normalization == "log1p"
    assert spec.params == {"position_decay": 0.5}
    assert spec.to_dict()["edge_type"] == "recommendation"


def test_parse_rejects_unknown_edge_type():
    with pytest.raises(WeightSpecError) as exc:
        parse_weight_spec("bogus:observation_count")
    assert "edge_type" in str(exc.value)


def test_parse_rejects_unknown_weight_mode():
    with pytest.raises(WeightSpecError) as exc:
        parse_weight_spec("recommendation:bogus_mode")
    assert "weight_mode" in str(exc.value)


def test_parse_rejects_unknown_normalization():
    with pytest.raises(WeightSpecError) as exc:
        parse_weight_spec("recommendation:observation_count:norm=bogus")
    assert "normalization" in str(exc.value)


def test_parse_rejects_unknown_param():
    with pytest.raises(WeightSpecError) as exc:
        parse_weight_spec("recommendation:observation_count:foo=1")
    assert "param" in str(exc.value)


def test_parse_coerces_param_types():
    spec = parse_weight_spec("co_comment:jaccard:min_shared=3")
    assert spec.params["min_shared"] == 3
    assert isinstance(spec.params["min_shared"], int)


# --- catalog tests --------------------------------------------------------


def test_catalog_has_all_modes():
    catalog = weight_options_catalog()
    keys = {(o["edge_type"], o["weight_mode"]) for o in catalog}
    assert ("recommendation", "observation_count") in keys
    assert ("recommendation", "reciprocal_position") in keys
    assert ("co_comment", "jaccard") in keys
    # Audience family gated until N2.
    co_comment = next(
        o for o in catalog if o["edge_type"] == "co_comment"
    )
    assert co_comment["available"] is False


def test_catalog_availability_from_repos(tmp_path):
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="kc")
    )
    _seed_karate(repos)
    catalog = weight_options_catalog(repos=repos, run_id="kc")
    rec_obs = next(
        o
        for o in catalog
        if o["edge_type"] == "recommendation"
        and o["weight_mode"] == "observation_count"
    )
    rec_pos = next(
        o
        for o in catalog
        if o["edge_type"] == "recommendation"
        and o["weight_mode"] == "reciprocal_position"
    )
    assert rec_obs  # silence unused
    assert rec_obs["available"] is True
    assert rec_pos["available"] is True  # seeded edges carry position


# --- endpoint tests -------------------------------------------------------


def test_weight_options_endpoint(tmp_path):
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(f"{PREFIX}/network/weights/options?run_id=kc")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "options" in body
    modes = {(o["edge_type"], o["weight_mode"]) for o in body["options"]}
    assert ("recommendation", "observation_count") in modes
    rec_pos = next(
        o
        for o in body["options"]
        if o["edge_type"] == "recommendation"
        and o["weight_mode"] == "reciprocal_position"
    )
    assert rec_pos["available"] is True


# --- weight math unit tests ----------------------------------------------


def test_edge_weight_for_mode():
    assert edge_weight_for_mode("observation_count", None) == 1.0
    assert edge_weight_for_mode("observation_count", 3) == 1.0
    assert edge_weight_for_mode("reciprocal_position", 2) == 0.5
    # Missing/zero position falls back to structural weight.
    assert edge_weight_for_mode("reciprocal_position", None) == 1.0
    assert edge_weight_for_mode("reciprocal_position", 0) == 1.0


def test_normalize_weights():
    vals = [1.0, 2.0, 3.0]
    assert normalize_weights(vals, "none") == vals
    mm = normalize_weights(vals, "min_max")
    assert mm[0] == 0.0 and mm[-1] == 1.0
    # Constant input -> all 1.0 (no divide-by-zero).
    assert normalize_weights([5.0, 5.0], "min_max") == [1.0, 1.0]
    log = normalize_weights([0.0, 1.0], "log1p")
    assert log[0] == 0.0


# --- service-level weight application ------------------------------------


def _service_with_karate(tmp_path):
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="kc")
    )
    _seed_karate(repos)
    return NetworkAnalyticsService(repos), repos


def test_graph_default_weight_is_structural(tmp_path):
    svc, _ = _service_with_karate(tmp_path)
    payload = svc.graph(run_id="kc")
    assert payload.weight_spec is None
    assert all(e.weight == 1.0 for e in payload.edges)


def test_graph_reciprocal_position_changes_weights(tmp_path):
    svc, _ = _service_with_karate(tmp_path)
    payload = svc.graph(run_id="kc", weight_spec="recommendation:reciprocal_position")
    assert payload.weight_spec == {
        "edge_type": "recommendation",
        "weight_mode": "reciprocal_position",
        "params": {},
        "normalization": "none",
    }
    weights = [e.weight for e in payload.edges]
    # Not all 1.0 -> the spec actually applied.
    assert any(w != 1.0 for w in weights)
    # min_max normalization compresses into [0, 1]; values differ from raw 1/pos.
    norm = svc.graph(
        run_id="kc", weight_spec="recommendation:reciprocal_position:norm=min_max"
    )
    nweights = [e.weight for e in norm.edges]
    assert min(nweights) == 0.0
    assert max(nweights) == 1.0


def test_export_default_byte_identical_count(tmp_path):
    svc, _ = _service_with_karate(tmp_path)
    # Default export: aggregated weight == observation count per edge.
    _, csv_default, _ = svc.export_network(format="csv", run_id="kc")
    # reciprocal_position export yields different (non-integer) weights.
    _, csv_weighted, _ = svc.export_network(
        format="csv", run_id="kc", weight_spec="recommendation:reciprocal_position"
    )
    default_lines = csv_default.strip().splitlines()[1:]
    weighted_lines = csv_weighted.strip().splitlines()[1:]
    assert len(default_lines) == len(weighted_lines)
    # At least one edge's weight column differs.
    assert any(
        d.split(",")[2] != w.split(",")[2]
        for d, w in zip(default_lines, weighted_lines)
    )


def test_export_nondefault_adds_weight_definition(tmp_path):
    svc, _ = _service_with_karate(tmp_path)
    _, csv, _ = svc.export_network(
        format="csv",
        run_id="kc",
        weight_spec="recommendation:reciprocal_position:norm=min_max",
    )
    header = csv.strip().splitlines()[0]
    assert "weight_definition" in header
    # JSON echoes the weight spec only when non-default.
    _, js, _ = svc.export_network(
        format="json", run_id="kc", weight_spec="recommendation:reciprocal_position"
    )
    import json as _json

    assert _json.loads(js).get("weight_spec") is not None
    _, js_def, _ = svc.export_network(format="json", run_id="kc")
    assert _json.loads(js_def).get("weight_spec") is None


def test_centralities_weighted_differs(tmp_path):
    svc, _ = _service_with_karate(tmp_path)
    base = svc.centralities(run_id="kc")
    weighted = svc.centralities(
        run_id="kc",
        weight_spec="recommendation:reciprocal_position",
        weighted=True,
    )
    assert set(base) == set(weighted)
    # Weighted eigenvector/betweenness diverge from the structural defaults.
    assert any(
        base[n]["eigenvector"] != weighted[n]["eigenvector"] for n in base
    )
    assert any(
        base[n]["betweenness"] != weighted[n]["betweenness"] for n in base
    )


# --- endpoint weight param -------------------------------------------------


def test_graph_endpoint_rejects_bad_weight(tmp_path):
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(f"{PREFIX}/network/graph?run_id=kc&weight=bogus:mode")
    assert resp.status_code == 400


def test_graph_endpoint_applies_weight(tmp_path):
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(
        f"{PREFIX}/network/graph?run_id=kc&weight=recommendation:reciprocal_position"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weight_spec"]["weight_mode"] == "reciprocal_position"


def test_export_endpoint_rejects_bad_weight(tmp_path):
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(f"{PREFIX}/network/export?run_id=kc&weight=bogus:mode")
    assert resp.status_code == 400


def test_centralities_endpoint_weighted(tmp_path):
    client, _ = _client_with_karate(tmp_path)
    resp = client.get(
        f"{PREFIX}/network/centralities?run_id=kc&weight="
        "recommendation:reciprocal_position&weighted=true"
    )
    assert resp.status_code == 200, resp.text
    # Sanity: still the karate club node set.
    assert set(resp.json()["nodes"]) == {str(i) for i in range(34)}
