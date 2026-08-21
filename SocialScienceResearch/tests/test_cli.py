"""End-to-end tests for the CLI wiring (no network)."""

from __future__ import annotations

import datetime

from SocialScienceResearch.domain.enums import RunType
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import utcnow


def _seed(tmp_path, repo_settings):
    repos = build_excel_repositories(repo_settings)
    repos.runs.create_run(
        CollectionRun(
            run_id="run_cli_1",
            run_type=RunType.CHANNEL,
            target_url="https://www.youtube.com/@example",
            target_channel_id="UCcli000000000000000000000",
            started_at=utcnow(),
            status="success",
            entities_discovered=2,
            entities_succeeded=2,
        )
    )
    repos.channels.upsert_channel(
        Channel(
            channel_id="UCcli000000000000000000000",
            url="https://www.youtube.com/channel/UCcli000000000000000000000",
            title="CLI Channel",
            first_observed_run_id="run_cli_1",
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_cli_ch",
            collection_run_id="run_cli_1",
            channel_id="UCcli000000000000000000000",
            observed_at=utcnow(),
            subscriber_count=555,
            video_count=2,
            view_count=1000,
        )
    )
    for i, (vid, views) in enumerate([("cli_v1", 800), ("cli_v2", 200)]):
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id="UCcli000000000000000000000",
                title=f"CLI Video {i}",
                first_observed_run_id="run_cli_1",
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_cli_{vid}",
                collection_run_id="run_cli_1",
                video_id=vid,
                observed_at=utcnow(),
                view_count=views,
                like_count=views // 10,
            )
        )
    repos.store.close()
    return repos


def _run_cli(monkeypatch, tmp_path, argv):
    monkeypatch.setenv("SOCIAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_DATASET_NAME", "dataset")
    from SocialScienceResearch.cli import main

    return main(argv)


def test_cli_runs_list(monkeypatch, tmp_path, capsys) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings

    _seed(tmp_path, RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset"))
    code = _run_cli(monkeypatch, tmp_path, ["runs", "list"])
    out = capsys.readouterr().out
    assert code == 0
    assert "run_cli_1" in out


def test_cli_analytics_channel(monkeypatch, tmp_path, capsys) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings

    _seed(tmp_path, RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset"))
    code = _run_cli(monkeypatch, tmp_path, ["analytics", "channel", "UCcli000000000000000000000"])
    out = capsys.readouterr().out
    assert code == 0
    assert "555" in out


def test_cli_analytics_video(monkeypatch, tmp_path, capsys) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings

    _seed(tmp_path, RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset"))
    code = _run_cli(monkeypatch, tmp_path, ["analytics", "video", "cli_v1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "800" in out


def test_cli_sample_videos(monkeypatch, tmp_path, capsys) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings

    _seed(tmp_path, RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset"))
    code = _run_cli(
        monkeypatch,
        tmp_path,
        ["sample", "videos", "UCcli000000000000000000000", "--strategy", "top_views", "--size", "1"],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "cli_v1" in out
    assert "cli_v2" not in out


def test_cli_runs_errors_empty(monkeypatch, tmp_path, capsys) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings

    _seed(tmp_path, RepositorySettings(data_dir=str(tmp_path), dataset_name="dataset"))
    code = _run_cli(monkeypatch, tmp_path, ["runs", "errors", "run_cli_1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No errors" in out
