"""Tests for the comment analytics service and its router endpoints.

Service tests seed data through the repositories and call
``CommentAnalyticsService`` directly, asserting known statistic values (e.g.
Gini of ``[1, 1, 1] == 0``, thread sizes). Endpoint tests exercise the router
via ``TestClient`` like ``tests/test_api.py``; the app import is guarded so
the service tests still run while the other module agents are mid-build.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from SocialScienceResearch.config.settings import (
    ApiSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.models import Comment, Video
from SocialScienceResearch.domain.query import CommentFilter
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.comment_analytics_service import (
    CommentAnalyticsService,
)

UPLOAD = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
PREFIX = "/api/v1/social-science"


def _add_video(repos, video_id="vid", *, upload=None):
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id="UCx",
            title=f"Video {video_id}",
            upload_timestamp=upload,
            first_observed_run_id="run_1",
        )
    )


def _add_comment(
    repos,
    comment_id,
    *,
    video_id="vid",
    author_id=None,
    author_name=None,
    published_at=None,
    is_reply=False,
    parent_comment_id=None,
    comment_text="text",
):
    repos.comments.upsert_comment(
        Comment(
            comment_id=comment_id,
            video_id=video_id,
            author_id=author_id,
            author_name=author_name,
            comment_text=comment_text,
            published_at=published_at,
            is_reply=is_reply,
            parent_comment_id=parent_comment_id,
            first_observed_run_id="run_1",
        )
    )


# ----------------------------------------------------------------------
# Participation
# ----------------------------------------------------------------------
def test_participation_equal_counts_gini_zero(excel_repos):
    for author in ("a", "b", "c"):
        _add_comment(excel_repos, f"c_{author}", author_id=author, author_name=author.upper())
    result = CommentAnalyticsService(excel_repos).participation("vid")
    assert result.total_comments == 3
    assert result.unique_authors == 3
    assert result.repeat_authors == 0
    assert result.repeat_author_share == 0.0
    assert result.participation_gini == 0.0  # Gini of [1, 1, 1]


def test_participation_concentration_and_repeat(excel_repos):
    for i in range(3):
        _add_comment(excel_repos, f"a{i}", author_id="a", author_name="A")
    _add_comment(excel_repos, "b1", author_id="b", author_name="B")
    _add_comment(excel_repos, "c1", author_id="c", author_name="C")
    result = CommentAnalyticsService(excel_repos).participation("vid")
    assert result.total_comments == 5
    assert result.unique_authors == 3
    assert result.repeat_authors == 1
    assert result.repeat_author_share == pytest.approx(1 / 3)
    # Gini([3, 1, 1]) = 4/15 via Brown's formula.
    assert result.participation_gini == pytest.approx(4 / 15)
    # Top 10% = the single largest author, holding 3 of 5 comments.
    counts = {a.author_id: a.comment_count for a in result.author_comment_counts}
    assert counts == {"a": 3, "b": 1, "c": 1}
    assert result.top_10pct_concentration == pytest.approx(0.6)


def test_participation_empty_video(excel_repos):
    result = CommentAnalyticsService(excel_repos).participation("vid")
    assert result.total_comments == 0
    assert result.unique_authors == 0
    assert result.repeat_author_share is None
    assert result.participation_gini is None


def test_participation_author_name_fallback(excel_repos):
    _add_comment(excel_repos, "c1", author_name="Researcher A")
    _add_comment(excel_repos, "c2", author_name="Researcher A")
    result = CommentAnalyticsService(excel_repos).participation("vid")
    assert result.unique_authors == 1
    assert result.repeat_authors == 1
    assert result.author_comment_counts[0].author_name == "Researcher A"
    assert result.author_comment_counts[0].comment_count == 2


# ----------------------------------------------------------------------
# Reply / thread metrics
# ----------------------------------------------------------------------
def test_reply_metrics_thread_breakdown(excel_repos):
    _add_comment(excel_repos, "root1", is_reply=False)
    _add_comment(excel_repos, "r1a", is_reply=True, parent_comment_id="root1")
    _add_comment(excel_repos, "r1b", is_reply=True, parent_comment_id="root1")
    _add_comment(excel_repos, "root2", is_reply=False)
    _add_comment(excel_repos, "r2a", is_reply=True, parent_comment_id="root2")
    _add_comment(excel_repos, "r2aa", is_reply=True, parent_comment_id="r2a")
    _add_comment(excel_repos, "root3", is_reply=False)
    _add_comment(excel_repos, "r3a", is_reply=True, parent_comment_id="root3")
    _add_comment(excel_repos, "r3aa", is_reply=True, parent_comment_id="r3a")
    _add_comment(excel_repos, "r3aaa", is_reply=True, parent_comment_id="r3aa")

    result = CommentAnalyticsService(excel_repos).reply_metrics("vid")
    assert result.total_comments == 10
    assert result.reply_count == 7
    assert result.reply_rate == pytest.approx(0.7)
    assert result.orphan_reply_count == 0
    assert result.thread_count == 3
    assert result.deepest_thread_depth == 4
    assert result.thread_size_mean == pytest.approx(10 / 3)
    assert result.thread_size_median == 3.0
    sizes = {t.root_comment_id: t.size for t in result.threads}
    assert sizes == {"root1": 3, "root2": 3, "root3": 4}


def test_reply_metrics_orphan_reply_is_reported(excel_repos):
    _add_comment(excel_repos, "root", is_reply=False)
    _add_comment(excel_repos, "orph", is_reply=True, parent_comment_id="ghost_parent")
    result = CommentAnalyticsService(excel_repos).reply_metrics("vid")
    assert result.orphan_reply_count == 1
    assert result.thread_count == 2  # root thread + orphan-anchored thread


def test_reply_metrics_cycled_parents_terminate(excel_repos):
    _add_comment(excel_repos, "x", is_reply=True, parent_comment_id="y")
    _add_comment(excel_repos, "y", is_reply=True, parent_comment_id="x")
    result = CommentAnalyticsService(excel_repos).reply_metrics("vid")
    # The bounded walk terminates (no infinite loop); each cycle member anchors
    # its own size-1 thread.
    assert result.total_comments == 2
    assert result.reply_count == 2
    assert result.thread_count == 2
    sizes = {t.root_comment_id: t.size for t in result.threads}
    assert sizes == {"x": 1, "y": 1}


# ----------------------------------------------------------------------
# Comment age at posting
# ----------------------------------------------------------------------
def test_comment_age_at_posting(excel_repos):
    _add_video(excel_repos, upload=UPLOAD)
    _add_comment(excel_repos, "c1", published_at=UPLOAD + timedelta(hours=1))
    _add_comment(excel_repos, "c2", published_at=UPLOAD + timedelta(hours=2))
    _add_comment(excel_repos, "c3", published_at=UPLOAD - timedelta(seconds=60))
    result = CommentAnalyticsService(excel_repos).comment_age_at_posting("vid")
    assert result.upload_missing is False
    assert result.aged_comments == 3
    assert result.negative_age_count == 1
    assert result.mean_age_seconds == pytest.approx(3580.0)
    assert result.median_age_seconds == 3600.0


def test_comment_age_missing_upload_is_explicit(excel_repos):
    _add_comment(excel_repos, "c1", published_at=UPLOAD + timedelta(hours=1))
    result = CommentAnalyticsService(excel_repos).comment_age_at_posting("vid")
    assert result.upload_missing is True
    assert result.aged_comments == 0
    assert result.mean_age_seconds is None
    assert result.median_age_seconds is None
    assert result.negative_age_count == 0


# ----------------------------------------------------------------------
# Velocity / decay
# ----------------------------------------------------------------------
def test_velocity_decay_buckets_and_shares(excel_repos):
    _add_video(excel_repos, upload=UPLOAD)
    _add_comment(excel_repos, "c1", published_at=UPLOAD + timedelta(hours=1))
    _add_comment(excel_repos, "c2", published_at=UPLOAD + timedelta(hours=2))
    _add_comment(excel_repos, "c3", published_at=UPLOAD + timedelta(days=2))
    _add_comment(excel_repos, "c4", published_at=UPLOAD + timedelta(days=10))
    _add_comment(excel_repos, "c5", published_at=None)
    result = CommentAnalyticsService(excel_repos).velocity_decay("vid", bucket="day")
    days = {p.bucket: p.count for p in result.timeline}
    assert days == {"2026-08-01": 2, "2026-08-03": 1, "2026-08-11": 1}
    assert result.missing_published_at == 1
    assert result.timestamped_comments == 4
    assert result.first_24h_share == pytest.approx(0.5)
    assert result.first_7d_share == pytest.approx(0.75)


def test_velocity_decay_hour_bucket(excel_repos):
    _add_comment(excel_repos, "c1", published_at=UPLOAD + timedelta(hours=1))
    _add_comment(excel_repos, "c2", published_at=UPLOAD + timedelta(hours=1, minutes=30))
    result = CommentAnalyticsService(excel_repos).velocity_decay("vid", bucket="hour")
    assert {p.bucket: p.count for p in result.timeline} == {"2026-08-01T13:00": 2}


def test_velocity_decay_invalid_bucket(excel_repos):
    with pytest.raises(ValueError):
        CommentAnalyticsService(excel_repos).velocity_decay("vid", bucket="week")


def test_velocity_decay_missing_upload_shares_none(excel_repos):
    _add_video(excel_repos, upload=None)
    _add_comment(excel_repos, "c1", published_at=UPLOAD)
    result = CommentAnalyticsService(excel_repos).velocity_decay("vid", bucket="day")
    assert result.upload_missing is True
    assert result.first_24h_share is None
    assert result.first_7d_share is None


def test_velocity_decay_wires_comment_filter(excel_repos):
    _add_video(excel_repos, upload=UPLOAD)
    _add_comment(excel_repos, "c1", published_at=UPLOAD, is_reply=False)
    _add_comment(excel_repos, "c2", published_at=UPLOAD + timedelta(days=3), is_reply=True, parent_comment_id="c1")
    result = CommentAnalyticsService(excel_repos).velocity_decay(
        "vid", bucket="day", filter=CommentFilter(only_roots=True)
    )
    assert result.total_comments == 1
    assert result.timeline[0].bucket == "2026-08-01"


def test_participation_wires_comment_filter(excel_repos):
    _add_comment(excel_repos, "root1", author_id="a", is_reply=False)
    _add_comment(excel_repos, "root2", author_id="a", is_reply=False)
    _add_comment(excel_repos, "reply1", author_id="a", is_reply=True, parent_comment_id="root1")
    _add_comment(excel_repos, "root3", author_id="b", is_reply=False)
    all_results = CommentAnalyticsService(excel_repos).participation("vid")
    assert all_results.total_comments == 4
    roots = CommentAnalyticsService(excel_repos).participation(
        "vid", filter=CommentFilter(only_roots=True)
    )
    assert roots.total_comments == 3
    assert roots.unique_authors == 2


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
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "b3comment")
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="b3comment")
    repos = build_excel_repositories(repo_settings)
    _add_video(repos, "v1", upload=UPLOAD)
    _add_comment(repos, "root1", video_id="v1", author_id="a", is_reply=False)
    _add_comment(repos, "r1", video_id="v1", author_id="a", is_reply=True, parent_comment_id="root1")
    _add_comment(
        repos,
        "c1",
        video_id="v1",
        author_id="b",
        is_reply=False,
        published_at=UPLOAD + timedelta(hours=1),
    )
    repos.store.close()
    settings = SocialScienceSettings(
        repository=repo_settings, api=ApiSettings(prefix=PREFIX)
    )
    from fastapi.testclient import TestClient

    yield TestClient(create_app(settings))


def test_participation_endpoint(client):
    resp = client.get(f"{PREFIX}/videos/v1/comments/analytics/participation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "v1"
    assert body["total_comments"] == 3
    assert body["unique_authors"] == 2
    assert body["repeat_authors"] == 1


def test_replies_endpoint(client):
    resp = client.get(f"{PREFIX}/videos/v1/comments/analytics/replies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply_count"] == 1
    assert body["reply_rate"] == pytest.approx(1 / 3)
    assert body["thread_count"] == 2


def test_velocity_endpoint_and_invalid_bucket(client):
    resp = client.get(
        f"{PREFIX}/videos/v1/comments/analytics/velocity", params={"bucket": "day"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_comments"] == 3
    assert body["missing_published_at"] == 2
    bad = client.get(
        f"{PREFIX}/videos/v1/comments/analytics/velocity", params={"bucket": "week"}
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "invalid_argument"