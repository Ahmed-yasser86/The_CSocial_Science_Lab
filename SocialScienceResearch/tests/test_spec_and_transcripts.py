"""Tests for the P0 spec-driven collection features.

Covers: spec resolution + multi-target collection, researcher comment
criteria (min likes / date window / cap), transcript persistence with explicit
availability, progress reporting, and correct success accounting when a
downstream capability fails (the video still counts as succeeded).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    ChannelExtract,
    TranscriptExtract,
)
from SocialScienceResearch.acquisition.errors import (
    TranscriptUnsupportedError,
    VideoUnavailableError,
)
from SocialScienceResearch.config.settings import (
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.collection import (
    CollectionSpec,
    CollectionTarget,
)
from SocialScienceResearch.domain.query import Operator, QueryCondition, QueryGroup
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    ErrorType,
    RunType,
    TargetKind,
    TranscriptStatus,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services import CollectionService

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


class TranscriptAwareProvider(AcquisitionProvider):
    """In-memory provider with controllable transcript behaviour."""

    def __init__(
        self,
        video_raw: dict[str, Any],
        *,
        transcript: str = "available",
        transcript_content: str = "Hello world.\nThis is a caption test.",
        transcript_lang: str = "en",
        fail_video: bool = False,
    ) -> None:
        self.video_raw = dict(video_raw)
        self.transcript = transcript
        self.transcript_content = transcript_content
        self.transcript_lang = transcript_lang
        self.fail_video = fail_video

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str, *, include_comments: bool | None = None) -> dict[str, Any]:
        if self.fail_video:
            raise VideoUnavailableError(f"Video unavailable: {video_url}")
        return self.video_raw

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        return []

    def extract_transcript(self, video_url: str, lang: str | None = None) -> TranscriptExtract:
        if self.transcript == "available":
            return TranscriptExtract(
                status=TranscriptStatus.AVAILABLE,
                content=self.transcript_content,
                lang=self.transcript_lang,
            )
        if self.transcript == "missing":
            return TranscriptExtract(
                status=TranscriptStatus.MISSING,
                message="no captions on this video",
            )
        raise TranscriptUnsupportedError("transcripts are unsupported")


def _build_service(tmp_path, provider, *, collect_comments=True):
    settings = SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="svc"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=collect_comments),
    )
    return CollectionService(provider, build_excel_repositories(settings.repository), settings=settings)


VIDEO_URL = "https://www.youtube.com/watch?v=v1example0000000000000000001"


def _video_spec(**overrides) -> CollectionSpec:
    defaults = {
        "targets": [CollectionTarget(kind=TargetKind.VIDEO, url=VIDEO_URL)],
        "collect_transcripts": True,
    }
    defaults.update(overrides)
    return CollectionSpec(**defaults)


# ----------------------------------------------------------------------
# Transcript persistence
# ----------------------------------------------------------------------
def test_video_run_persists_available_transcript(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_video(VIDEO_URL, spec=_video_spec())

    assert result.status == CollectionStatus.SUCCESS
    record = service._repos.transcripts.get_transcript(
        "v1example0000000000000000001"
    )
    assert record is not None
    assert record.status == TranscriptStatus.AVAILABLE
    assert record.lang == "en"
    assert record.collection_run_id == result.run_id

    artifact = Path(tmp_path) / "transcripts" / "v1example0000000000000000001.txt"
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == provider.transcript_content
    assert record.path == "transcripts/v1example0000000000000000001.txt"

    video = service._repos.videos.get_video("v1example0000000000000000001")
    assert video is not None
    assert video.transcript_status == "available"
    assert video.transcript_lang == "en"


def test_video_run_transcript_unsupported_is_explicit(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"), transcript="unsupported")
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_video(VIDEO_URL, spec=_video_spec())

    assert result.status == CollectionStatus.PARTIAL
    assert result.entities_failed == 1
    assert result.errors[0].error_type == ErrorType.TRANSCRIPT_UNSUPPORTED
    assert result.errors[0].entity_id == "v1example0000000000000000001"
    record = service._repos.transcripts.get_transcript(
        "v1example0000000000000000001"
    )
    assert record is not None
    assert record.status == TranscriptStatus.UNSUPPORTED
    # The video itself still persisted and counts as succeeded (no silent drop).
    assert result.entities_created == 1
    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    assert run.entities_succeeded == 1


def test_video_run_transcript_missing_is_recorded_not_failure(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"), transcript="missing")
    service = _build_service(tmp_path, provider, collect_comments=False)

    result = service.collect_video(VIDEO_URL, spec=_video_spec())

    # Absence of captions is an availability outcome, not a collection error.
    assert result.status == CollectionStatus.SUCCESS
    assert result.errors == []
    record = service._repos.transcripts.get_transcript(
        "v1example0000000000000000001"
    )
    assert record is not None
    assert record.status == TranscriptStatus.MISSING
    assert record.message == "no captions on this video"


def test_transcripts_off_by_default_never_calls_provider(tmp_path) -> None:
    calls = []

    class _Spy(TranscriptAwareProvider):
        def extract_transcript(self, video_url, lang=None):
            calls.append(video_url)
            return super().extract_transcript(video_url, lang=lang)

    service = _build_service(tmp_path, _Spy(_load("video_raw.json")), collect_comments=False)
    result = service.collect_video(VIDEO_URL, spec=_video_spec(collect_transcripts=False))

    assert result.status == CollectionStatus.SUCCESS
    assert calls == []
    assert service._repos.transcripts.list_transcripts() == []


# ----------------------------------------------------------------------
# Researcher comment criteria
# ----------------------------------------------------------------------
def _video_with_comments() -> dict[str, Any]:
    video = _load("video_raw.json")
    video["comments"] = _load("comments_raw.json")
    return video


def test_comment_min_likes_filters(tmp_path) -> None:
    provider = TranscriptAwareProvider(_video_with_comments())
    service = _build_service(tmp_path, provider)
    spec = _video_spec(collect_transcripts=False, comment_min_likes=10)

    result = service.collect_video(VIDEO_URL, spec=spec)

    # Only the 42-like comment passes; the 5-like and 0-like are excluded.
    assert result.comments_collected == 1
    comments = service._repos.comments.list_comments(
        "v1example0000000000000000001"
    )
    assert {c.comment_id for c in comments} == {"Ugxrootcomment0000000000001"}
    assert result.status == CollectionStatus.SUCCESS


def test_comment_date_window_filters(tmp_path) -> None:
    provider = TranscriptAwareProvider(_video_with_comments())
    service = _build_service(tmp_path, provider)
    # comments_raw.json timestamps: 2024-01-15 10:20, 2024-01-16 11:40,
    # 2024-01-17 15:20 (UTC); a window from midnight on the 16th keeps two.
    date_from = datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)
    spec = _video_spec(
        collect_transcripts=False, comment_date_from=date_from
    )

    result = service.collect_video(VIDEO_URL, spec=spec)

    assert result.comments_collected == 2
    assert result.status == CollectionStatus.SUCCESS


def test_comment_max_cap_applies(tmp_path) -> None:
    provider = TranscriptAwareProvider(_video_with_comments())
    service = _build_service(tmp_path, provider)
    spec = _video_spec(collect_transcripts=False, max_comments_per_video=2)

    result = service.collect_video(VIDEO_URL, spec=spec)

    assert result.comments_collected == 2
    assert result.status == CollectionStatus.SUCCESS


def test_comment_criteria_filters(tmp_path) -> None:
    provider = TranscriptAwareProvider(_video_with_comments())
    service = _build_service(tmp_path, provider)
    spec = _video_spec(
        collect_transcripts=False,
        comment_criteria=QueryGroup(
            operator="AND",
            conditions=[
                QueryCondition(
                    variable="like_count", operator=Operator.GTE, value=10
                )
            ],
        ),
    )

    result = service.collect_video(VIDEO_URL, spec=spec)

    assert result.comments_collected == 1
    comments = service._repos.comments.list_comments(
        "v1example0000000000000000001"
    )
    assert {c.comment_id for c in comments} == {"Ugxrootcomment0000000000001"}


def test_comment_criteria_roots_only(tmp_path) -> None:
    provider = TranscriptAwareProvider(_video_with_comments())
    service = _build_service(tmp_path, provider)
    spec = _video_spec(
        collect_transcripts=False,
        comment_criteria=QueryGroup(
            operator="AND",
            conditions=[
                QueryCondition(variable="is_reply", operator=Operator.EQ, value=False)
            ],
        ),
    )

    result = service.collect_video(VIDEO_URL, spec=spec)

    assert result.comments_collected == 2
    comments = service._repos.comments.list_comments(
        "v1example0000000000000000001"
    )
    assert {c.comment_id for c in comments} == {
        "Ugxrootcomment0000000000001",
        "Ugxrootcomment0000000000002",
    }


def test_comment_criteria_unknown_variable_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown variable 'nope'"):
        _video_spec(
            comment_criteria=QueryGroup(
                operator="AND",
                conditions=[
                    QueryCondition(variable="nope", operator=Operator.EQ, value=1)
                ],
            ),
        )


def test_resolved_spec_recorded_in_run_config(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)
    spec = _video_spec(comment_min_likes=25)

    result = service.collect_video(VIDEO_URL, spec=spec)

    run = service._repos.runs.get_run(result.run_id)
    assert run is not None
    config = run.config_json
    assert config["comment_min_likes"] == 25
    assert config["collect_transcripts"] is True
    assert config["collect_comments"] is False
    assert config["spec_hash"] == spec.spec_hash
    # Timestamps are stored in a JSON-safe ISO form.
    assert config["comment_date_from"] is None


# ----------------------------------------------------------------------
# Multi-target collection + progress reporting
# ----------------------------------------------------------------------
def test_collect_runs_every_target_in_order(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)
    spec = CollectionSpec(
        targets=[
            CollectionTarget(kind=TargetKind.VIDEO, url=VIDEO_URL),
            CollectionTarget(
                kind=TargetKind.VIDEO,
                url="https://www.youtube.com/watch?v=v1example0000000000000000001",
            ),
        ],
        collect_transcripts=False,
    )

    results = service.collect(spec)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r.run_type == RunType.VIDEO for r in results)
    assert len(service._repos.runs.list_runs()) == 2


def test_progress_reporter_receives_checkpoints(tmp_path) -> None:
    provider = TranscriptAwareProvider(_load("video_raw.json"))
    service = _build_service(tmp_path, provider, collect_comments=False)
    checkpoints: list[dict[str, Any]] = []

    def reporter(**kwargs: Any) -> None:
        checkpoints.append(kwargs)

    service.collect_video(VIDEO_URL, spec=_video_spec(), reporter=reporter)

    stages = [c["stage"] for c in checkpoints]
    assert "video/extract" in stages
    assert "video/metadata" in stages
    assert "transcripts" in stages
