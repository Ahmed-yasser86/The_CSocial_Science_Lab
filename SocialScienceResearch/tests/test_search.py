"""E2 tests: global entity search service + ``/search`` endpoint + ``q`` params.

Covers the unified result projection, relevance ranking (title fields weight
higher than body fields), cursor pagination across entities, per-entity
restriction and the like-search ``q`` param added to ``GET /channels`` and
``GET /videos``.
"""

from __future__ import annotations

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
    CollectionRun,
    Comment,
    RecommendationObservation,
    Video,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.search_service import SearchService

PREFIX = "/api/v1/social-science"


def _seed(tmp_path):
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="e2")
    repos = build_excel_repositories(repo_settings)
    repos.runs.create_run(
        CollectionRun(
            run_id="run_e2",
            run_type="channel",
            target_url="https://www.youtube.com/@alpha",
            target_channel_id="UCe2",
            started_at="2026-08-01T00:00:00+00:00",
            status="success",
        )
    )
    repos.channels.upsert_channel(
        Channel(
            channel_id="UCe2",
            url="https://www.youtube.com/channel/UCe2",
            title="Alpha Methods Channel",
            handle="@alphascience",
            description="quantitative methods and causal inference",
            first_observed_run_id="run_e2",
        )
    )
    repos.videos.upsert_video(
        Video(
            video_id="v_alpha",
            url="https://www.youtube.com/watch?v=v_alpha",
            channel_id="UCe2",
            title="Regression Analysis",
            description="stats primer for causal inference research",
            first_observed_run_id="run_e2",
        )
    )
    repos.comments.upsert_comment(
        Comment(
            comment_id="c_alpha",
            video_id="v_alpha",
            author_name="Researcher Alpha",
            author_id="author_alpha",
            comment_text="love the causal inference examples",
            first_observed_run_id="run_e2",
        )
    )
    repos.comments.upsert_comment(
        Comment(
            comment_id="c_beta",
            video_id="v_alpha",
            author_name="Dr Beta",
            author_id="author_beta",
            comment_text="unrelated cooking note",
            first_observed_run_id="run_e2",
        )
    )
    repos.recommendations.save_recommendation(
        RecommendationObservation(
            observation_id="rec_e2",
            collection_run_id="run_e2",
            source_video_id="v_alpha",
            recommended_video_id="v_alpha",
            position=0,
            channel_id="UCe2",
            title="Regression Analysis",
            observed_at="2026-08-01T00:00:00+00:00",
        )
    )
    repos.store.save()
    return repo_settings, repos


@pytest.fixture
def search_service(tmp_path):
    _, repos = _seed(tmp_path)
    return SearchService(repos)


@pytest.fixture
def client(tmp_path):
    repo_settings, _ = _seed(tmp_path)
    settings = SocialScienceSettings(
        repository=repo_settings,
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )
    yield TestClient(create_app(settings, provider=None))


# ----------------------------------------------------------------------
# Service-level
# ----------------------------------------------------------------------
def test_search_empty_query_returns_empty(search_service) -> None:
    page = search_service.search("   ")
    assert page.items == []
    assert page.total == 0


def test_search_across_entities_unified_projection(search_service) -> None:
    page = search_service.search("alpha")
    entities = {hit.entity for hit in page.items}
    # "alpha" appears in channel handle/title, video title (via rec), comment
    # author/body and author name -> cross-entity hit.
    assert entities >= {"channel", "comment", "author", "recommendation"}
    hit = next(h for h in page.items if h.entity == "channel")
    assert hit.entity_id == "UCe2"
    assert hit.title == "Alpha Methods Channel"
    assert hit.subtitle == "@alphascience"
    assert hit.score > 0


def test_search_ranks_title_matches_first(search_service) -> None:
    page = search_service.search("alpha")
    hits = page.items
    # Title/handle-level fields (weight >= 2) must outrank body/subtitle-only
    # matches: channel + author carry "alpha" in high-weight fields; comment
    # (author_name, w=1) and recommendation (recommended_video_id, w=1) do not.
    high = [h for h in hits if h.score >= 2]
    low = [h for h in hits if h.score < 2]
    assert {h.entity for h in high} == {"channel", "author"}
    assert all(h.entity in {"comment", "recommendation"} for h in low)


def test_search_entity_restriction(search_service) -> None:
    page = search_service.search("regression", entity="video")
    assert all(hit.entity == "video" for hit in page.items)
    assert [hit.entity_id for hit in page.items] == ["v_alpha"]


def test_search_unknown_entity_raises(search_service) -> None:
    with pytest.raises(ValueError):
        search_service.search("alpha", entity="planet")


def test_search_cursor_pagination(search_service) -> None:
    page1 = search_service.search("a", page_size=2)
    assert page1.has_more is True
    assert page1.next_cursor is not None
    ids1 = [(hit.entity, hit.entity_id) for hit in page1.items]

    page2 = search_service.search("a", cursor=page1.next_cursor, page_size=2)
    ids2 = [(hit.entity, hit.entity_id) for hit in page2.items]
    assert ids1 != ids2 and not set(ids1) & set(ids2)
    assert page2.total == page1.total


def test_search_no_match_empty(search_service) -> None:
    page = search_service.search("zzzznothing")
    assert page.items == []
    assert page.total == 0


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
def test_search_endpoint(client) -> None:
    resp = client.get(f"{PREFIX}/search", params={"q": "alpha"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert {item["entity"] for item in body["items"]} >= {"channel", "comment"}
    first = body["items"][0]
    assert {"entity", "entity_id", "title", "score"} <= set(first)


def test_search_endpoint_entity_and_cursor(client) -> None:
    page1 = client.get(f"{PREFIX}/search", params={"q": "a", "entity": "comment", "page_size": 1})
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 1 and body1["has_more"] is True

    page2 = client.get(
        f"{PREFIX}/search",
        params={"q": "a", "entity": "comment", "page_size": 1, "cursor": body1["next_cursor"]},
    )
    body2 = page2.json()
    assert body2["items"]
    assert body2["items"][0]["entity_id"] != body1["items"][0]["entity_id"]


def test_search_endpoint_unknown_entity_400(client) -> None:
    resp = client.get(f"{PREFIX}/search", params={"q": "alpha", "entity": "planet"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_argument"


def test_channels_endpoint_q_param(client) -> None:
    resp = client.get(f"{PREFIX}/channels", params={"q": "methods"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["channel_id"] == "UCe2"

    none = client.get(f"{PREFIX}/channels", params={"q": "nope"})
    assert none.json()["total"] == 0


def test_videos_endpoint_q_param(client) -> None:
    resp = client.get(f"{PREFIX}/videos", params={"q": "regression"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    none = client.get(f"{PREFIX}/videos", params={"q": "nope"})
    assert none.json()["total"] == 0
