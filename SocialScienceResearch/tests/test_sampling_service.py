"""Tests for the reproducible research sampling service."""

from __future__ import annotations

import pytest

from SocialScienceResearch.domain.enums import SamplingStrategy
from SocialScienceResearch.domain.models import Video, VideoObservation
from SocialScienceResearch.domain.query import AdvancedSamplingSpec, SamplingSpec
from SocialScienceResearch.services import (
    SamplingService,
    UnsupportedSamplingError,
)
from SocialScienceResearch.utils.idgen import utcnow


def _add_video(repos, video_id, *, views, likes=0, comments=0, duration=100, upload_date=None):
    video = Video(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_id="UCx",
        title=f"Video {video_id}",
        duration=duration,
        upload_date=upload_date,
        first_observed_run_id="run_1",
    )
    repos.videos.upsert_video(video)
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id=f"obs_{video_id}",
            collection_run_id="run_1",
            video_id=video_id,
            observed_at=utcnow(),
            view_count=views,
            like_count=likes,
            comment_count=comments,
        )
    )
    return video


@pytest.fixture
def corpus(excel_repos):
    _add_video(excel_repos, "v1", views=1000, likes=100, comments=10, duration=120, upload_date=None)
    _add_video(excel_repos, "v2", views=5000, likes=500, comments=50, duration=300, upload_date=None)
    _add_video(excel_repos, "v3", views=200, likes=20, comments=2, duration=60, upload_date=None)
    # v4 has an entity row but NO observation -> views are MISSING.
    excel_repos.videos.upsert_video(
        Video(
            video_id="v4",
            url="https://www.youtube.com/watch?v=v4",
            channel_id="UCx",
            title="Video v4",
            first_observed_run_id="run_1",
        )
    )
    return excel_repos


def _spec(strategy, **kwargs) -> SamplingSpec:
    return SamplingSpec(strategy=strategy, **kwargs)


# ----------------------------------------------------------------------
def test_top_views_orders_descending(corpus) -> None:
    svc = SamplingService(corpus)
    result = svc.sample_videos("UCx", _spec(SamplingStrategy.TOP_VIEWS, size=2))
    assert result.entity_ids == ["v2", "v1"]
    assert result.sample_size == 2
    assert result.population_size == 4


def test_bottom_views_orders_ascending(corpus) -> None:
    svc = SamplingService(corpus)
    result = svc.sample_videos("UCx", _spec(SamplingStrategy.BOTTOM_VIEWS, size=2))
    assert result.entity_ids == ["v3", "v1"]


def test_top_likes(corpus) -> None:
    svc = SamplingService(corpus)
    result = svc.sample_videos("UCx", _spec(SamplingStrategy.TOP_LIKES, size=1))
    assert result.entity_ids == ["v2"]


def test_missing_metric_ranked_last_and_reported(corpus) -> None:
    svc = SamplingService(corpus)
    result = svc.sample_videos("UCx", _spec(SamplingStrategy.TOP_VIEWS))
    # v4 (no observation) is ranked last, never assigned a fabricated value.
    assert result.entity_ids[-1] == "v4"
    assert result.missing_metric_count == 1


def test_random_is_reproducible_with_seed(corpus) -> None:
    svc = SamplingService(corpus)
    first = svc.sample_videos("UCx", _spec(SamplingStrategy.RANDOM, seed=7))
    second = svc.sample_videos("UCx", _spec(SamplingStrategy.RANDOM, seed=7))
    assert first.entity_ids == second.entity_ids
    assert set(first.entity_ids) == {"v1", "v2", "v3", "v4"}


def test_percent_sampling(corpus) -> None:
    svc = SamplingService(corpus)
    result = svc.sample_videos("UCx", _spec(SamplingStrategy.TOP_VIEWS, percent=50))
    # 50% of 4 population -> top 2 by views.
    assert result.entity_ids == ["v2", "v1"]


def test_stratified_by_upload_year(corpus) -> None:
    svc = SamplingService(corpus)
    from datetime import date

    _add_video(corpus, "y2023", views=10, upload_date=date(2023, 5, 1))
    _add_video(corpus, "y2023b", views=20, upload_date=date(2023, 6, 1))
    _add_video(corpus, "y2025", views=30, upload_date=date(2025, 1, 1))
    result = svc.sample_videos(
        "UCx", _spec(SamplingStrategy.STRATIFIED, strata="year", sample_per_stratum=1)
    )
    selected = set(result.entity_ids)
    # One representative per year present, balanced.
    assert "y2023" in selected or "y2023b" in selected
    assert "y2025" in selected


def test_date_range_filters_by_upload_date(corpus) -> None:
    from datetime import date

    _add_video(corpus, "jan", views=1, upload_date=date(2024, 1, 15))
    _add_video(corpus, "mar", views=1, upload_date=date(2024, 3, 20))
    result = SamplingService(corpus).sample_videos(
        "UCx",
        _spec(
            SamplingStrategy.DATE_RANGE,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 2, 1),
        ),
    )
    assert result.entity_ids == ["jan"]


def test_criteria_json_records_spec(corpus) -> None:
    result = SamplingService(corpus).sample_videos(
        "UCx", _spec(SamplingStrategy.TOP_VIEWS, size=1, seed=99)
    )
    assert result.criteria_json["strategy"] == "top_views"
    assert result.criteria_json["size"] == 1
    assert result.criteria_json["seed"] == 99
    assert result.criteria_json["population_size"] == 4
    assert result.seed == 99


# ----------------------------------------------------------------------
# Comment sampling
# ----------------------------------------------------------------------
def _add_comment(repos, comment_id, *, video_id="vid", likes=0, published_at=None):
    from SocialScienceResearch.domain.models import Comment, CommentObservation

    repos.comments.upsert_comment(
        Comment(
            comment_id=comment_id,
            video_id=video_id,
            author_name=f"Author {comment_id}",
            comment_text="text",
            published_at=published_at,
            first_observed_run_id="run_1",
        )
    )
    repos.comments.save_comment_observation(
        CommentObservation(
            observation_id=f"obs_c_{comment_id}",
            collection_run_id="run_1",
            comment_id=comment_id,
            observed_at=utcnow(),
            like_count=likes,
        )
    )


@pytest.fixture
def comment_corpus(excel_repos):
    _add_comment(excel_repos, "c1", likes=5)
    _add_comment(excel_repos, "c2", likes=50)
    _add_comment(excel_repos, "c3", likes=1)
    return excel_repos


def test_comment_top_likes(comment_corpus) -> None:
    result = SamplingService(comment_corpus).sample_comments(
        "vid", _spec(SamplingStrategy.TOP_LIKES, size=1)
    )
    assert result.entity_ids == ["c2"]


def test_comment_random_reproducible(comment_corpus) -> None:
    svc = SamplingService(comment_corpus)
    a = svc.sample_comments("vid", _spec(SamplingStrategy.RANDOM, seed=3))
    b = svc.sample_comments("vid", _spec(SamplingStrategy.RANDOM, seed=3))
    assert a.entity_ids == b.entity_ids


def test_video_strategy_rejected_for_comments(comment_corpus) -> None:
    with pytest.raises(UnsupportedSamplingError):
        SamplingService(comment_corpus).sample_comments(
            "vid", _spec(SamplingStrategy.TOP_VIEWS)
        )


# ----------------------------------------------------------------------
# Advanced sampling: author names, categories, video_ids, overlap
# ----------------------------------------------------------------------
def _add_video_in_channel(repos, video_id, channel_id, *, categories=None):
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            title=f"Video {video_id}",
            categories=categories or [],
            first_observed_run_id="run_1",
        )
    )


def _add_comment_advanced(
    repos, comment_id, *, video_id, author_id=None, author_name=None
):
    from SocialScienceResearch.domain.models import Comment

    repos.comments.upsert_comment(
        Comment(
            comment_id=comment_id,
            video_id=video_id,
            author_id=author_id,
            author_name=author_name,
            comment_text="text",
            first_observed_run_id="run_1",
        )
    )


@pytest.fixture
def overlap_corpus(excel_repos):
    """Two channels, three videos; Alice spans 2 videos in 1 channel and
    Carol spans 2 channels, so video vs channel overlap are distinguishable."""
    _add_video_in_channel(excel_repos, "va1", "CH-A", categories=["news"])
    _add_video_in_channel(excel_repos, "va2", "CH-A", categories=["news"])
    _add_video_in_channel(excel_repos, "vb1", "CH-B", categories=["comedy"])

    _add_comment_advanced(excel_repos, "c1", video_id="va1", author_id="a1", author_name="Alice")
    _add_comment_advanced(excel_repos, "c2", video_id="va2", author_id="a1", author_name="Alice")
    _add_comment_advanced(excel_repos, "c3", video_id="va2", author_id="a1", author_name="Alice")
    _add_comment_advanced(excel_repos, "c4", video_id="vb1", author_id="b1", author_name="Bob")
    _add_comment_advanced(excel_repos, "c5", video_id="va1", author_id="d1", author_name="Dave")
    _add_comment_advanced(excel_repos, "c6", video_id="va1", author_id="c1", author_name="Carol")
    _add_comment_advanced(excel_repos, "c7", video_id="vb1", author_id="c1", author_name="Carol")
    return excel_repos


def _advanced_comment_spec(**kwargs):
    return AdvancedSamplingSpec(
        strategy=SamplingStrategy.RANDOM,
        entity_type="comment",
        seed=7,
        channel_ids=["CH-A", "CH-B"],
        **kwargs,
    )


def test_advanced_spec_accepts_new_filter_fields() -> None:
    spec = AdvancedSamplingSpec(
        strategy=SamplingStrategy.RANDOM,
        entity_type="comment",
        author_names=["alice", "carol"],
        exclude_author_names=["bot"],
        categories=["news"],
        video_ids=["va1", "va2"],
        overlap="video",
        overlap_min=3,
    )
    assert spec.author_names == ["alice", "carol"]
    assert spec.exclude_author_names == ["bot"]
    assert spec.categories == ["news"]
    assert spec.overlap == "video"
    assert spec.overlap_min == 3


def test_advanced_author_names_filters_case_insensitive(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(author_names=["ALI"])
    )
    assert set(result.entity_ids) == {"c1", "c2", "c3"}
    assert result.population_size == 3


def test_advanced_exclude_author_names_drops_matches(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(exclude_author_names=["bob"])
    )
    assert "c4" not in result.entity_ids
    assert result.population_size == 6


def test_advanced_categories_restrict_video_population(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(categories=["news"])
    )
    # Only va1/va2 (news) enter the population; vb1 (comedy) comments dropped.
    assert set(result.entity_ids) == {"c1", "c2", "c3", "c5", "c6"}
    assert result.population_size == 5


def test_advanced_video_ids_restrict_comments(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(video_ids=["va1"])
    )
    assert set(result.entity_ids) == {"c1", "c5", "c6"}
    assert result.population_size == 3


def test_advanced_overlap_video_keeps_authors_across_videos(overlap_corpus) -> None:
    # Alice appears on va1 + va2 (2 distinct videos); Carol on va1 + vb1.
    # Bob and Dave appear on a single video each -> dropped.
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(overlap="video", overlap_min=2)
    )
    assert set(result.entity_ids) == {"c1", "c2", "c3", "c6", "c7"}
    assert result.population_size == 5


def test_advanced_overlap_channel_keeps_authors_across_channels(overlap_corpus) -> None:
    # Only Carol comments in both CH-A and CH-B (2 distinct channels).
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(overlap="channel", overlap_min=2)
    )
    assert set(result.entity_ids) == {"c6", "c7"}
    assert result.population_size == 2


def test_advanced_overlap_min_raises_threshold(overlap_corpus) -> None:
    # overlap_min=3: no author spans 3 distinct videos here.
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(overlap="video", overlap_min=3)
    )
    assert result.entity_ids == []
    assert result.population_size == 0


def test_advanced_overlap_off_is_noop(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(overlap="off", overlap_min=2)
    )
    assert set(result.entity_ids) == {"c1", "c2", "c3", "c4", "c5", "c6", "c7"}
    assert result.population_size == 7


def test_advanced_overlap_video_ids_restrict_units(overlap_corpus) -> None:
    # Alice spans va1 + va2 (both allowed); Carol's vb1 comment is outside the
    # allowed videos so she only has 1 allowed unit -> dropped.
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(
            overlap="video",
            overlap_min=2,
            overlap_video_ids=["va1", "va2"],
        )
    )
    assert set(result.entity_ids) == {"c1", "c2", "c3"}
    assert result.population_size == 3


def test_advanced_overlap_channel_ids_restrict_units(overlap_corpus) -> None:
    # Carol spans CH-A + CH-B. Restricting to CH-A only leaves her with a single
    # channel, so nobody qualifies at overlap_min=2.
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(
            overlap="channel",
            overlap_min=2,
            overlap_channel_ids=["CH-A"],
        )
    )
    assert result.entity_ids == []
    assert result.population_size == 0


def test_advanced_overlap_specific_units_fall_back_to_corpus(overlap_corpus) -> None:
    # Empty specific-entity lists preserve the existing corpus-wide behavior.
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(
            overlap="video",
            overlap_min=2,
            overlap_video_ids=[],
            overlap_channel_ids=[],
        )
    )
    assert set(result.entity_ids) == {"c1", "c2", "c3", "c6", "c7"}
    assert result.population_size == 5


def test_advanced_criteria_records_new_filters(overlap_corpus) -> None:
    result = SamplingService(overlap_corpus).sample_advanced(
        _advanced_comment_spec(
            author_names=["alice"],
            categories=["news"],
            video_ids=["va1", "va2"],
            overlap="channel",
            overlap_min=2,
            overlap_video_ids=["va1"],
            overlap_channel_ids=["CH-A", "CH-B"],
        )
    )
    assert result.criteria_json["author_names"] == ["alice"]
    assert result.criteria_json["categories"] == ["news"]
    assert result.criteria_json["video_ids"] == ["va1", "va2"]
    assert result.criteria_json["overlap"] == "channel"
    assert result.criteria_json["overlap_min"] == 2
    assert result.criteria_json["overlap_video_ids"] == ["va1"]
    assert result.criteria_json["overlap_channel_ids"] == ["CH-A", "CH-B"]


# ----------------------------------------------------------------------
# Advanced sampling: run_ids scoping + top_replies strategy
# ----------------------------------------------------------------------
def _add_video_with_run(repos, video_id, channel_id, run_id, *, title=None):
    repos.videos.upsert_video(
        Video(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            title=title or f"Video {video_id}",
            first_observed_run_id=run_id,
        )
    )


def test_advanced_run_ids_restrict_videos(excel_repos) -> None:
    _add_video_with_run(excel_repos, "vr1", "CH-A", "run_x")
    _add_video_with_run(excel_repos, "vr2", "CH-A", "run_y")
    result = SamplingService(excel_repos).sample_advanced(
        AdvancedSamplingSpec(
            strategy=SamplingStrategy.RANDOM,
            entity_type="video",
            seed=1,
            channel_ids=["CH-A"],
            run_ids=["run_x"],
        )
    )
    assert set(result.entity_ids) == {"vr1"}
    assert result.population_size == 1
    assert result.criteria_json["run_ids"] == ["run_x"]


def test_advanced_run_ids_restrict_comments(excel_repos) -> None:
    _add_video_with_run(excel_repos, "va1", "CH-A", "run_x")
    _add_video_with_run(excel_repos, "va2", "CH-A", "run_y")
    _add_comment_advanced(excel_repos, "cx1", video_id="va1", author_id="a")
    _add_comment_advanced(excel_repos, "cy1", video_id="va2", author_id="a")
    result = SamplingService(excel_repos).sample_advanced(
        AdvancedSamplingSpec(
            strategy=SamplingStrategy.RANDOM,
            entity_type="comment",
            seed=1,
            channel_ids=["CH-A"],
            run_ids=["run_x"],
        )
    )
    assert set(result.entity_ids) == {"cx1"}
    assert result.population_size == 1


def test_advanced_top_replies_ranks_by_reply_count(excel_repos) -> None:
    from SocialScienceResearch.domain.models import CommentObservation

    _add_video_in_channel(excel_repos, "vt", "CH-A")
    for cid, replies in (("cr1", 5), ("cr2", 40), ("cr3", 12)):
        _add_comment_advanced(excel_repos, cid, video_id="vt", author_id="a")
        excel_repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"obs_{cid}",
                collection_run_id="run_1",
                comment_id=cid,
                observed_at=utcnow(),
                like_count=0,
                reply_count=replies,
            )
        )
    result = SamplingService(excel_repos).sample_advanced(
        AdvancedSamplingSpec(
            strategy=SamplingStrategy.TOP_REPLIES,
            entity_type="comment",
            channel_ids=["CH-A"],
            size=2,
        )
    )
    assert result.entity_ids == ["cr2", "cr3"]
    assert result.population_size == 3


def test_advanced_top_replies_percent_takes_top_x_percent(excel_repos) -> None:
    from SocialScienceResearch.domain.models import CommentObservation

    _add_video_in_channel(excel_repos, "vt", "CH-A")
    for cid, replies in (("p1", 1), ("p2", 10), ("p3", 100), ("p4", 1000)):
        _add_comment_advanced(excel_repos, cid, video_id="vt", author_id="a")
        excel_repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"obs_{cid}",
                collection_run_id="run_1",
                comment_id=cid,
                observed_at=utcnow(),
                like_count=0,
                reply_count=replies,
            )
        )
    result = SamplingService(excel_repos).sample_advanced(
        AdvancedSamplingSpec(
            strategy=SamplingStrategy.TOP_REPLIES,
            entity_type="comment",
            channel_ids=["CH-A"],
            percent=50,
        )
    )
    # Top 50% of 4 -> the two most-replied comments.
    assert result.entity_ids == ["p4", "p3"]
    assert result.sample_size == 2
