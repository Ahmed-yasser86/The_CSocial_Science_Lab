"""Local-first transcript guard tests (defense against redundant scraping / 429).

These avoid importing ``SocialScienceResearch.api`` (whose module-level app
singleton collides with a running backend). They drive ``CollectionService``
directly with excel repositories.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from SocialScienceResearch.acquisition.base import (
    AcquisitionProvider,
    TranscriptExtract,
)
from SocialScienceResearch.config.settings import (
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType, TranscriptStatus
from SocialScienceResearch.domain.models import CollectionRun, TranscriptRecord, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services.collection_service import CollectionService
from SocialScienceResearch.utils.idgen import new_id, new_run_id, utcnow


class CallCountingProvider(AcquisitionProvider):
    def __init__(self):
        self.transcript_calls = 0
        self.return_status = TranscriptStatus.AVAILABLE

    def extract_channel(self, channel_url): raise NotImplementedError
    def extract_video(self, video_url, *, include_comments=None): raise NotImplementedError
    def extract_recommendations(self, video_url): return []
    def extract_transcript(self, video_url, lang=None):
        self.transcript_calls += 1
        if self.return_status == TranscriptStatus.AVAILABLE:
            return TranscriptExtract(content="scraped text", lang=lang or "en",
                                     status=TranscriptStatus.AVAILABLE)
        return TranscriptExtract(status=self.return_status, message="nope")


def _settings(d):
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(d), dataset_name="coll", backend="excel"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
    )


def _seed_local_transcript(repos, run_id, video_id, data_dir, text="local transcript text", lang="en"):
    abs_path = repos.transcripts.write_artifact(video_id, text)
    relative = str(abs_path.relative_to(Path(data_dir)).as_posix())
    repos.transcripts.save_transcript(TranscriptRecord(
        transcript_id=new_id("tx"),
        video_id=video_id,
        collection_run_id=run_id,
        path=relative,
        lang=lang,
        status=TranscriptStatus.AVAILABLE,
        observed_at=utcnow(),
    ))


def _make_run():
    return CollectionRun(run_id=new_run_id(), run_type=RunType.RECOMMENDATION,
                         target_url="https://youtube.com/watch?v=v1",
                         started_at=utcnow(), status=CollectionStatus.SUCCESS)


def test_read_local_transcript_returns_text_when_available():
    with tempfile.TemporaryDirectory() as d:
        repos = build_excel_repositories(RepositorySettings(data_dir=d, dataset_name="coll"))
        run = _make_run()
        _seed_local_transcript(repos, run.run_id, "v1", str(d), text="hi")
        svc = CollectionService(CallCountingProvider(), repos, settings=_settings(d))
        text, lang = svc._read_local_transcript("v1")
        assert text == "hi"
        assert lang == "en"


def test_read_local_transcript_returns_none_when_absent():
    with tempfile.TemporaryDirectory() as d:
        repos = build_excel_repositories(RepositorySettings(data_dir=d, dataset_name="coll"))
        svc = CollectionService(CallCountingProvider(), repos, settings=_settings(d))
        assert svc._read_local_transcript("missing") == (None, None)


def test_collect_transcript_reuses_local_without_scraping():
    with tempfile.TemporaryDirectory() as d:
        repos = build_excel_repositories(RepositorySettings(data_dir=d, dataset_name="coll"))
        run = _make_run()
        _seed_local_transcript(repos, run.run_id, "v1", str(d), text="already here")
        provider = CallCountingProvider()
        svc = CollectionService(provider, repos, settings=_settings(d))
        video = Video(video_id="v1", url="https://youtube.com/watch?v=v1",
                      channel_id="c", title="t", first_observed_run_id=run.run_id)
        errors: list = []
        svc._collect_transcript(run, video, errors, {"collect_transcripts": True}, None)
        # The upstream provider must NOT be hit when the transcript is local.
        assert provider.transcript_calls == 0
        assert errors == []


def test_collect_transcript_scrapes_when_local_absent():
    with tempfile.TemporaryDirectory() as d:
        repos = build_excel_repositories(RepositorySettings(data_dir=d, dataset_name="coll"))
        run = _make_run()
        provider = CallCountingProvider()
        svc = CollectionService(provider, repos, settings=_settings(d))
        video = Video(video_id="v1", url="https://youtube.com/watch?v=v1",
                      channel_id="c", title="t", first_observed_run_id=run.run_id)
        errors: list = []
        svc._collect_transcript(run, video, errors, {"collect_transcripts": True}, None)
        # No local transcript -> must scrape exactly once.
        assert provider.transcript_calls == 1
        # And the scraped result is persisted for next time.
        rec = repos.transcripts.get_transcript("v1")
        assert rec is not None and rec.status == TranscriptStatus.AVAILABLE
