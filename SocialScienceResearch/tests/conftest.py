"""Shared fixtures for SocialScienceResearch tests.

All fixtures here are local and deterministic - no live YouTube requests.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

# Legacy service/API tests exercise the Excel backend through settings objects
# that don't pin a backend explicitly. The production default is now "sql",
# so lock this suite to "excel" for the tests that build settings without an
# explicit backend. SQL-backend tests (test_sql_backend.py) pass backend="sql"
# explicitly and are unaffected.
os.environ.setdefault("SOCIAL_REPOSITORY_BACKEND", "excel")

from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Comment,
    CommentObservation,
    Video,
    VideoObservation,
)


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def excel_repos(tmp_path):
    """Real Excel-backed repositories on a temporary directory."""
    from SocialScienceResearch.config.settings import RepositorySettings
    from SocialScienceResearch.persistence.excel_repository import (
        build_excel_repositories,
    )

    return build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset")
    )


@pytest.fixture
def sample_run(fixed_now: datetime) -> CollectionRun:
    return CollectionRun(
        run_id="run_test_20260810_000000_abc12345",
        run_type=RunType.CHANNEL,
        target_url="https://www.youtube.com/@example",
        target_channel_id="UCexample00000000000000000",
        started_at=fixed_now,
        status="pending",
    )


@pytest.fixture
def sample_channel() -> Channel:
    return Channel(
        channel_id="UCexample00000000000000000",
        url="https://www.youtube.com/channel/UCexample00000000000000000",
        title="Example Channel",
        handle="@example",
        first_observed_run_id="run_test_20260810_000000_abc12345",
    )


@pytest.fixture
def sample_channel_observation(fixed_now: datetime) -> ChannelObservation:
    return ChannelObservation(
        observation_id="obs_channel_0001",
        collection_run_id="run_test_20260810_000000_abc12345",
        channel_id="UCexample00000000000000000",
        observed_at=fixed_now,
        subscriber_count=100000,
        video_count=500,
        view_count=50_000_000,
    )


@pytest.fixture
def sample_video() -> Video:
    return Video(
        video_id="v1example0000000000000000001",
        url="https://www.youtube.com/watch?v=v1example0000000000000000001",
        channel_id="UCexample00000000000000000",
        title="Example Video",
        duration=300,
        first_observed_run_id="run_test_20260810_000000_abc12345",
    )


@pytest.fixture
def sample_video_observation(fixed_now: datetime) -> VideoObservation:
    return VideoObservation(
        observation_id="obs_video_0001",
        collection_run_id="run_test_20260810_000000_abc12345",
        video_id="v1example0000000000000000001",
        observed_at=fixed_now,
        view_count=1_000_000,
        like_count=50_000,
        comment_count=1_200,
    )


@pytest.fixture
def sample_comment() -> Comment:
    return Comment(
        comment_id="Uglyxamplecommentid0000001",
        video_id="v1example0000000000000000001",
        author_name="Researcher A",
        comment_text="This is an example comment.",
        first_observed_run_id="run_test_20260810_000000_abc12345",
    )


@pytest.fixture
def sample_comment_observation(fixed_now: datetime) -> CommentObservation:
    return CommentObservation(
        observation_id="obs_comment_0001",
        collection_run_id="run_test_20260810_000000_abc12345",
        comment_id="Uglyxamplecommentid0000001",
        observed_at=fixed_now,
        like_count=42,
        reply_count=3,
    )
