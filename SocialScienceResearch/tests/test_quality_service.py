"""Tests for quality / coverage reporting (explicit availability)."""

from __future__ import annotations

import json
from pathlib import Path

from SocialScienceResearch.config.settings import RepositorySettings
from SocialScienceResearch.domain.enums import TranscriptStatus
from SocialScienceResearch.domain.models import (
    CollectionRun,
    TranscriptRecord,
    Video,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.quality_service import QualityService
from SocialScienceResearch.utils.idgen import utcnow

FIXTURES = Path(__file__).parent / "fixtures"
VIDEO_URL = "https://www.youtube.com/watch?v=v1example0000000000000000001"


def _seed(tmp_path):
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="quality")
    )
    repos.runs.create_run(
        CollectionRun(
            run_id="run_q_1",
            run_type="video",
            target_url=VIDEO_URL,
            target_video_id="v1example0000000000000000001",
            started_at=utcnow(),
            status="success",
        )
    )
    # Two videos; one has an available transcript, one is unsupported, and a
    # third is collected but has no transcript row at all.
    for video_id in ("available_video", "unsupported_video", "bare_video"):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id="UCq000000000000000000000",
                title=video_id,
                first_observed_run_id="run_q_1",
            )
        )
    repos.transcripts.save_transcript(
        TranscriptRecord(
            transcript_id="tx_avail",
            video_id="available_video",
            collection_run_id="run_q_1",
            path="transcripts/available_video.txt",
            lang="en",
            status=TranscriptStatus.AVAILABLE,
            observed_at=utcnow(),
        )
    )
    repos.transcripts.save_transcript(
        TranscriptRecord(
            transcript_id="tx_unsup",
            video_id="unsupported_video",
            collection_run_id="run_q_1",
            status=TranscriptStatus.UNSUPPORTED,
            message="captions blocked",
            observed_at=utcnow(),
        )
    )
    repos.transcripts.save_transcript(
        TranscriptRecord(
            transcript_id="tx_missing",
            video_id="bare_video",
            collection_run_id="run_q_1",
            status=TranscriptStatus.MISSING,
            message="no captions",
            observed_at=utcnow(),
        )
    )
    return repos


def test_coverage_buckets_are_explicit(tmp_path) -> None:
    repos = _seed(tmp_path)
    report = QualityService(repos).coverage()

    assert report.total_videos == 3
    assert report.transcripts_available == 1
    assert report.transcripts_missing == 1
    assert report.transcripts_unsupported == 1
    # Coverage is only the *available* bucket, never inflated by missing rows.
    assert report.transcript_coverage == round(1 / 3, 4)
    assert report.total_runs == 1


def test_coverage_empty_dataset(tmp_path) -> None:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="quality_empty")
    )
    report = QualityService(repos).coverage()

    assert report.total_videos == 0
    assert report.transcript_coverage == 0.0
    assert report.comment_coverage == 0.0
    assert report.total_runs == 0
    assert report.last_run_id is None


def test_dataset_summary_shape(tmp_path) -> None:
    repos = _seed(tmp_path)
    summary = QualityService(repos).dataset_summary()

    assert summary["videos"] == 3
    assert summary["transcripts_available"] == 1
    assert summary["runs"] == 1
    assert "generated_at" in summary
