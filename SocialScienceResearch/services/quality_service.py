"""Quality / coverage reporting for a collected dataset.

Answers "what did we actually capture, and how complete is it?" with explicit
availability counts - coverage is never implied from absence. A video counts
as *covered for comments* only when comment rows exist for it, and as
*covered for transcripts* only when a transcript record with status
``available`` exists (missing/unsupported are reported as their own buckets,
never folded into coverage).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from SocialScienceResearch.domain.enums import TranscriptStatus
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.utils.idgen import utcnow


class CoverageReport(BaseModel):
    """Snapshot of dataset completeness at a point in time."""

    generated_at: datetime
    total_channels: int
    total_videos: int
    total_comments: int
    videos_with_comments: int
    comment_coverage: float
    transcripts_available: int
    transcripts_missing: int
    transcripts_unsupported: int
    transcript_coverage: float
    total_runs: int
    last_run_id: str | None = None
    last_run_at: datetime | None = None


class QualityService:
    """Reports on the completeness of the collected corpus."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def coverage(self) -> CoverageReport:
        videos = self._repos.videos.list_videos()
        total_videos = len(videos)

        videos_with_comments = 0
        for video in videos:
            if self._repos.comments.list_comments(video.video_id):
                videos_with_comments += 1

        transcript_rows = self._repos.transcripts.list_transcripts()
        by_status: dict[str, set[str]] = {
            TranscriptStatus.AVAILABLE.value: set(),
            TranscriptStatus.MISSING.value: set(),
            TranscriptStatus.UNSUPPORTED.value: set(),
        }
        for row in transcript_rows:
            key = row.status.value if row.status.value in by_status else "missing"
            by_status[key].add(row.video_id)

        total_comments = 0
        for video in videos:
            total_comments += len(self._repos.comments.list_comments(video.video_id))

        runs = self._repos.runs.list_runs()
        last_run = max(runs, key=lambda r: r.started_at) if runs else None

        return CoverageReport(
            generated_at=utcnow(),
            total_channels=len(self._repos.channels.list_channels()),
            total_videos=total_videos,
            total_comments=total_comments,
            videos_with_comments=videos_with_comments,
            comment_coverage=(
                round(videos_with_comments / total_videos, 4) if total_videos else 0.0
            ),
            transcripts_available=len(by_status["available"]),
            transcripts_missing=len(by_status["missing"]),
            transcripts_unsupported=len(by_status["unsupported"]),
            transcript_coverage=(
                round(len(by_status["available"]) / total_videos, 4)
                if total_videos
                else 0.0
            ),
            total_runs=len(runs),
            last_run_id=last_run.run_id if last_run else None,
            last_run_at=last_run.started_at if last_run else None,
        )

    def dataset_summary(self) -> dict[str, Any]:
        """Lightweight summary used by the UI dashboard header."""
        report = self.coverage()
        return {
            "generated_at": report.generated_at,
            "channels": report.total_channels,
            "videos": report.total_videos,
            "comments": report.total_comments,
            "transcripts_available": report.transcripts_available,
            "transcript_coverage": report.transcript_coverage,
            "runs": report.total_runs,
        }
