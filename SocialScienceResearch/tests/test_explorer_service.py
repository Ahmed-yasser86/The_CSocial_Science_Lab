"""B8 tests: ExplorerService + ProvenanceService + their API endpoints.

Covers the explorer contract (columns + paginated envelope, text search,
eq/contains filters, unknown-variable rejection, descending sort with None
last, raw-record retrieval) and the provenance chain (first-observed run,
provider/config info, observation history, per-entity provenance links).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.explorer_service import ExplorerService
from SocialScienceResearch.services.provenance_service import (
    EntityNotFoundError,
    ProvenanceService,
)

PREFIX = "/api/v1/social-science"

CHANNEL_ID = "UCb8000000000000000000000"

T0 = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 6, 12, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def repos(tmp_path):
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="b8")
    repos = build_excel_repositories(repo_settings)

    repos.runs.create_run(
        CollectionRun(
            run_id="run_b8_first",
            run_type="channel",
            target_url=f"https://www.youtube.com/channel/{CHANNEL_ID}",
            target_channel_id=CHANNEL_ID,
            started_at=T0,
            finished_at=T1,
            status="success",
            provider="yt-dlp",
            provider_version="2026.01.01",
            config_json={"workflow": "channel", "strategy": "flat"},
        )
    )
    repos.runs.create_run(
        CollectionRun(
            run_id="run_b8_second",
            run_type="video",
            target_url="https://www.youtube.com/watch?v=v_a",
            target_video_id="v_a",
            started_at=T1,
            status="success",
            provider="yt-dlp",
            config_json={"workflow": "video"},
        )
    )

    repos.channels.upsert_channel(
        Channel(
            channel_id=CHANNEL_ID,
            url=f"https://www.youtube.com/channel/{CHANNEL_ID}",
            title="B8 Alpha Channel",
            description="quantitative methods and surveys",
            handle="@b8alpha",
            first_observed_run_id="run_b8_first",
            raw_json={"kind": "channel", "id": CHANNEL_ID},
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_ch_b8",
            collection_run_id="run_b8_first",
            channel_id=CHANNEL_ID,
            observed_at=T1,
            subscriber_count=25000,
            video_count=4,
            view_count=1_200_000,
        )
    )

    videos = [
        dict(
            video_id="v_a",
            title="Regression Analysis",
            description="stats primer for research",
            duration=700,
            view_count=100,
            raw_json={"id": "v_a", "source": "yt-dlp"},
        ),
        dict(
            video_id="v_b",
            title="Network Science Lecture",
            description="graph theory",
            duration=400,
            view_count=500,
            raw_json={},
        ),
        dict(
            video_id="v_c",
            title="Missing Metrics Clip",
            description="no observation seeded",
            duration=200,
            view_count=None,  # video exists but has no observation
            raw_json={},
        ),
        dict(
            video_id="v_d",
            title="Causal Inference",
            description="research methods primer",
            duration=800,
            view_count=300,
            raw_json={},
        ),
    ]
    for spec in videos:
        repos.videos.upsert_video(
            Video(
                video_id=spec["video_id"],
                url=f"https://www.youtube.com/watch?v={spec['video_id']}",
                channel_id=CHANNEL_ID,
                title=spec["title"],
                description=spec["description"],
                duration=spec["duration"],
                first_observed_run_id="run_b8_first",
                raw_json=spec["raw_json"],
            )
        )
        if spec["view_count"] is not None:
            repos.videos.save_video_observation(
                VideoObservation(
                    observation_id=f"obs_v_{spec['video_id']}",
                    collection_run_id="run_b8_first",
                    video_id=spec["video_id"],
                    observed_at=T1,
                    view_count=spec["view_count"],
                    like_count=10,
                    comment_count=2,
                )
            )

    comments = [
        dict(
            comment_id="c1",
            comment_text="love this example study",
            is_reply=True,
            parent_comment_id="c2",
            root_comment_id="c2",
        ),
        dict(
            comment_id="c2",
            comment_text="open data please",
            is_reply=False,
            parent_comment_id=None,
            root_comment_id="c2",
        ),
    ]
    for spec in comments:
        repos.comments.upsert_comment(
            Comment(
                comment_id=spec["comment_id"],
                video_id="v_a",
                author_name="Researcher A",
                comment_text=spec["comment_text"],
                is_reply=spec["is_reply"],
                parent_comment_id=spec["parent_comment_id"],
                root_comment_id=spec["root_comment_id"],
                first_observed_run_id="run_b8_first",
            )
        )
        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"obs_c_{spec['comment_id']}",
                collection_run_id="run_b8_second",
                comment_id=spec["comment_id"],
                observed_at=T1,
                like_count=7,
                reply_count=0,
            )
        )

    # Observation ids are deliberately scrambled relative to the feed rail so
    # the default explorer order must come from the feed rank, not the primary
    # key (rec_b8_2 has position 2, rec_b8_3 position 1).
    rec_edges = [
        dict(observation_id="rec_b8_1", recommended_video_id="v_b", position=0, title="Network Science Lecture"),
        dict(observation_id="rec_b8_2", recommended_video_id="v_c", position=2, title="Missing Metrics Clip"),
        dict(observation_id="rec_b8_3", recommended_video_id="v_d", position=1, title="Causal Inference"),
        dict(observation_id="rec_b8_4", recommended_video_id="v_a", position=None, title="Regression Analysis"),
    ]
    for spec in rec_edges:
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=spec["observation_id"],
                collection_run_id="run_b8_first",
                source_video_id="v_a",
                recommended_video_id=spec["recommended_video_id"],
                position=spec["position"],
                channel_id=CHANNEL_ID,
                title=spec["title"],
                observed_at=T1,
                raw_json={"kind": "recommendation", "position": spec["position"]},
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
def explorer(repos):
    return ExplorerService(repos[0])


@pytest.fixture
def provenance(repos):
    return ProvenanceService(repos[0])


@pytest.fixture
def client(repos):
    yield TestClient(create_app(repos[1]))


# ----------------------------------------------------------------------
# Service-level: explore
# ----------------------------------------------------------------------
def test_explore_returns_columns_and_envelope(explorer) -> None:
    result = explorer.explore("video")
    assert result.entity == "video"
    names = [column.name for column in result.columns]
    assert "view_count" in names and "title" in names and "channel_id" in names
    assert {item["video_id"] for item in result.items} == {"v_a", "v_b", "v_c", "v_d"}
    assert result.total == 4
    assert result.has_more is False
    assert result.next_cursor is None
    assert {option.variable for option in result.sort_options} == {
        name for name in names if name not in ("tags", "categories")
    }


def test_explore_unknown_entity_raises(explorer) -> None:
    with pytest.raises(ValueError):
        explorer.explore("planet")


def test_explore_text_search_narrows(explorer) -> None:
    videos = explorer.explore("video", q="regression")
    assert [item["video_id"] for item in videos.items] == ["v_a"]

    comments = explorer.explore("comment", q="example")
    assert [item["comment_id"] for item in comments.items] == ["c1"]

    channels = explorer.explore("channel", q="quantitative")
    assert [item["channel_id"] for item in channels.items] == [CHANNEL_ID]


def test_explore_filter_eq_and_contains(explorer) -> None:
    eq = explorer.explore(
        "video", filters=[{"variable": "title", "operator": "eq", "value": "Regression Analysis"}]
    )
    assert [item["video_id"] for item in eq.items] == ["v_a"]

    contains = explorer.explore(
        "video", filters=[{"variable": "description", "operator": "contains", "value": "primer"}]
    )
    # v_a ("stats primer for research") and v_d ("research methods primer") both match.
    assert {item["video_id"] for item in contains.items} == {"v_a", "v_d"}

    # gt over a numeric (coerced) metric uses the latest observation.
    gt = explorer.explore(
        "video", filters=[{"variable": "view_count", "operator": "gt", "value": "250"}]
    )
    assert {item["video_id"] for item in gt.items} == {"v_b", "v_d"}


def test_explore_filter_unknown_variable_and_operator_raise(explorer) -> None:
    with pytest.raises(ValueError, match="Unknown variable"):
        explorer.explore("video", filters=[{"variable": "nope", "operator": "eq", "value": 1}])
    with pytest.raises(ValueError, match="Unsupported operator"):
        explorer.explore("video", filters=[{"variable": "title", "operator": "median_split", "value": 1}])


def test_explore_sort_desc_none_last(explorer) -> None:
    result = explorer.explore("video", sort="-view_count")
    assert [item["video_id"] for item in result.items] == ["v_b", "v_d", "v_a", "v_c"]
    assert result.items[-1]["view_count"] is None  # None value sorted last


def test_explore_sort_asc_and_unknown_sort_raise(explorer) -> None:
    asc = explorer.explore("video", sort="view_count")
    assert [item["video_id"] for item in asc.items] == ["v_a", "v_d", "v_b", "v_c"]
    with pytest.raises(ValueError, match="Unknown variable"):
        explorer.explore("video", sort="-nope")


def test_explore_cursor_pagination_is_stable(explorer) -> None:
    page1 = explorer.explore("video", page_size=2)
    assert [item["video_id"] for item in page1.items] == ["v_a", "v_b"]
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = explorer.explore("video", cursor=page1.next_cursor, page_size=2)
    assert [item["video_id"] for item in page2.items] == ["v_c", "v_d"]
    assert page2.has_more is False
    assert page2.next_cursor is None
    assert page2.total == 4


def test_explore_recommendation_rows_carry_observation_id(explorer) -> None:
    result = explorer.explore("recommendation")
    # Default order is the feed rank (position 0, 1, 2, then unknown last),
    # not the observation-id primary key order.
    assert [item["observation_id"] for item in result.items] == [
        "rec_b8_1",
        "rec_b8_3",
        "rec_b8_2",
        "rec_b8_4",
    ]
    assert result.items[0]["source_video_id"] == "v_a"
    assert result.items[0]["recommended_video_id"] == "v_b"


def test_explore_recommendation_default_order_is_feed_ranked(explorer) -> None:
    result = explorer.explore("recommendation")
    assert [(item["position"], item["recommended_video_id"]) for item in result.items] == [
        (0, "v_b"),
        (1, "v_d"),
        (2, "v_c"),
        (None, "v_a"),
    ]
    assert result.total == 4


def test_explore_author_rows_aggregate_comments(explorer) -> None:
    result = explorer.explore("author")
    assert result.entity == "author"
    names = [column.name for column in result.columns]
    assert {"author_id", "comment_count", "video_ids"} <= set(names)
    authors = {item["author_id"]: item for item in result.items}
    # Both comments share the name "Researcher A" with no author_id, so the
    # name-fallback key groups them into a single author.
    assert list(authors) == ["Researcher A"]
    assert authors["Researcher A"]["comment_count"] == 2
    assert authors["Researcher A"]["video_ids"] == ["v_a"]

    search = explorer.explore("author", q="researcher")
    assert [item["author_id"] for item in search.items] == ["Researcher A"]


def test_explore_author_unknown_variable_raises(explorer) -> None:
    with pytest.raises(ValueError, match="Unknown variable"):
        explorer.explore(
            "author", filters=[{"variable": "nope", "operator": "eq", "value": 1}]
        )


# ----------------------------------------------------------------------
# Service-level: raw + provenance
# ----------------------------------------------------------------------
def test_get_row_raw_returns_raw_json(explorer) -> None:
    raw = explorer.get_row_raw("video", "v_a")
    assert raw == {"entity": "video", "entity_id": "v_a", "raw_json": {"id": "v_a", "source": "yt-dlp"}}
    assert explorer.get_row_raw("video", "missing") is None
    with pytest.raises(ValueError):
        explorer.get_row_raw("planet", "x")


def test_provenance_returns_run_and_config_info(provenance) -> None:
    record = provenance.provenance("video", "v_a")
    assert record.entity == "video"
    assert record.entity_id == "v_a"
    assert record.first_observed_run_id == "run_b8_first"
    assert record.first_seen_at == T0
    assert record.provider == "yt-dlp"
    assert record.config_json == {"workflow": "channel", "strategy": "flat"}
    assert record.channel_id == CHANNEL_ID
    assert record.observation_count == 1
    assert record.observations[0].run_id == "run_b8_first"
    run = next(r for r in record.runs if r.run_id == "run_b8_first")
    assert run.status == "success"
    assert run.provider_version == "2026.01.01"
    assert run.started_at == T0


def test_provenance_comment_links_and_missing_entity(provenance) -> None:
    record = provenance.provenance("comment", "c1")
    assert record.parent_comment_id == "c2"
    assert record.root_comment_id == "c2"

    with pytest.raises(EntityNotFoundError):
        provenance.provenance("video", "does_not_exist")
    with pytest.raises(ValueError):
        provenance.provenance("planet", "x")


def test_provenance_author_reports_first_seen_run(provenance) -> None:
    record = provenance.provenance("author", "Researcher A")
    assert record.entity == "author"
    assert record.entity_id == "Researcher A"
    assert record.first_observed_run_id == "run_b8_first"
    assert record.first_seen_at == T0
    assert record.observation_count == 1
    assert record.observations[0].run_id == "run_b8_first"

    with pytest.raises(EntityNotFoundError):
        provenance.provenance("author", "Nobody")


# ----------------------------------------------------------------------
# Endpoints (TestClient)
# ----------------------------------------------------------------------
def test_explore_endpoint_envelope(client) -> None:
    resp = client.get(f"{PREFIX}/explore/records", params={"entity": "video"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity"] == "video"
    assert body["total"] == 4
    assert {column["name"] for column in body["columns"]} >= {"title", "view_count"}
    assert [item["video_id"] for item in body["items"]] == ["v_a", "v_b", "v_c", "v_d"]
    assert body["sort_options"]


def test_explore_endpoint_search_and_filter(client) -> None:
    search = client.get(f"{PREFIX}/explore/records", params={"entity": "comment", "q": "example"})
    assert [item["comment_id"] for item in search.json()["items"]] == ["c1"]

    filters = json.dumps([{"variable": "title", "operator": "contains", "value": "network"}])
    filtered = client.get(
        f"{PREFIX}/explore/records", params={"entity": "video", "filters": filters}
    )
    assert [item["video_id"] for item in filtered.json()["items"]] == ["v_b"]


def test_explore_endpoint_unknown_variable_returns_400_envelope(client) -> None:
    filters = json.dumps([{"variable": "nope", "operator": "eq", "value": 1}])
    resp = client.get(
        f"{PREFIX}/explore/records", params={"entity": "video", "filters": filters}
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["code"] == "invalid_argument"
    assert "nope" in payload["message"]


def test_explore_endpoint_malformed_filters_returns_400(client) -> None:
    resp = client.get(
        f"{PREFIX}/explore/records", params={"entity": "video", "filters": "not-json"}
    )
    assert resp.status_code == 400


def test_explore_endpoint_sort_desc(client) -> None:
    resp = client.get(f"{PREFIX}/explore/records", params={"entity": "video", "sort": "-view_count"})
    assert resp.status_code == 200
    assert [item["video_id"] for item in resp.json()["items"]] == ["v_b", "v_d", "v_a", "v_c"]


def test_explore_author_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/explore/records", params={"entity": "author"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity"] == "author"
    assert body["total"] == 1
    assert body["items"][0]["author_id"] == "Researcher A"
    assert body["items"][0]["comment_count"] == 2


def test_raw_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/explore/records/video/v_a/raw")
    assert resp.status_code == 200
    assert resp.json() == {
        "entity": "video",
        "entity_id": "v_a",
        "raw_json": {"id": "v_a", "source": "yt-dlp"},
    }
    missing = client.get(f"{PREFIX}/explore/records/video/missing/raw")
    assert missing.status_code == 404


def test_provenance_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/explore/provenance/video/v_a")
    assert resp.status_code == 200
    body = resp.json()
    assert body["first_observed_run_id"] == "run_b8_first"
    assert body["provider"] == "yt-dlp"
    assert body["config_json"]["workflow"] == "channel"
    assert body["channel_id"] == CHANNEL_ID
    assert any(run["run_id"] == "run_b8_first" for run in body["runs"])

    missing = client.get(f"{PREFIX}/explore/provenance/video/does_not_exist")
    assert missing.status_code == 404
    unknown = client.get(f"{PREFIX}/explore/provenance/planet/x")
    assert unknown.status_code == 400