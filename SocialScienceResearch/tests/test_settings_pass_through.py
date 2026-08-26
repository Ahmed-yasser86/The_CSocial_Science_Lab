"""Tests that settings actually reach the services and repositories.

The B2 task asked to make settings authoritative at runtime (single source of
truth), so we lock the wiring down here:

  * ``flush_every`` drives the Excel workbook writer's in-memory flush.
  * ``long_video_threshold_seconds`` drives QueryService's availability/type
    classification.
  * sampling ``default_seed`` drives SamplingService's reproducible RNG.
  * jobs ``max_workers`` drives the JobManager thread pool.
  * ``DEFAULT_TOP_N`` is the single top-N constant.
  * CORS origins flow into the FastAPI middleware.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from SocialScienceResearch.config.settings import (
    DEFAULT_TOP_N,
    AnalyticsSettings,
    CollectionSettings,
    JobSettings,
    QuerySettings,
    RepositorySettings,
    SamplingSettings,
    SocialScienceSettings,
    _env_bool,
)
from SocialScienceResearch.domain.models import (
    Channel,
    CollectionRun,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.query import SamplingSpec, SamplingStrategy, VideoFilter
from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services import SamplingService


@pytest.fixture
def repos(tmp_path):
    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="wired")
    repos = build_excel_repositories(rs)
    yield repos
    repos.store.close()


# ----------------------------------------------------------------------
# collection constants single-sourced
# ----------------------------------------------------------------------
def test_comment_cap_is_single_default() -> None:
    from SocialScienceResearch.config.settings import DEFAULT_MAX_COMMENTS_PER_VIDEO

    assert CollectionSettings().max_comments_per_video == DEFAULT_MAX_COMMENTS_PER_VIDEO
    assert not hasattr(CollectionSettings(), "extra_comment_max")


def test_channel_enrichment_defaults_on_by_default() -> None:
    from SocialScienceResearch.config.settings import (
        DEFAULT_ENRICH_VIDEO_STATS,
        DEFAULT_MAX_VIDEOS_TO_ENRICH,
    )

    settings = CollectionSettings()
    # Channel scraping captures likes/comments out of the box (the bug this
    # default flip fixes); the per-run cap bounds the cost.
    assert settings.enrich_video_stats is DEFAULT_ENRICH_VIDEO_STATS
    assert settings.enrich_video_stats is True
    assert settings.max_videos_to_enrich == DEFAULT_MAX_VIDEOS_TO_ENRICH
    # Env override still wins (explicit "0" remains the unbounded escape hatch).
    assert _env_bool("SOCIAL_ENRICH_VIDEO_STATS", True) == settings.enrich_video_stats


def test_enrichment_concurrency_default_and_override(monkeypatch) -> None:
    from SocialScienceResearch.config.settings import (
        DEFAULT_ENRICHMENT_CONCURRENCY,
        ScraperSettings,
    )

    assert DEFAULT_ENRICHMENT_CONCURRENCY == 6
    assert ScraperSettings().enrichment_concurrency == 6
    monkeypatch.setenv("SOCIAL_ENRICHMENT_CONCURRENCY", "7")
    assert ScraperSettings().enrichment_concurrency == 7


def test_top_n_is_single_default() -> None:
    assert AnalyticsSettings().top_n == DEFAULT_TOP_N
    assert not hasattr(SamplingSettings(), "default_top_n")


# ----------------------------------------------------------------------
# flush_every reaches the workbook store
# ----------------------------------------------------------------------
def test_flush_every_drives_workbook_flush(tmp_path) -> None:
    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="flush", flush_every=2)
    repos = build_excel_repositories(rs)
    assert repos.store.flush_every == 2

    repos.channels.upsert_channel(
        Channel(
            channel_id="UCf00000000000000000000000",
            title="Flush",
            url="https://www.youtube.com/@flush",
            first_observed_run_id="r0",
        )
    )
    assert not rs.workbook_path.exists(), "below flush_every: no write yet"
    repos.channels.upsert_channel(
        Channel(
            channel_id="UCf00000000000000000000001",
            title="Flush 2",
            url="https://www.youtube.com/@flush2",
            first_observed_run_id="r0",
        )
    )
    assert rs.workbook_path.exists(), "flush_every reached: workbook written"
    repos.store.close()


# ----------------------------------------------------------------------
# long_video_threshold_seconds reaches QueryService classification
# ----------------------------------------------------------------------
def test_long_video_threshold_wired(repos) -> None:
    repos.runs.create_run(
        CollectionRun(
            run_id="r_thresh",
            run_type=RunType.VIDEO,
            status="success",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
            target_url="https://www.youtube.com/watch?v=vid_thresh",
            target_id="vid_thresh",
        )
    )
    for vid, duration, is_short in (
        ("vid_thresh", 250, False),
        ("vid_short", 60, True),
    ):
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id="UCthresh000000000000000000",
                title=f"Video {vid}",
                duration=duration,
                is_short=is_short,
                first_observed_run_id="r_thresh",
            )
        )
    channel_id = "UCthresh000000000000000000"

    from SocialScienceResearch.services import QueryService

    default = QueryService(repos)
    assert default.filter_videos(channel_id, VideoFilter(video_type="long")) == []
    assert default.filter_videos(channel_id, VideoFilter(video_type="short")) != []

    custom = QueryService(repos, settings=SocialScienceSettings(
        query=QuerySettings(long_video_threshold_seconds=200)
    ))
    long_rows = custom.filter_videos(channel_id, VideoFilter(video_type="long"))
    assert [v.video_id for v in long_rows] == ["vid_thresh"]
    short_rows = custom.filter_videos(channel_id, VideoFilter(video_type="short"))
    assert [v.video_id for v in short_rows] == ["vid_short"]
    assert custom._settings.query.long_video_threshold_seconds == 200  # noqa: SLF001


# ----------------------------------------------------------------------
# sampling default_seed reaches SamplingService
# ----------------------------------------------------------------------
def test_sampling_default_seed_wired(repos) -> None:
    svc = SamplingService(repos, default_seed=7)
    assert svc._default_seed == 7  # noqa: SLF001
    assert SamplingSettings().default_seed == 42  # stock default unchanged


def test_sampling_seed_reproducible_across_instances(repos) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(8):
        repos.videos.upsert_video(
            Video(
                video_id=f"seed_vid_{i}",
                url=f"https://www.youtube.com/watch?v=seed_vid_{i}",
                channel_id="UCseed00000000000000000000",
                title=f"Seed video {i}",
                first_observed_run_id="r_seed",
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_{i}",
                collection_run_id="r_seed",
                video_id=f"seed_vid_{i}",
                observed_at=now,
                view_count=100 + i,
            )
        )
    a = SamplingService(repos, default_seed=99)
    b = SamplingService(repos, default_seed=99)
    spec = SamplingSpec(strategy=SamplingStrategy.RANDOM, size=3)
    a_ids = a.sample_videos("UCseed00000000000000000000", spec).entity_ids
    b_ids = b.sample_videos("UCseed00000000000000000000", spec).entity_ids
    assert a_ids == b_ids, "same seed must reproduce the same random sample"
    for other_seed in (100, 101, 102):
        other = SamplingService(repos, default_seed=other_seed)
        if other.sample_videos("UCseed00000000000000000000", spec).entity_ids != a_ids:
            break
    else:
        pytest.fail("different seeds all produced identical random samples")


# ----------------------------------------------------------------------
# jobs max_workers reaches the JobManager pool
# ----------------------------------------------------------------------
def test_job_max_workers_wired(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    from SocialScienceResearch.api import create_app
    from SocialScienceResearch.config.settings import DEFAULT_JOB_MAX_WORKERS

    assert JobSettings().max_workers == DEFAULT_JOB_MAX_WORKERS
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="mw"),
        jobs=JobSettings(max_workers=3),
    )
    app = create_app(settings)
    pool = app.state.services["jobs"]
    assert pool._executor._max_workers == 3  # noqa: SLF001


# ----------------------------------------------------------------------
# CORS origins flow into the middleware
# ----------------------------------------------------------------------
def test_cors_origins_wired(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    from SocialScienceResearch.api import create_app
    from starlette.middleware.cors import CORSMiddleware

    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="cors"),
        api=SocialScienceSettings().api,  # stock origins
    )
    app = create_app(settings)
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors
    assert cors[0].kwargs["allow_origins"] == settings.api.cors_origins