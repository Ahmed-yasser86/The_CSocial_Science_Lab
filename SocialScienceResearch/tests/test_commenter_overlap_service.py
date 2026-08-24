"""Tests for ``CommenterOverlapService`` (audience duplication analytics).

Seeds a deterministic comment corpus across 4 videos / 2 channels:

* ``v1`` (UC1): alice(id) x2, bob(id), carol(name-only), dave(id), one anonymous
* ``v2`` (UC1): alice x1, bob x1
* ``v3`` (UC2): alice x1, carol x1, eve(id) x1
* ``v4`` (UC2): eve x1

Hand-computed expectations:
* v1 commenter set = {alice, bob, carol, dave}, comments 6, unidentified 1,
  identity_coverage 5/6.
* pair (v1, v2): shared {alice, bob} (2), union 4 -> jaccard 0.5,
  overlap_coefficient 1.0 (2 / min(4,2)), reach_overlap_pct 0.5.
* bridges (>= 2 distinct videos): alice(3 videos, 2 channels), carol,
  bob, eve.
* channel projection (UC1, UC2): shared {alice, carol} (2), jaccard 0.4.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import Comment
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapService,
    resolve_author,
)

T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _comment(
    comment_id: str,
    video_id: str,
    *,
    author_id: str | None = None,
    author_name: str | None = None,
    published: datetime | None = None,
    is_reply: bool = False,
    parent: str | None = None,
    text: str | None = None,
) -> Comment:
    return Comment(
        comment_id=comment_id,
        video_id=video_id,
        author_id=author_id,
        author_name=author_name,
        comment_text=text,
        published_at=published,
        is_reply=is_reply,
        parent_comment_id=parent,
        first_observed_run_id="run_overlap",
    )


def _seed(repos) -> None:
    for video_id, channel_id, title in (
        ("v1", "UC1", "Video One"),
        ("v2", "UC1", "Video Two"),
        ("v3", "UC2", "Video Three"),
        ("v4", "UC2", "Video Four"),
    ):
        from SocialScienceResearch.domain.models import Channel, Video

        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id=channel_id,
                title=title,
                first_observed_run_id="run_overlap",
            )
        )
        repos.channels.upsert_channel(
            Channel(
                channel_id=channel_id,
                url=f"https://www.youtube.com/channel/{channel_id}",
                title=f"Channel {channel_id}",
                first_observed_run_id="run_overlap",
            )
        )

    comments = [
        # v1: 4 distinct authors + anonymous.
        _comment("c1", "v1", author_id="UCid_alice", author_name="Alice",
                 published=T0, text="alice root on v1"),
        _comment("c2", "v1", author_id="UCid_alice", author_name="Alice",
                 published=T0 + timedelta(minutes=1), is_reply=True,
                 parent="c3", text="alice replies to bob"),
        _comment("c3", "v1", author_id="UCid_bob", author_name="Bob",
                 published=T0, text="bob root on v1"),
        _comment("c4", "v1", author_name="Carol", published=T0 + timedelta(minutes=2)),
        _comment("c5", "v1", author_id="UCid_dave", author_name="Dave",
                 published=T0 + timedelta(minutes=3)),
        _comment("c6", "v1"),  # anonymous, excluded
        # v2
        _comment("c7", "v2", author_id="UCid_alice", author_name="Alice",
                 published=T0 + timedelta(days=1)),
        _comment("c8", "v2", author_id="UCid_bob", author_name="Bob",
                 published=T0 + timedelta(days=1)),
        # v3
        _comment("c9", "v3", author_id="UCid_alice", author_name="Alice",
                 published=T0 + timedelta(days=2)),
        _comment("c10", "v3", author_name="Carol", published=T0 + timedelta(days=2)),
        _comment("c11", "v3", author_id="UCid_eve", author_name="Eve",
                 published=T0 + timedelta(days=2)),
        # v4
        _comment("c12", "v4", author_id="UCid_eve", author_name="Eve",
                 published=T0 + timedelta(days=3)),
    ]
    for comment in comments:
        repos.comments.upsert_comment(comment)


def _service(excel_repos) -> CommenterOverlapService:
    _seed(excel_repos)
    return CommenterOverlapService(excel_repos)


# ----------------------------------------------------------------------
# Identity resolution
# ----------------------------------------------------------------------
def test_resolve_author_priority() -> None:
    id_backed = _comment("x", "v1", author_id="UCid_alice", author_name="Alice")
    name_only = _comment("y", "v1", author_name="Carol")
    anonymous = _comment("z", "v1")

    assert resolve_author(id_backed) == ("id", "UCid_alice", "Alice")
    assert resolve_author(name_only) == ("name", "Carol", "Carol")
    assert resolve_author(anonymous) == (None, None, None)


def test_anonymous_comments_excluded_from_sets(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2"])
    projection = result.videos
    assert projection is not None
    entity = next(e for e in projection.entities if e.entity_id == "v1")
    assert entity.comment_count == 6
    assert entity.commenter_count == 4
    assert entity.identity_coverage == pytest.approx(5 / 6)
    assert projection.summary.unidentified_comments == 1


# ----------------------------------------------------------------------
# Set math
# ----------------------------------------------------------------------
def test_pair_metrics_hand_computed(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2"])
    pair = next(
        p
        for p in result.videos.pairs
        if {p.entity_a, p.entity_b} == {"v1", "v2"}
    )
    assert pair.set_size_a == 4 and pair.set_size_b == 2
    assert pair.intersection_size == 2
    assert pair.union_size == 4
    assert pair.unique_a == 2 and pair.unique_b == 0
    assert pair.jaccard == pytest.approx(0.5)
    assert pair.overlap_coefficient == pytest.approx(1.0)
    assert pair.reach_overlap_pct == pytest.approx(0.5)
    assert pair.total_shared == 2
    assert len(pair.shared_commenters) == 2


def test_empty_set_pair_metric_is_none(excel_repos) -> None:
    # Seed a video with zero comments -> every pair involving it has a None
    # ratio (never 0), while a pair of populated sets with no shared author
    # reports 0.0.
    svc = _service(excel_repos)
    from SocialScienceResearch.domain.models import Video

    svc._repos.videos.upsert_video(
        Video(
            video_id="v_empty",
            url="https://www.youtube.com/watch?v=v_empty",
            channel_id="UC9",
            title="Empty",
            first_observed_run_id="run_overlap",
        )
    )
    result = svc.overlap(video_ids=["v1", "v_empty"])
    pair = result.videos.pairs[0]
    assert pair.intersection_size == 0
    assert pair.jaccard is None
    assert pair.overlap_coefficient is None

    result2 = svc.overlap(video_ids=["v1", "v2"])
    pair2 = next(
        p
        for p in result2.videos.pairs
        if {p.entity_a, p.entity_b} == {"v1", "v2"}
    )
    assert pair2.jaccard == pytest.approx(0.5)


def test_metric_param_switches_pair_ordering(excel_repos) -> None:
    svc = _service(excel_repos)
    jaccard = svc.overlap(video_ids=["v1", "v2", "v3"], metric="jaccard")
    assert jaccard.videos.pairs[0].entity_a == "v1"
    assert jaccard.videos.pairs[0].entity_b == "v2"  # 0.5 > 0.4 > ...

    intersection = svc.overlap(
        video_ids=["v1", "v2", "v3"], metric="intersection"
    )
    top = intersection.videos.pairs[0]
    assert top.intersection_size == 2  # (v1,v2) and (v1,v3) both share 2

    coeff = svc.overlap(video_ids=["v1", "v2"], metric="overlap_coefficient")
    pair = coeff.videos.pairs[0]
    assert pair.overlap_coefficient == pytest.approx(1.0)


# ----------------------------------------------------------------------
# Projections
# ----------------------------------------------------------------------
def test_video_vs_channel_projection_differ(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3", "v4"], channel_ids=["UC1", "UC2"])
    assert result.videos is not None and result.channels is not None
    assert result.videos.entity_type == "video"
    assert result.channels.entity_type == "channel"

    video_pair = next(
        p
        for p in result.videos.pairs
        if {p.entity_a, p.entity_b} == {"v1", "v3"}
    )
    assert video_pair.intersection_size == 2  # alice + carol

    channel_pair = next(
        p
        for p in result.channels.pairs
        if {p.entity_a, p.entity_b} == {"UC1", "UC2"}
    )
    assert channel_pair.intersection_size == 2
    assert channel_pair.jaccard == pytest.approx(0.4)

    # Only-requested scope returns only that projection.
    videos_only = svc.overlap(video_ids=["v1", "v2"])
    assert videos_only.videos is not None
    assert videos_only.channels is None
    channels_only = svc.overlap(channel_ids=["UC1", "UC2"])
    assert channels_only.videos is None
    assert channels_only.channels is not None


def test_heatmap_symmetric_and_no_diagonal(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3"])
    heatmap = result.videos.heatmap
    for a in ("v1", "v2", "v3"):
        for b in ("v1", "v2", "v3"):
            if a == b:
                assert b not in heatmap.get(a, {})
            else:
                assert heatmap[a][b] == heatmap[b][a]


# ----------------------------------------------------------------------
# Bridges + top shared
# ----------------------------------------------------------------------
def test_bridge_commenters_ranked_and_threshold(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3", "v4"], min_entities=2)
    bridges = result.videos.bridge_commenters
    keys = [b.author_key for b in bridges]
    assert keys == ["UCid_alice", "Carol", "UCid_bob", "UCid_eve"]

    alice = bridges[0]
    assert alice.entity_count == 3
    assert alice.video_count == 3
    assert alice.channel_count == 2
    assert alice.comment_count == 4
    assert {e["entity_id"] for e in alice.entities} == {"v1", "v2", "v3"}

    # dave (1 video) excluded; raising the threshold drops the 2-video bridges.
    result3 = svc.overlap(video_ids=["v1", "v2", "v3", "v4"], min_entities=3)
    assert [b.author_key for b in result3.videos.bridge_commenters] == ["UCid_alice"]


def test_top_shared_commenters_ranked_by_activity(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3", "v4"])
    top = result.videos.top_shared_commenters
    assert top[0].author_key == "UCid_alice"
    assert top[0].comment_count == 4
    assert top[0].entity_count == 3
    assert top[0].channel_count == 2


def test_overlap_edges_min_shared_filter(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3", "v4"], min_shared=2)
    edges = result.videos.overlap_edges
    by_pair = {
        (e["entity_a"], e["entity_b"]): e for e in edges
    }
    assert by_pair[("v1", "v2")]["shared_commenter_count"] == 2
    assert by_pair[("v1", "v3")]["shared_commenter_count"] == 2
    assert all(e["shared_commenter_count"] >= 2 for e in edges)
    assert ("v3", "v4") not in by_pair  # only 1 shared author


# ----------------------------------------------------------------------
# Summary + validation
# ----------------------------------------------------------------------
def test_summary_and_global(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.overlap(video_ids=["v1", "v2", "v3", "v4"], channel_ids=["UC1", "UC2"])
    summary = result.videos.summary
    assert summary.entity_count == 4
    assert summary.commenter_count == 5  # alice, bob, carol, dave, eve
    assert summary.comment_count == 12  # 6 + 2 + 3 + 1 (incl. 1 unidentified)
    assert summary.unidentified_comments == 1
    assert summary.pair_count == 6
    assert summary.max_shared_pair["intersection_size"] == 2
    assert summary.bridge_commenter_count == 4

    assert result.global_summary["unique_commenters"] == 5
    assert result.global_summary["comment_count"] == 12
    assert result.global_summary["bridge_commenter_count"] == 4


def test_validation_errors(excel_repos) -> None:
    svc = _service(excel_repos)
    with pytest.raises(ValueError):
        svc.overlap()
    with pytest.raises(ValueError):
        svc.overlap(video_ids=["v1"], metric="euclidean")
    with pytest.raises(ValueError):
        svc.overlap(video_ids=["v1"], top_n=0)


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------
def test_profile_totals_and_reply_context(excel_repos) -> None:
    svc = _service(excel_repos)
    profile = svc.profile("UCid_alice")
    assert profile.identity_kind == "id"
    assert profile.author_name == "Alice"
    assert profile.total_comments == 4
    assert profile.video_count == 3
    assert profile.channel_count == 2

    v1 = next(v for v in profile.videos if v.video_id == "v1")
    assert v1.comment_count == 2
    assert v1.root_count == 1
    assert v1.reply_count == 1
    assert v1.reply_to_count == 1
    assert v1.title == "Video One"
    assert v1.channel_name == "Channel UC1"

    uc2 = next(c for c in profile.channels if c.channel_id == "UC2")
    assert uc2.comment_count == 1
    assert uc2.video_count == 1

    # The reply carries parent-author context.
    reply = next(c for c in profile.comments if c.comment_id == "c2")
    assert reply.is_reply is True
    assert reply.parent_author_name == "Bob"

    # Most recent first.
    assert [c.comment_id for c in profile.comments] == ["c9", "c7", "c2", "c1"]


def test_profile_scope_and_limit(excel_repos) -> None:
    svc = _service(excel_repos)
    scoped = svc.profile("UCid_alice", video_ids=["v1"], limit=1)
    assert scoped.video_count == 1
    assert scoped.total_comments == 2  # c1 + c2 on v1
    assert len(scoped.comments) == 1

    name_only = svc.profile("Carol")
    assert name_only.identity_kind == "name"
    assert name_only.video_count == 2
    assert name_only.channel_count == 2


def test_profile_unknown_author_raises(excel_repos) -> None:
    svc = _service(excel_repos)
    with pytest.raises(KeyError):
        svc.profile("ghost")


# ----------------------------------------------------------------------
# Chunked scan + cache invalidation (pitfall A1/R1 for the overlap cache)
# ----------------------------------------------------------------------
def test_iter_comments_chunks_cover_corpus_and_match_full_scan(
    excel_repos, monkeypatch
) -> None:
    svc = _service(excel_repos)

    # The chunked iterator covers every comment exactly once.
    chunks = list(excel_repos.comments.iter_comments(chunk_size=5))
    assert len(chunks) == 3  # 12 seeded comments / chunk_size 5
    assert all(len(chunk) <= 5 for chunk in chunks)
    flattened = [c for chunk in chunks for c in chunk]
    assert sorted(c.comment_id for c in flattened) == sorted(
        c.comment_id for c in excel_repos.comments.list_comments()
    )

    # Aggregating over tiny chunks yields identical results to one full scan.
    scope = dict(video_ids=["v1", "v2", "v3", "v4"], channel_ids=["UC1", "UC2"])
    CommenterOverlapService.clear_overlap_cache()
    expected = svc.overlap(**scope)
    CommenterOverlapService.clear_overlap_cache()
    monkeypatch.setattr(CommenterOverlapService, "_CHUNK_SIZE", 4)
    chunked = CommenterOverlapService(excel_repos).overlap(**scope)
    assert chunked == expected


def test_comment_write_invalidates_overlap_cache(excel_repos) -> None:
    """A persisted comment must surface without waiting out the TTL.

    Mirrors ``test_recommendation_scrape_invalidates_graph_cache``: warm the
    cache, drive the production comment write path
    (``CollectionService._persist_comments``), and assert the next overlap read
    reflects the new commenter immediately.
    """
    from SocialScienceResearch.domain.models import CollectionRun
    from SocialScienceResearch.services.collection_service import CollectionService

    svc = _service(excel_repos)
    first = svc.overlap(video_ids=["v1", "v2"])
    assert first.global_summary["unique_commenters"] == 4
    pair = next(
        p for p in first.videos.pairs if p.entity_b == "v2"
    )
    assert pair.set_size_b == 2  # alice, bob

    service = CollectionService(None, excel_repos)
    run = CollectionRun(
        run_id="run_overlap_write",
        run_type=RunType.VIDEO,
        target_url="https://www.youtube.com/watch?v=v2",
        started_at=T0,
        status="pending",
    )
    effective = {
        "comment_min_likes": None,
        "comment_date_from": None,
        "comment_date_to": None,
        "max_comments_per_video": None,
        "comment_criteria": None,
    }
    stored = service._persist_comments(
        run,
        [{"id": "c13", "author": "Frank", "author_id": "UCid_frank"}],
        "v2",
        [],
        effective,
        None,
    )
    assert stored == 1

    second = svc.overlap(video_ids=["v1", "v2"])
    assert second.global_summary["unique_commenters"] == 5
    pair2 = next(
        p for p in second.videos.pairs if p.entity_b == "v2"
    )
    assert pair2.set_size_b == 3  # frank joined v2
