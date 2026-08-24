"""Tests for ``NetworkMatrixService`` (US-60/61 structural matrices).

Reuses the 4-video / 2-channel corpus (see ``test_commenter_overlap_service``)
plus seeded recommendation edges with ``layer_index`` so both matrices can be
asserted deterministically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from SocialScienceResearch.domain.models import (
    Channel,
    Comment,
    RecommendationObservation,
    Video,
)
from SocialScienceResearch.services.network_matrix_service import (
    NetworkMatrixService,
)

T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _comment(comment_id, video_id, *, author_id=None, author_name=None):
    return Comment(
        comment_id=comment_id,
        video_id=video_id,
        author_id=author_id,
        author_name=author_name,
        published_at=T0,
        first_observed_run_id="run_matrix",
    )


def _seed(repos) -> None:
    for video_id, channel_id in (("v1", "UC1"), ("v2", "UC1"), ("v3", "UC2"), ("v4", "UC2")):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id=channel_id,
                title=f"Video {video_id}",
                first_observed_run_id="run_matrix",
            )
        )
        repos.channels.upsert_channel(
            Channel(
                channel_id=channel_id,
                url=f"https://www.youtube.com/channel/{channel_id}",
                title=f"Channel {channel_id}",
                first_observed_run_id="run_matrix",
            )
        )
    comments = [
        _comment("c1", "v1", author_id="UCid_alice", author_name="Alice"),
        _comment("c2", "v1", author_name="Carol"),
        _comment("c3", "v2", author_id="UCid_bob", author_name="Bob"),
        _comment("c4", "v3", author_id="UCid_alice", author_name="Alice"),
        _comment("c5", "v3", author_name="Carol"),
        _comment("c6", "v4", author_id="UCid_eve", author_name="Eve"),
    ]
    for c in comments:
        repos.comments.upsert_comment(c)

    edges = [
        # layer 0: 3 edges, 2 unique sources, 3 unique targets
        RecommendationObservation(
            observation_id="e1", collection_run_id="run_matrix",
            source_video_id="v1", recommended_video_id="v3", layer_index=0,
            observed_at=T0,
        ),
        RecommendationObservation(
            observation_id="e2", collection_run_id="run_matrix",
            source_video_id="v1", recommended_video_id="v4", layer_index=0,
            observed_at=T0,
        ),
        RecommendationObservation(
            observation_id="e3", collection_run_id="run_matrix",
            source_video_id="v2", recommended_video_id="v3", layer_index=0,
            observed_at=T0,
        ),
        # layer 1: 1 edge, 1 unique source, 1 unique target (v2 -> v4)
        RecommendationObservation(
            observation_id="e4", collection_run_id="run_matrix",
            source_video_id="v2", recommended_video_id="v4", layer_index=1,
            observed_at=T0,
        ),
    ]
    for e in edges:
        repos.recommendations.save_recommendation(e)


def _service(excel_repos) -> NetworkMatrixService:
    _seed(excel_repos)
    return NetworkMatrixService(excel_repos)


def test_community_matrix_shared_commenters(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.community_matrix(channel_ids=["UC1", "UC2"])
    assert set(result["labels"]) == {"UC1", "UC2"}
    # alice + carol are active on both channels.
    assert result["matrix"]["UC1"]["UC2"] == 2
    assert result["matrix"]["UC2"]["UC1"] == 2
    # diagonal is implicit (absent -> 0).
    assert result["matrix"]["UC1"].get("UC1", 0) == 0
    # identifying metadata is returned so the UI can show names, not just ids.
    assert set(result["label_meta"]) == {"UC1", "UC2"}


def test_community_matrix_empty_scope(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.community_matrix(channel_ids=[])
    assert result["labels"] == []
    assert result["matrix"] == {}


def test_layer_matrix_counts(excel_repos) -> None:
    svc = _service(excel_repos)
    result = svc.layer_matrix()
    by_layer = {row["layer_index"]: row for row in result["rows"]}
    assert by_layer[0]["edge_count"] == 3
    assert by_layer[0]["unique_sources"] == 2  # v1, v2
    assert by_layer[0]["unique_targets"] == 2  # v3, v4
    assert by_layer[1]["edge_count"] == 1
    assert by_layer[1]["unique_sources"] == 1
