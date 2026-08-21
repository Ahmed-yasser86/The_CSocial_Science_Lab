"""Tests for the longitudinal service and its router endpoints.

Service tests seed data through the repositories and call
``LongitudinalService`` directly, asserting known growth % values, run-snapshot
deltas and observation gaps. Endpoint tests exercise the router via
``TestClient`` (including a pagination-envelope assertion on the history list
endpoints); the app import is guarded so the service tests still run while the
other module agents are mid-build.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.longitudinal_service import LongitudinalService

D0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
D1 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
D7 = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)
D20 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
PREFIX = "/api/v1/social-science"


def _add_save_video(excel_repos, video_id, *, views, likes=0, comments=0, **kwargs):
    excel_repos.videos.save_video_observation(
        VideoObservation(
            observation_id=kwargs.get("observation_id", f"obs_{video_id}"),
            collection_run_id=kwargs.get("run_id", "run_a"),
            video_id=video_id,
            observed_at=kwargs.get("observed_at", D0),
            view_count=views,
            like_count=likes,
            comment_count=comments,
        )
    )


# ----------------------------------------------------------------------
# Histories with step growth
# ----------------------------------------------------------------------
def test_channel_history_step_growth(excel_repos):
    cid = "UCx"
    excel_repos.channels.upsert_channel(
        Channel(channel_id=cid, url="https://www.youtube.com/channel/UCx", title="C", first_observed_run_id="run_a")
    )
    excel_repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="o1", collection_run_id="run_a", channel_id=cid,
            observed_at=D0, subscriber_count=1000, video_count=10, view_count=100000,
        )
    )
    excel_repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="o2", collection_run_id="run_b", channel_id=cid,
            observed_at=D1, subscriber_count=1100, video_count=12, view_count=120000,
        )
    )
    history = LongitudinalService(excel_repos).channel_history(cid)
    assert [p.observation_id for p in history] == ["o1", "o2"]
    assert history[0].subscriber_growth_pct is None
    assert history[1].subscriber_growth_pct == pytest.approx(10.0)
    assert history[1].video_growth_pct == pytest.approx(20.0)
    assert history[1].view_growth_pct == pytest.approx(20.0)


def test_video_history_step_growth(excel_repos):
    vid = "v1"
    excel_repos.videos.upsert_video(
        Video(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title="V1", first_observed_run_id="run_a")
    )
    _add_save_video(excel_repos, vid, run_id="run_a", observation_id="vo1", observed_at=D0, views=100, likes=50, comments=10)
    _add_save_video(excel_repos, vid, run_id="run_b", observation_id="vo2", observed_at=D1, views=200, likes=60, comments=15)
    history = LongitudinalService(excel_repos).video_history(vid)
    assert [p.observation_id for p in history] == ["vo1", "vo2"]
    assert history[0].view_growth_pct is None
    assert history[1].view_growth_pct == pytest.approx(100.0)
    assert history[1].like_growth_pct == pytest.approx(20.0)
    assert history[1].comment_growth_pct == pytest.approx(50.0)
    assert history[1].favorite_growth_pct == 0.0  # both None -> flat


def test_video_history_empty(excel_repos):
    assert LongitudinalService(excel_repos).video_history("ghost") == []


# ----------------------------------------------------------------------
# Run deltas
# ----------------------------------------------------------------------
@pytest.fixture
def run_corpus(excel_repos):
    for run_id, at in (("run_a", D0), ("run_b", D1)):
        excel_repos.runs.create_run(
            CollectionRun(
                run_id=run_id,
                run_type=RunType.VIDEO,
                target_url="https://www.youtube.com/watch?v=v1",
                target_video_id="v1",
                started_at=at,
                status="success",
            )
        )
    for vid, title in (("v1", "One"), ("v_old", "Old")):
        excel_repos.videos.upsert_video(
            Video(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=title, first_observed_run_id="run_a")
        )
    excel_repos.videos.upsert_video(
        Video(video_id="v_new", url="https://www.youtube.com/watch?v=v_new", title="New", first_observed_run_id="run_b")
    )
    _add_save_video(excel_repos, "v1", run_id="run_a", observation_id="vo1", observed_at=D0, views=100, likes=50, comments=10)
    _add_save_video(excel_repos, "v1", run_id="run_b", observation_id="vo2", observed_at=D1, views=150, likes=60, comments=15)
    _add_save_video(excel_repos, "v_old", run_id="run_a", observation_id="vo3", observed_at=D0, views=10)
    _add_save_video(excel_repos, "v_new", run_id="run_b", observation_id="vo4", observed_at=D1, views=25)
    return excel_repos


def test_run_deltas_changed_new_disappeared(run_corpus):
    result = LongitudinalService(run_corpus).run_deltas("run_a", "run_b")
    assert result.run_type == "video"
    assert result.entity_count_a == 2
    assert result.entity_count_b == 2
    assert [e.entity_id for e in result.changed] == ["v1"]
    assert [e.entity_id for e in result.new] == ["v_new"]
    assert [e.entity_id for e in result.disappeared] == ["v_old"]
    delta = result.changed[0]
    by_metric = {m.metric: m for m in delta.metric_deltas}
    assert by_metric["view_count"].previous == 100
    assert by_metric["view_count"].current == 150
    assert by_metric["view_count"].absolute_change == 50
    assert by_metric["view_count"].growth_pct == pytest.approx(50.0)
    assert by_metric["like_count"].growth_pct == pytest.approx(20.0)
    assert by_metric["comment_count"].growth_pct == pytest.approx(50.0)


def test_run_deltas_unknown_run_raises(excel_repos):
    with pytest.raises(ValueError):
        LongitudinalService(excel_repos).run_deltas("nope", "nope2")


def test_run_deltas_mismatched_types_raise(excel_repos):
    excel_repos.runs.create_run(
        CollectionRun(run_id="rc", run_type=RunType.CHANNEL, target_url="https://www.youtube.com/@@x", started_at=D0, status="success")
    )
    excel_repos.runs.create_run(
        CollectionRun(run_id="rv", run_type=RunType.VIDEO, target_url="https://www.youtube.com/watch?v=x", started_at=D1, status="success")
    )
    with pytest.raises(ValueError):
        LongitudinalService(excel_repos).run_deltas("rc", "rv")


def test_run_entity_deltas_uses_previous_run(run_corpus):
    result = LongitudinalService(run_corpus).run_entity_deltas("run_b")
    assert result.run_id_a == "run_a"
    assert result.run_id_b == "run_b"
    assert [e.entity_id for e in result.changed] == ["v1"]


def test_run_entity_deltas_without_predecessor_raises(run_corpus):
    with pytest.raises(ValueError):
        LongitudinalService(run_corpus).run_entity_deltas("run_a")


# ----------------------------------------------------------------------
# Observation gaps
# ----------------------------------------------------------------------
def test_observation_gaps_channel(excel_repos):
    cid = "UCx"
    excel_repos.channels.upsert_channel(
        Channel(channel_id=cid, url="https://www.youtube.com/channel/UCx", title="C", first_observed_run_id="run_a")
    )
    for obs_id, at in (("o0", D0), ("o7", D7), ("o20", D20)):
        excel_repos.channels.save_channel_observation(
            ChannelObservation(
                observation_id=obs_id, collection_run_id="run_x", channel_id=cid,
                observed_at=at, subscriber_count=1000,
            )
        )
    service = LongitudinalService(excel_repos)
    sparse = service.observation_gaps("channel", cid, min_gap_days=10.0)
    assert [(g.from_observed_at, g.to_observed_at) for g in sparse] == [(D7, D20)]
    assert sparse[0].gap_days == pytest.approx(13.0)
    dense = service.observation_gaps("channel", cid, min_gap_days=6.0)
    assert len(dense) == 2


def test_observation_gaps_invalid_entity(excel_repos):
    with pytest.raises(ValueError):
        LongitudinalService(excel_repos).observation_gaps("widget", "x")


# ----------------------------------------------------------------------
# Endpoints via TestClient (guarded against the parallel module build)
# ----------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    try:
        from SocialScienceResearch.api import create_app
    except Exception as exc:  # another module agent is mid-build
        pytest.skip(f"app not importable yet (parallel module build): {exc}")
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "b3long")
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="b3long")
    repos = build_excel_repositories(repo_settings)

    repos.runs.create_run(
        CollectionRun(run_id="run_a", run_type=RunType.VIDEO, target_url="https://www.youtube.com/watch?v=v1", target_video_id="v1", started_at=D0, status="success")
    )
    repos.runs.create_run(
        CollectionRun(run_id="run_b", run_type=RunType.VIDEO, target_url="https://www.youtube.com/watch?v=v1", target_video_id="v1", started_at=D1, status="success")
    )
    cid = "UCx"
    repos.channels.upsert_channel(
        Channel(channel_id=cid, url="https://www.youtube.com/channel/UCx", title="Chan", first_observed_run_id="run_a")
    )
    repos.channels.save_channel_observation(
        ChannelObservation(observation_id="co1", collection_run_id="run_a", channel_id=cid, observed_at=D0, subscriber_count=1000, video_count=10, view_count=100000)
    )
    repos.channels.save_channel_observation(
        ChannelObservation(observation_id="co2", collection_run_id="run_b", channel_id=cid, observed_at=D1, subscriber_count=1100, video_count=12, view_count=120000)
    )
    for vid, title, first_run in (("v1", "V1", "run_a"), ("v_old", "Old", "run_a"), ("v_new", "New", "run_b")):
        repos.videos.upsert_video(
            Video(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", channel_id=cid, title=title, first_observed_run_id=first_run)
        )
    _add_save_video(repos, "v1", run_id="run_a", observation_id="vo1", observed_at=D0, views=100, likes=50, comments=10)
    _add_save_video(repos, "v1", run_id="run_b", observation_id="vo2", observed_at=D1, views=150, likes=60, comments=15)
    _add_save_video(repos, "v_old", run_id="run_a", observation_id="vo3", observed_at=D0, views=10)
    _add_save_video(repos, "v_new", run_id="run_b", observation_id="vo4", observed_at=D1, views=25)
    repos.store.close()

    settings = SocialScienceSettings(
        repository=repo_settings, api=ApiSettings(prefix=PREFIX)
    )
    from fastapi.testclient import TestClient

    yield TestClient(create_app(settings))


def test_video_history_pagination_envelope(client):
    resp = client.get(f"{PREFIX}/videos/v1/history", params={"page_size": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert {"items", "next_cursor", "has_more", "total"} <= set(body)
    assert body["total"] == 2
    assert body["has_more"] is True
    assert body["next_cursor"] is not None
    assert len(body["items"]) == 1
    assert body["items"][0]["observation_id"] == "vo1"

    next_page = client.get(
        f"{PREFIX}/videos/v1/history",
        params={"page_size": 1, "cursor": body["next_cursor"]},
    )
    assert next_page.status_code == 200
    nbody = next_page.json()
    assert nbody["has_more"] is False
    assert nbody["next_cursor"] is None
    assert len(nbody["items"]) == 1
    assert nbody["items"][0]["observation_id"] == "vo2"


def test_channel_history_endpoint_growth(client):
    resp = client.get(f"{PREFIX}/channels/UCx/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    points = body["items"]
    assert points[0]["subscriber_growth_pct"] is None
    assert points[1]["subscriber_growth_pct"] == pytest.approx(10.0)
    assert points[1]["view_growth_pct"] == pytest.approx(20.0)
    # pagination envelope present
    assert "items" in body and "next_cursor" in body and "has_more" in body


def test_run_deltas_endpoint(client):
    resp = client.get(f"{PREFIX}/runs/run_b/deltas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id_a"] == "run_a"
    assert body["run_id_b"] == "run_b"
    assert [e["entity_id"] for e in body["changed"]] == ["v1"]
    assert [e["entity_id"] for e in body["new"]] == ["v_new"]
    assert [e["entity_id"] for e in body["disappeared"]] == ["v_old"]
    view = {m["metric"]: m for m in body["changed"][0]["metric_deltas"]}["view_count"]
    assert view["absolute_change"] == 50
    assert view["growth_pct"] == pytest.approx(50.0)