"""B1 integration: batch latest-observation resolution, comment filtering,
row resolution, and the research query endpoints.

The corpus here has two observations per entity so the *latest* metric is
unambiguous, plus a video with no observation to prove rows never fabricate
metric values.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import RecommendationStatus
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.query import (
    CommentFilter,
    Operator,
    QueryCondition,
    QueryContext,
    QueryGroup,
    ResearchQueryRequest,
    VideoFilter,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.query_service import QueryService
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"

CHANNEL_ID = "UCb1000000000000000000000"
T0 = utcnow()
# T1 is guaranteed later than T0: Windows `datetime.now` can step backward by
# microseconds, which made T0/T1 ordering nondeterministic under ties.
T1 = T0 + timedelta(microseconds=1)


@pytest.fixture
def repos(tmp_path):
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="b1")
    repos = build_excel_repositories(repo_settings)

    repos.channels.upsert_channel(
        Channel(
            channel_id=CHANNEL_ID,
            url=f"https://www.youtube.com/channel/{CHANNEL_ID}",
            title="B1 Channel",
            handle="@b1",
            first_observed_run_id="run_b1",
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_ch_old",
            collection_run_id="run_b1",
            channel_id=CHANNEL_ID,
            observed_at=T0,
            subscriber_count=90_000,
            video_count=2,
            view_count=9_000_000,
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_ch_new",
            collection_run_id="run_b1",
            channel_id=CHANNEL_ID,
            observed_at=T1,
            subscriber_count=100_000,
            video_count=5,
            view_count=10_000_000,
        )
    )

    for i in range(5):
        vid = f"v0{i}"
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id=CHANNEL_ID,
                title=f"B1 video {i}",
                description=f"research sample {i}",
                duration=100 + i,
                upload_timestamp=T0,
                tags=["research", f"tag{i}"] if i % 2 == 0 else ["research"],
                is_short=i % 2 == 0,
                first_observed_run_id="run_b1",
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_v_{vid}_old",
                collection_run_id="run_b1",
                video_id=vid,
                observed_at=T0,
                view_count=10 + i,
                like_count=1 + i,
                comment_count=2 + i,
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_v_{vid}_new",
                collection_run_id="run_b1",
                video_id=vid,
                observed_at=T1,
                view_count=100 + i * 100,  # 100, 200, 300, 400, 500
                like_count=100 + i * 10,
                comment_count=10 + i,
            )
        )
    # A video without any observation: view-range filters must exclude it.
    repos.videos.upsert_video(
        Video(
            video_id="v_noobs",
            url="https://www.youtube.com/watch?v=v_noobs",
            channel_id=CHANNEL_ID,
            title="No observations",
            duration=99,
            first_observed_run_id="run_b1",
        )
    )

    comments = [
        dict(
            comment_id="c0",
            video_id="v00",
            author_id="author_a",
            author_name="A",
            comment_text="love this research",
            is_reply=True,
            parent_comment_id="c1",
            root_comment_id="c0",
            is_author=False,
            obs=dict(like_count=50, reply_count=1, is_removed=False),
        ),
        dict(
            comment_id="c1",
            video_id="v00",
            author_id="author_b",
            author_name="B",
            comment_text="questions and answers",
            is_reply=False,
            parent_comment_id=None,
            root_comment_id="c1",
            is_author=True,
            obs=dict(like_count=5, reply_count=2, is_removed=False),
        ),
        dict(
            comment_id="c2",
            video_id="v01",
            author_id="author_a",
            author_name="A",
            comment_text="sample data please",
            is_reply=False,
            parent_comment_id=None,
            root_comment_id="c2",
            is_author=False,
            obs=dict(like_count=99, reply_count=0, is_removed=True),
        ),
    ]
    for c in comments:
        repos.comments.upsert_comment(
            Comment(
                comment_id=c["comment_id"],
                video_id=c["video_id"],
                author_id=c["author_id"],
                author_name=c["author_name"],
                comment_text=c["comment_text"],
                is_reply=c["is_reply"],
                parent_comment_id=c["parent_comment_id"],
                root_comment_id=c["root_comment_id"],
                is_author=c["is_author"],
                first_observed_run_id="run_b1",
            )
        )
        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"obs_c_{c['comment_id']}",
                collection_run_id="run_b1",
                comment_id=c["comment_id"],
                observed_at=T1,
                like_count=c["obs"]["like_count"],
                reply_count=c["obs"]["reply_count"],
                is_removed=c["obs"]["is_removed"],
            )
        )

    for i in range(1, 4):
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=f"rec_{i}",
                collection_run_id="run_b1",
                source_video_id="v00",
                recommended_video_id=f"v0{i}",
                position=i - 1,
                status=RecommendationStatus.OBSERVED,
            )
        )

    repos.store.close()

    settings = SocialScienceSettings(
        repository=repo_settings,
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )
    return repos, settings


@pytest.fixture
def query_service(repos):
    return QueryService(repos[0])


@pytest.fixture
def client(repos):
    settings = repos[1]
    yield TestClient(create_app(settings))


# ----------------------------------------------------------------------
# Batch latest-observation resolution
# ----------------------------------------------------------------------
def test_batch_latest_video_observations_match_single_lookup(repos) -> None:
    repo = repos[0].videos
    ids = ["v00", "v03", "v02", "v_noobs"]
    batch = repo.get_latest_video_observations(ids)
    assert list(batch.keys()) == ["v00", "v03", "v02"]  # input order; missing id omitted
    assert set(batch) == {"v00", "v02", "v03"}
    for vid in ("v00", "v02", "v03"):
        assert batch[vid].view_count == repo.get_latest_video_observation(vid).view_count
        assert batch[vid].observed_at == T1  # newest observed_at wins
    assert batch["v02"].view_count == 300


def test_batch_latest_video_observations_equivalence_per_id(repos) -> None:
    repo = repos[0].videos
    ids = [f"v0{i}" for i in range(5)]
    batch = repo.get_latest_video_observations(ids)
    for vid in ids:
        assert batch[vid] == repo.get_latest_video_observation(vid)


def test_batch_latest_channels_and_comments(repos) -> None:
    channels = repos[0].channels
    batch = channels.get_latest_channel_observations([CHANNEL_ID])
    assert batch[CHANNEL_ID].subscriber_count == 100_000
    assert batch[CHANNEL_ID] == channels.get_latest_channel_observation(CHANNEL_ID)

    comments = repos[0].comments
    cids = ["c0", "c1", "c2"]
    comment_batch = comments.get_latest_comment_observations(cids)
    assert list(comment_batch.keys()) == cids
    for cid in cids:
        assert comment_batch[cid] == comments.get_latest_comment_observation(cid)


def test_list_comments_without_video_id_returns_all(repos) -> None:
    comments = repos[0].comments
    assert {c.comment_id for c in comments.list_comments()} == {"c0", "c1", "c2"}
    assert {c.comment_id for c in comments.list_comments("v00")} == {"c0", "c1"}


# ----------------------------------------------------------------------
# QueryService wiring
# ----------------------------------------------------------------------
def test_filter_videos_uses_latest_observation_batch(repos, query_service) -> None:
    video_repo = repos[0].videos
    latest = video_repo.get_latest_video_observations([f"v0{i}" for i in range(5)])
    matched = query_service.filter_videos(CHANNEL_ID, VideoFilter(views_min=300))
    ids = {v.video_id for v in matched}
    assert ids == {"v02", "v03", "v04"}
    assert "v_noobs" not in ids  # no observation -> excluded from view filter
    # Same answer as if resolved one observation at a time.
    single = {
        vid
        for vid in ("v00", "v01", "v02", "v03", "v04")
        if latest.get(vid) is not None and latest[vid].view_count >= 300
    }
    assert single == ids


def test_filter_comments_semantics(query_service) -> None:
    rows = query_service.resolve_latest_rows("comment")
    assert len(rows) == 3
    roots = query_service.filter_comments(CommentFilter(only_roots=True), rows)
    assert {r["comment_id"] for r in roots} == {"c1", "c2"}
    authored = query_service.filter_comments(CommentFilter(is_author=True), rows)
    assert [r["comment_id"] for r in authored] == ["c1"]
    liked = query_service.filter_comments(CommentFilter(min_likes=10), rows)
    assert {r["comment_id"] for r in liked} == {"c0", "c2"}
    keyword = query_service.filter_comments(CommentFilter(keywords=["sample"]), rows)
    assert [r["comment_id"] for r in keyword] == ["c2"]
    by_author = query_service.filter_comments(CommentFilter(author_id="author_a"), rows)
    assert {r["comment_id"] for r in by_author} == {"c0", "c2"}


def test_resolve_latest_rows_video_keys_and_sort(query_service) -> None:
    rows = query_service.resolve_latest_rows("video", sort="view_count")
    vids = [r["video_id"] for r in rows]
    assert len(rows) == 6
    assert vids[-1] == "v_noobs"  # None view sorted last
    assert vids[:-1] == ["v00", "v01", "v02", "v03", "v04"]
    observed = [r for r in rows if r["view_count"] is not None]
    assert [r["view_count"] for r in observed] == [100, 200, 300, 400, 500]


def test_resolve_latest_rows_comment_scoped_and_recommendation(query_service) -> None:
    scoped = query_service.resolve_latest_rows(
        "comment", context=QueryContext(video_id="v01")
    )
    assert [r["comment_id"] for r in scoped] == ["c2"]
    assert scoped[0]["like_count"] == 99

    edges = query_service.resolve_latest_rows("recommendation")
    assert len(edges) == 3
    assert all(r["status"] == "observed" for r in edges)
    assert {r["source_video_id"] for r in edges} == {"v00"}

    channels = query_service.resolve_latest_rows("channel")
    assert len(channels) == 1
    assert channels[0]["subscriber_count"] == 100_000
    assert channels[0]["video_count"] == 5


def test_recommendation_query_rows_ranked_by_feed_position(
    repos, query_service
) -> None:
    # Insert an out-of-order edge (position None) to prove ranking, not
    # insertion order.
    repos[0].recommendations.save_recommendation(
        RecommendationObservation(
            observation_id="rec_unranked",
            collection_run_id="run_b1",
            source_video_id="v00",
            recommended_video_id="v99",
            position=None,
            status=RecommendationStatus.OBSERVED,
        )
    )
    rows = query_service.resolve_latest_rows("recommendation")
    positions = [r["position"] for r in rows]
    assert positions == [0, 1, 2, None]


def test_resolve_latest_rows_unknown_entity_raises(query_service) -> None:
    with pytest.raises(ValueError):
        query_service.resolve_latest_rows("planet")


# ----------------------------------------------------------------------
# Research endpoints
# ----------------------------------------------------------------------
def test_research_variables_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/research/variables")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 58
    assert any(v["entity"] == "video" and v["name"] == "view_count" for v in body)
    assert any(v["name"] == "transcript_length_chars" for v in body)

    video_only = client.get(f"{PREFIX}/research/variables", params={"entity": "video"})
    assert video_only.status_code == 200
    assert all(v["entity"] == "video" for v in video_only.json())
    assert len(video_only.json()) == 21


def test_research_operators_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/research/operators")
    assert resp.status_code == 200
    names = {op["name"] for op in resp.json()}
    assert names == {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "contains",
        "not_contains",
        "in",
        "not_in",
        "between",
        "is_null",
        "not_null",
        "top_pct",
        "bottom_pct",
        "percentile_rank",
        "quartile",
        "quantile",
        "median_split",
    }
    assert all(op["description"] for op in resp.json())


def _query(body: ResearchQueryRequest) -> dict:
    return body.model_dump()


def test_research_query_preview_endpoint(client) -> None:
    body = _query(
        ResearchQueryRequest(
            entity="video",
            root=QueryGroup(
                operator="AND",
                conditions=[QueryCondition(variable="view_count", operator=Operator.GT, value=300)],
            ),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/preview", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["population_size"] == 6
    assert payload["n"] == 2
    assert payload["total"] == 2
    assert payload["stages"][0]["cumulative"] == 2
    assert payload["stages"][0]["condition"] == "view_count gt 300"


def test_research_query_resolve_endpoint_with_context(client) -> None:
    body = _query(
        ResearchQueryRequest(
            entity="comment",
            root=QueryGroup(
                operator="AND",
                conditions=[QueryCondition(variable="like_count", operator=Operator.GTE, value=10)],
            ),
            query_context=QueryContext(video_id="v00"),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/resolve", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {"total": 1, "population_size": 2}


def test_research_query_resolve_rank_operator(client) -> None:
    body = _query(
        ResearchQueryRequest(
            entity="video",
            root=QueryGroup(
                operator="AND",
                conditions=[QueryCondition(variable="view_count", operator=Operator.TOP_PCT, value=60)],
            ),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/resolve", json=body)
    assert resp.status_code == 200
    # view %60 of [100,200,300,400,500] -> v03 (400) and v04 (500). v_noobs has no value.
    assert resp.json() == {"total": 2, "population_size": 6}


def test_research_query_preview_nested_funnel(client) -> None:
    body = _query(
        ResearchQueryRequest(
            entity="video",
            root=QueryGroup(
                operator="AND",
                conditions=[
                    QueryCondition(variable="view_count", operator=Operator.GT, value=100),
                    QueryGroup(
                        operator="OR",
                        conditions=[
                            QueryCondition(variable="view_count", operator=Operator.LT, value=100),
                            QueryCondition(variable="view_count", operator=Operator.GT, value=400),
                        ],
                    ),
                ],
            ),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/preview", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1  # v04 only (500 > 400 && > 100)
    assert [s["cumulative"] for s in payload["stages"]] == [4, 1]
    assert [s["matched"] for s in payload["stages"]] == [2, 3]


def test_research_query_unknown_variable_returns_envelope(client) -> None:
    body = _query(
        ResearchQueryRequest(
            entity="video",
            root=QueryGroup(operator="AND", conditions=[QueryCondition(variable="nope", operator=Operator.GT, value=1)]),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/resolve", json=body)
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["code"] == "invalid_argument"
    assert "nope" in payload["message"]


def test_research_query_author_entity(client) -> None:
    # Corpus: author_a wrote c0 + c2, author_b wrote c1 -> two authors.
    body = _query(
        ResearchQueryRequest(
            entity="author",
            root=QueryGroup(
                operator="AND",
                conditions=[QueryCondition(variable="comment_count", operator=Operator.GTE, value=2)],
            ),
        )
    )
    resp = client.post(f"{PREFIX}/research/query/resolve", json=body)
    assert resp.status_code == 200
    assert resp.json() == {"total": 1, "population_size": 2}

    preview = client.post(
        f"{PREFIX}/research/query/preview",
        json=_query(
            ResearchQueryRequest(
                entity="author",
                root=QueryGroup(
                    operator="AND",
                    conditions=[QueryCondition(variable="comment_count", operator=Operator.GTE, value=2)],
                ),
            )
        ),
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["total"] == 1
    assert payload["population_size"] == 2