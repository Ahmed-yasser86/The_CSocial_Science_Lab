"""Regression tests for the B2 defect fixes.

Covers:
  * JobStatus lives in the services layer, not the domain enums module.
  * TranscriptRecord has a single optional ``observed_at`` (openpyxl 3.1+
    empty-cell datetime_1904 deprecation workaround).
  * RecommendationObservation carries an optional ``observed_at``.
  * CollectionResult.ok is derived from the merged status set.
  * The /videos/top endpoint preserves videos whose latest observation is
    missing / stale (it no longer silently drops them).
  * Stratified sampling honors ``spec.seed`` and is reproducible.
  * collect(..., max_videos_to_enrich=...) skips are observable on the result.
  * Recommendation targets from an unsupported provider produce structured
    ``recommendation_unsupported`` errors instead of a crash.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pytest

from SocialScienceResearch.acquisition import (
    AcquisitionProvider,
    ChannelExtract,
    RecommendationUnsupportedError,
)
from SocialScienceResearch.config.settings import (
    CollectionSettings,
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import (
    Channel,
    CollectionRun,
    RecommendationObservation,
    TranscriptRecord,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.query import (
    SamplingSpec,
    SamplingStrategy,
    VideoFilter,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services import SamplingService
from SocialScienceResearch.services.jobs import JobStatus
from SocialScienceResearch.services.results import CollectionResult

PREFIX = "/api/v1/social-science"


# ----------------------------------------------------------------------
# JobStatus placement
# ----------------------------------------------------------------------
def test_job_status_lives_in_services_not_domain() -> None:
    import importlib

    assert not hasattr(importlib.import_module("SocialScienceResearch.domain.enums"), "JobStatus")
    assert JobStatus.SUCCEEDED.value == "succeeded"
    assert JobStatus.FAILED.value == "failed"


# ----------------------------------------------------------------------
# TranscriptRecord observed_at
# ----------------------------------------------------------------------
def test_transcript_observed_at_single_optional_field() -> None:
    fields = TranscriptRecord.model_fields
    assert list(fields).count("observed_at") == 1
    rec = TranscriptRecord(
        transcript_id="tx_1",
        video_id="v1",
        collection_run_id="run_1",
        path="transcripts/v1.txt",
        lang="en",
        status="available",
        observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert rec.observed_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
    no_date = TranscriptRecord(
        transcript_id="tx_2",
        video_id="v2",
        collection_run_id="run_2",
        path="transcripts/v2.txt",
        lang="en",
        status="available",
    )
    assert no_date.observed_at is None


# ----------------------------------------------------------------------
# RecommendationObservation.observed_at
# ----------------------------------------------------------------------
def test_recommendation_observation_has_observed_at() -> None:
    rec = RecommendationObservation(
        observation_id="obs_1",
        collection_run_id="run_1",
        source_video_id="src",
        recommended_video_id="dst",
        status="observed",
    )
    assert rec.observed_at is None
    rec2 = RecommendationObservation(
        observation_id="obs_2",
        collection_run_id="run_1",
        source_video_id="src",
        recommended_video_id="dst2",
        status="observed",
        observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert rec2.observed_at is not None


# ----------------------------------------------------------------------
# CollectionResult.ok from merged status
# ----------------------------------------------------------------------
def _result(status: CollectionStatus) -> CollectionResult:
    return CollectionResult(
        run_id="run_x",
        run_type=RunType.CHANNEL,
        status=status,
        target_url="https://www.youtube.com/@x",
        target_id="UCx",
        entities_discovered=1,
        entities_created=1,
        entities_existing=0,
        entities_failed=0,
        comments_collected=0,
    )


@pytest.mark.parametrize(
    "status,ok",
    [
        (CollectionStatus.SUCCESS, True),
        (CollectionStatus.PARTIAL, True),
        (CollectionStatus.FAILED, False),
    ],
)
def test_collection_result_ok_merged(status: CollectionStatus, ok: bool) -> None:
    assert _result(status).ok is ok


# ----------------------------------------------------------------------
# /videos/top preserves videos whose latest observation is missing
# ----------------------------------------------------------------------
@pytest.fixture
def top_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "top_missing")
    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="top_missing")
    repos = build_excel_repositories(rs)
    repos.runs.create_run(
        CollectionRun(
            run_id="run_top",
            run_type=RunType.VIDEO,
            status="success",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
            target_url="https://www.youtube.com/watch?v=v_ok",
            target_id="Vok",
        )
    )
    repos.channels.upsert_channel(
        Channel(
            channel_id="UCtop00000000000000000000",
            title="Top channel",
            url="u",
            first_observed_run_id="run_top",
        )
    )
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for vid, dur in (("v_ok", 600), ("v_missing", 700)):
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id="UCtop00000000000000000000",
                title=f"Video {vid}",
                duration=dur,
                first_observed_run_id="run_top",
            )
        )
    # only v_ok has an observation; v_missing never received stats so its
    # "latest observation" is missing and must still appear in /videos/top.
    repos.videos.save_video_observation(
        VideoObservation(
            observation_id="obs_v_ok",
            collection_run_id="run_top",
            video_id="v_ok",
            observed_at=now,
            view_count=1200,
        )
    )

    from SocialScienceResearch.api import create_app
    from fastapi.testclient import TestClient

    repos.store.close()
    settings = SocialScienceSettings(repository=rs)
    return TestClient(create_app(settings))


def test_top_preserves_missing_videos(top_client) -> None:
    r = top_client.get(f"{PREFIX}/channels/UCtop00000000000000000000/videos/top")
    assert r.status_code == 200, r.text
    body = r.json()
    by_id = {row["video_id"]: row for row in body["top"]}
    assert set(by_id) == {"v_ok", "v_missing"}
    assert by_id["v_missing"]["availability"] == "missing"
    assert by_id["v_ok"]["availability"] == "available"


# ----------------------------------------------------------------------
# Stratified sampling honors spec.seed
# ----------------------------------------------------------------------
def _seed_videos(repos, channel_id, run_id, strata=4, per_stratum=5) -> None:
    for s in range(strata):
        for j in range(per_stratum):
            repos.videos.upsert_video(
                Video(
                    video_id=f"v_{s}_{j}",
                    url=f"https://www.youtube.com/watch?v=v_{s}_{j}",
                    channel_id=channel_id,
                    title=f"V {s}-{j}",
                    upload_date=date(2020 + s, 1, 1),
                    first_observed_run_id=run_id,
                )
            )


@pytest.fixture
def sampling_repos(tmp_path):
    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="strat")
    repos = build_excel_repositories(rs)
    _seed_videos(repos, "UCstrat0000000000000000000", "run_strat")
    return repos


def _strat_spec(seed: int) -> SamplingSpec:
    return SamplingSpec(
        strategy=SamplingStrategy.STRATIFIED,
        strata="year",
        sample_per_stratum=2,
        seed=seed,
    )


def test_stratified_same_seed_is_identical(sampling_repos) -> None:
    svc = SamplingService(sampling_repos, default_seed=42)
    first = svc.sample_videos("UCstrat0000000000000000000", _strat_spec(123))
    second = svc.sample_videos("UCstrat0000000000000000000", _strat_spec(123))
    assert first.entity_ids == second.entity_ids
    assert len(first.entity_ids) == 8  # 4 strata * 2 per stratum


def test_stratified_different_seed_differs(sampling_repos) -> None:
    svc = SamplingService(sampling_repos, default_seed=42)
    base = svc.sample_videos("UCstrat0000000000000000000", _strat_spec(123)).entity_ids
    for other in (124, 125, 126):
        if svc.sample_videos("UCstrat0000000000000000000", _strat_spec(other)).entity_ids != base:
            break
    else:
        pytest.fail("all alternative seeds produced identical stratified samples")


def test_uniform_spec_seed_reproducible(sampling_repos) -> None:
    svc = SamplingService(sampling_repos, default_seed=42)
    spec = SamplingSpec(strategy=SamplingStrategy.RANDOM, size=4, seed=99)
    a = svc.sample_videos("UCstrat0000000000000000000", spec).entity_ids
    b = svc.sample_videos(
        "UCstrat0000000000000000000",
        SamplingSpec(strategy=SamplingStrategy.RANDOM, size=4, seed=99),
    ).entity_ids
    assert a == b


# ----------------------------------------------------------------------
# collect(...) enrichment-quota skips are observable
# ----------------------------------------------------------------------
class _TwoVideoProvider(AcquisitionProvider):
    """Deterministic provider exposing two channel entries for enrichment."""

    def extract_recommendations(self, video_url: str):
        raise RecommendationUnsupportedError("no recommendations available")

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        return ChannelExtract(
            channel={
                "id": "UCcan0000000000000000000",
                "title": "Can enrich channel",
                "url": channel_url,
            },
            videos=[
                {"id": "v1", "title": "One", "url": "https://www.youtube.com/watch?v=v1"},
                {"id": "v2", "title": "Two", "url": "https://www.youtube.com/watch?v=v2"},
            ],
        )

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {
            "id": video_id,
            "title": "Observed",
            "channel_id": "UCcan0000000000000000000",
            "url": video_url,
            "view_count": 800,
            "like_count": 20,
        }


@pytest.fixture
def quota_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "quota")
    from SocialScienceResearch.api import create_app
    from fastapi.testclient import TestClient

    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="quota")
    settings = SocialScienceSettings(
        repository=rs,
        collection=CollectionSettings(
            enrich_video_stats=True, max_videos_to_enrich=1
        ),
    )
    app = create_app(settings, provider=_TwoVideoProvider())
    return TestClient(app)


def test_enrichment_quota_skip_is_observable(quota_client) -> None:
    r = quota_client.post(
        f"{PREFIX}/collect",
        json={"targets": [{"kind": "channel", "url": "https://www.youtube.com/@can"}]},
    )
    assert r.status_code in (200, 202), r.text
    result = _wait_for_result(quota_client, r.json()["job_id"])
    inner = result["results"][0]
    assert inner["status"] in ("success", "partial")
    reasons = {item["reason"] for item in inner["skipped"]}
    assert reasons, "expected at least one enrichment quota skip"
    assert any("enrichment quota" in reason.lower() for reason in reasons)


# ----------------------------------------------------------------------
# recommendation target from unsupported provider -> structured error
# ----------------------------------------------------------------------
class _UnsupportedRecsProvider(_TwoVideoProvider):
    def extract_recommendations(self, video_url: str):
        raise RecommendationUnsupportedError(
            "social platform does not expose recommendations"
        )


@pytest.fixture
def unsupported_recs_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "unsup_recs")
    from SocialScienceResearch.api import create_app
    from fastapi.testclient import TestClient

    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="unsup_recs")
    settings = SocialScienceSettings(repository=rs)
    app = create_app(settings, provider=_UnsupportedRecsProvider())
    return TestClient(app)


def test_recommendation_unsupported_is_structured_error(unsupported_recs_client) -> None:
    r = unsupported_recs_client.post(
        f"{PREFIX}/collect",
        json={
            "targets": [{"kind": "recommendation", "url": "https://www.youtube.com/watch?v=v1"}]
        },
    )
    assert r.status_code in (200, 202), r.text
    result = _wait_for_result(unsupported_recs_client, r.json()["job_id"])
    inner = result["results"][0]
    assert inner["status"] in ("success", "partial", "failed")
    assert inner["errors"]
    assert inner["errors"][0]["error_type"] == "recommendation_unsupported"


# ----------------------------------------------------------------------
# VideoFilter round-trips list fields
# ----------------------------------------------------------------------
def test_video_filter_keywords_tags() -> None:
    f = VideoFilter(
        keywords=["math", "science"],
        tags=["tutorial"],
        video_type="full",
        duration_min=500,
    )
    dumped = f.model_dump()
    assert dumped["keywords"] == ["math", "science"]
    assert dumped["tags"] == ["tutorial"]
    assert dumped["duration_min"] == 500


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _wait_for_result(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"{PREFIX}/jobs/{job_id}").json()
        if state["status"] in ("succeeded", "failed", "cancelled"):
            return client.get(f"{PREFIX}/jobs/{job_id}/result").json()
        time.sleep(0.02)
    pytest.fail("collection job did not finish in time")