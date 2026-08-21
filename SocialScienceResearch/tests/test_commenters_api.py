"""API tests for the commenter-overlap endpoints.

Exercises ``GET /network/commenters/overlap`` and
``GET /network/commenters/{author_key}/profile`` against a seeded corpus:
400 on an empty scope, the response contract (heatmap symmetry, metric-driven
ordering, caps), and 200/404 profile lookups for id- and name-backed authors.
"""

from __future__ import annotations

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

PREFIX = "/api/v1/social-science"

T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="commenters"),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="commenters")
    )
    repos.videos.upsert_video(
        Video(
            video_id="v1",
            url="https://www.youtube.com/watch?v=v1",
            channel_id="UC1",
            title="Video One",
            first_observed_run_id="r_commenters",
        )
    )
    repos.videos.upsert_video(
        Video(
            video_id="v2",
            url="https://www.youtube.com/watch?v=v2",
            channel_id="UC2",
            title="Video Two",
            first_observed_run_id="r_commenters",
        )
    )
    for cid in ("UC1", "UC2"):
        repos.channels.upsert_channel(
            Channel(
                channel_id=cid,
                url=f"https://www.youtube.com/channel/{cid}",
                title=f"Channel {cid}",
                first_observed_run_id="r_commenters",
            )
        )
    comments = [
        Comment(
            comment_id="a1", video_id="v1", author_id="UCid_alice",
            author_name="Alice", comment_text="on v1",
            published_at=T0, first_observed_run_id="r_commenters",
        ),
        Comment(
            comment_id="a2", video_id="v2", author_id="UCid_alice",
            author_name="Alice", comment_text="on v2",
            published_at=T0, first_observed_run_id="r_commenters",
        ),
        Comment(
            comment_id="b1", video_id="v1", author_id="UCid_bob",
            author_name="Bob", comment_text="bob v1",
            published_at=T0, first_observed_run_id="r_commenters",
        ),
        Comment(
            comment_id="c1", video_id="v1", author_name="Carol",
            comment_text="carol v1", published_at=T0,
            first_observed_run_id="r_commenters",
        ),
    ]
    for comment in comments:
        repos.comments.upsert_comment(comment)
    repos.store.close()


@pytest.fixture
def client(tmp_path):
    _seed(tmp_path)
    return TestClient(create_app(_settings(tmp_path)))


def test_overlap_empty_scope_400(client) -> None:
    resp = client.get(f"{PREFIX}/network/commenters/overlap")
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_overlap_result_contract(client) -> None:
    resp = client.get(
        f"{PREFIX}/network/commenters/overlap?video_ids=v1,v2&channel_ids=UC1,UC2"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric"] == "jaccard"
    assert body["scope"] == {"video_ids": ["v1", "v2"], "channel_ids": ["UC1", "UC2"]}
    assert body["videos"]["entity_type"] == "video"
    assert body["channels"]["entity_type"] == "channel"

    pair = next(
        p
        for p in body["videos"]["pairs"]
        if {p["entity_a"], p["entity_b"]} == {"v1", "v2"}
    )
    assert pair["intersection_size"] == 1  # alice
    assert pair["jaccard"] == pytest.approx(1 / 3)
    assert pair["shared_commenters"][0]["author_key"] == "UCid_alice"
    assert pair["shared_commenters"][0]["identity_kind"] == "id"

    # Heatmap symmetric, diagonal absent.
    heatmap = body["videos"]["heatmap"]
    assert heatmap["v1"]["v2"] == heatmap["v2"]["v1"]
    assert "v1" not in heatmap.get("v1", {})

    # Overlap edges threshold (min_shared=1 default includes the shared pair).
    edges = body["videos"]["overlap_edges"]
    assert any(e["shared_commenter_count"] == 1 for e in edges)


def test_overlap_metric_param_changes_ordering(client) -> None:
    resp = client.get(
        f"{PREFIX}/network/commenters/overlap?video_ids=v1,v2&metric=intersection"
    )
    assert resp.status_code == 200
    assert resp.json()["metric"] == "intersection"
    assert resp.json()["videos"]["pairs"][0]["intersection_size"] == 1


def test_overlap_invalid_metric_400(client) -> None:
    resp = client.get(
        f"{PREFIX}/network/commenters/overlap?video_ids=v1,v2&metric=euclidean"
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_profile_id_backed(client) -> None:
    resp = client.get(f"{PREFIX}/network/commenters/UCid_alice/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["author_key"] == "UCid_alice"
    assert body["identity_kind"] == "id"
    assert body["total_comments"] == 2
    assert body["video_count"] == 2
    assert {v["video_id"] for v in body["videos"]} == {"v1", "v2"}


def test_profile_name_backed(client) -> None:
    from urllib.parse import quote

    resp = client.get(
        f"{PREFIX}/network/commenters/{quote('Carol')}/profile"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["author_key"] == "Carol"
    assert body["identity_kind"] == "name"
    assert body["total_comments"] == 1


def test_profile_unknown_404(client) -> None:
    resp = client.get(f"{PREFIX}/network/commenters/ghost/profile")
    assert resp.status_code == 404
