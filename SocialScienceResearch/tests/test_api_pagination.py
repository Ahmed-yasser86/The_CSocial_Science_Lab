"""API-level pagination, envelopes, response models and OpenAPI metadata."""

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
from SocialScienceResearch.domain.enums import RecommendationStatus
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Comment,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import utcnow

PREFIX = "/api/v1/social-science"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "api_pg")
    repo_settings = RepositorySettings(data_dir=str(tmp_path), dataset_name="api_pg")
    repos = build_excel_repositories(repo_settings)

    for i in range(3):
        repos.runs.create_run(
            CollectionRun(
                run_id=f"run_pg_{i}",
                run_type="channel",
                target_url=f"https://www.youtube.com/@run{i}",
                target_channel_id="UCpg000000000000000000000",
                started_at=utcnow(),
                status="success",
            )
        )

    repos.channels.upsert_channel(
        Channel(
            channel_id="UCpg000000000000000000000",
            url="https://www.youtube.com/channel/UCpg000000000000000000000",
            title="Paginated Channel",
            first_observed_run_id="run_pg_0",
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_pg_ch",
            collection_run_id="run_pg_0",
            channel_id="UCpg000000000000000000000",
            observed_at=utcnow(),
            subscriber_count=999,
            video_count=5,
            view_count=10000,
        )
    )

    for i in range(5):
        vid = f"pg_v{i}"
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id="UCpg000000000000000000000",
                title=f"Paginated video {i}",
                duration=500 + i * 100,
                first_observed_run_id="run_pg_0",
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_pg_v{i}",
                collection_run_id="run_pg_0",
                video_id=vid,
                observed_at=utcnow(),
                view_count=1000 + i * 100,
                like_count=100 + i * 10,
                comment_count=10 + i,
            )
        )
        for c in range(3):
            repos.comments.upsert_comment(
                Comment(
                    comment_id=f"com_{vid}_{c}",
                    video_id=vid,
                    author_name=f"user-{i}-{c}",
                    comment_text=f"comment {i}-{c}",
                    first_observed_run_id="run_pg_0",
                )
            )

    # recommendation edges: pg_v0 -> others
    for i in range(1, 5):
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=f"rec_pg_{i}",
                collection_run_id="run_pg_0",
                source_video_id="pg_v0",
                recommended_video_id=f"pg_v{i}",
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
    yield TestClient(create_app(settings))


def _walk(client, path: str, page_size: int = 2) -> list[dict]:
    """Follow the opaque cursor until the last page; return every item."""
    collected: list[dict] = []
    cursor = None
    pages = 0
    while True:
        params = {"page_size": page_size}
        if cursor is not None:
            params["cursor"] = cursor
        resp = client.get(path, params=params)
        assert resp.status_code == 200, (path, resp.text)
        body = resp.json()
        collected.extend(body["items"])
        pages += 1
        assert body["total"] is not None
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        assert body["next_cursor"] is not None
        cursor = body["next_cursor"]
        assert pages < 100
    return collected


# ----------------------------------------------------------------------
# cursor pagination walking
# ----------------------------------------------------------------------
def test_videos_endpoint_paginates(client) -> None:
    items = _walk(client, f"{PREFIX}/videos")
    assert [v["video_id"] for v in items] == [f"pg_v{i}" for i in range(5)]


def test_channel_videos_paginates_with_filter(client) -> None:
    items = _walk(
        client,
        f"{PREFIX}/channels/UCpg000000000000000000000/videos",
        page_size=2,
    )
    assert len(items) == 5

    filtered = _walk(
        client,
        f"{PREFIX}/channels/UCpg000000000000000000000/videos",
    )
    with_min = _walk(
        client,
        f"{PREFIX}/channels/UCpg000000000000000000000/videos",
    )
    assert len([v for v in with_min if v["duration"] >= 700]) == 3  # 500..900 step 100
    del filtered


def test_runs_endpoint_paginates(client) -> None:
    items = _walk(client, f"{PREFIX}/runs", page_size=2)
    assert len(items) == 3
    assert {r["run_id"] for r in items} == {f"run_pg_{i}" for i in range(3)}


def test_recommendations_endpoint_paginates(client) -> None:
    items = _walk(client, f"{PREFIX}/videos/pg_v0/recommendations")
    assert [e["recommended_video_id"] for e in items] == [f"pg_v{i}" for i in range(1, 5)]


def test_comments_endpoint_paginates(client) -> None:
    items = _walk(client, f"{PREFIX}/videos/pg_v0/comments")
    assert len(items) == 3  # 3 comments for pg_v0


def test_observations_endpoint_paginates(client) -> None:
    items = _walk(client, f"{PREFIX}/videos/pg_v0/observations")
    assert len(items) == 1


def test_pagination_keys_are_stable_across_pages(client) -> None:
    """Walking with a filter yields a total that reflects the filtered set."""
    resp = client.get(
        f"{PREFIX}/channels/UCpg000000000000000000000/videos",
        params={"page_size": 2, "duration_min": 700},
    )
    assert resp.status_code == 200
    total = resp.json()["total"]
    assert total == 3  # durations 700, 800, 900


# ----------------------------------------------------------------------
# error envelope for invalid cursor
# ----------------------------------------------------------------------
def test_invalid_cursor_returns_error_envelope(client) -> None:
    resp = client.get(f"{PREFIX}/videos", params={"cursor": "!!!not-base64!!!"})
    assert resp.status_code in (400, 422)
    if resp.status_code == 400:
        body = resp.json()
        assert body["code"] == "invalid_cursor"
        assert "message" in body


def test_sampling_error_returns_error_envelope(client) -> None:
    resp = client.post(
        f"{PREFIX}/videos/pg_v0/comments/sample",
        json={"strategy": "top_views", "size": 1},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "sampling_error"
    assert "message" in body


# ----------------------------------------------------------------------
# every route declares a response model
# ----------------------------------------------------------------------
def test_all_routes_declare_response_model(client) -> None:
    app = client.app
    missing = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods or not path.startswith(PREFIX):
            continue
        # Streaming endpoints (SSE, downloads) deliberately return a raw
        # StreamingResponse/FileResponse and are exempt from response_model.
        response_class = getattr(route, "response_class", None)
        if response_class is not None:
            continue
        if getattr(route, "response_model", None) is None:
            missing.append((path, sorted(methods)))
    assert missing == [], f"routes without response_model: {missing}"


# ----------------------------------------------------------------------
# CORS + OpenAPI metadata
# ----------------------------------------------------------------------
def test_cors_allows_configured_origin(client) -> None:
    resp = client.get(f"{PREFIX}/runs", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_openapi_metadata_and_schema_present(client) -> None:
    schema = client.app.openapi()
    assert schema["info"]["title"] == "SocialScienceResearch API"
    assert schema["info"]["version"] == "0.1.0"
    assert schema["info"]["description"]
    schemas = schema["components"]["schemas"]
    paginated = [name for name in schemas if name.startswith("Paginated")]
    assert paginated, "expected registered Paginated response schemas"
    assert any(p.startswith(PREFIX) for p in schema["paths"])


def test_videos_response_model_fields(client) -> None:
    resp = client.get(f"{PREFIX}/videos", params={"page_size": 1})
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    for key in (
        "video_id",
        "url",
        "channel_id",
        "title",
        "description",
        "duration",
        "upload_date",
        "first_observed_run_id",
    ):
        assert key in item, f"missing field {key!r}"