"""Command-line entry point for the SocialScienceResearch module.

Usage::

    python -m SocialScienceResearch collect channel <url>
    python -m SocialScienceResearch collect video <url>
    python -m SocialScienceResearch collect recommendations <url>
    python -m SocialScienceResearch runs list
    python -m SocialScienceResearch runs errors <run_id>
    python -m SocialScienceResearch analytics channel <channel_id>
    python -m SocialScienceResearch analytics video <video_id>
    python -m SocialScienceResearch sample videos <channel_id> --strategy top_views --size 10
    python -m SocialScienceResearch sample comments <video_id> --strategy random --size 10

All commands persist into the Excel workbook configured by
``SOCIAL_DATA_DIR`` / ``SOCIAL_DATASET_NAME`` (see ``config.settings``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from SocialScienceResearch.acquisition import YtDlpAcquisitionProvider
from SocialScienceResearch.config.settings import (
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import DataAvailability, SamplingStrategy
from SocialScienceResearch.domain.query import SamplingSpec
from SocialScienceResearch.persistence.factory import build_repositories
from SocialScienceResearch.services import (
    AnalyticsService,
    CollectionService,
    RecommendationService,
    SamplingService,
)
from SocialScienceResearch.utils.logger import (
    get_logger,
    log_error,
    log_header,
    log_success,
)

logger = get_logger(__name__)


def _services(settings: SocialScienceSettings):
    repos = build_repositories(settings.repository)
    provider = YtDlpAcquisitionProvider(
        settings=settings.scraper, collection=settings.collection
    )
    return {
        "repos": repos,
        "collection": CollectionService(provider, repos, settings=settings),
        "recommendations": RecommendationService(provider, repos, settings=settings),
        "analytics": AnalyticsService(repos),
        "sampling": SamplingService(repos, settings.sampling.default_seed),
    }


def _print_collection_result(result) -> None:
    log_header(f"Run {result.run_id} [{result.status.value}]")
    print(f"  type       : {result.run_type.value}")
    print(f"  target     : {result.target_url}")
    print(f"  target id  : {result.target_id}")
    print(f"  discovered : {result.entities_discovered}")
    print(f"  created    : {result.entities_created}")
    print(f"  existing   : {result.entities_existing}")
    print(f"  failed     : {result.entities_failed}")
    print(f"  comments   : {result.comments_collected}")
    for error in result.errors:
        print(f"  error      : [{error.error_type.value}] {error.message}")


def _cmd_collect_channel(settings, args) -> int:
    svc = _services(settings)
    result = svc["collection"].collect_channel(args.url)
    _print_collection_result(result)
    svc["repos"].store.close()
    return 0


def _cmd_collect_video(settings, args) -> int:
    svc = _services(settings)
    result = svc["collection"].collect_video(args.url)
    _print_collection_result(result)
    svc["repos"].store.close()
    return 0


def _cmd_collect_recommendations(settings, args) -> int:
    svc = _services(settings)
    result = svc["recommendations"].collect_recommendations(args.url)
    _print_collection_result(result)
    svc["repos"].store.close()
    return 0


def _cmd_runs_list(settings, args) -> int:
    svc = _services(settings)
    runs = svc["repos"].runs.list_runs()
    if not runs:
        print("No runs recorded yet.")
        return 0
    for run in reversed(runs):
        target = run.target_channel_id or run.target_video_id or "-"
        print(
            f"{run.run_id}  {run.run_type.value:<14} {run.status.value:<8} "
            f"{run.started_at:%Y-%m-%d %H:%M}  target={target}"
        )
    svc["repos"].store.close()
    return 0


def _cmd_runs_errors(settings, args) -> int:
    svc = _services(settings)
    errors = svc["repos"].runs.list_errors(args.run_id)
    if not errors:
        print(f"No errors for run {args.run_id}.")
        return 0
    for error in errors:
        print(
            f"[{error.error_type.value}] {error.entity_type.value}"
            f" id={error.entity_id} retryable={error.retryable}: {error.message}"
        )
    svc["repos"].store.close()
    return 0


def _print_value(value, label: str) -> None:
    if value.availability == DataAvailability.AVAILABLE:
        print(f"  {label:<22}: {value.value}")
    else:
        print(f"  {label:<22}: {value.availability.value} (no value)")


def _cmd_analytics_channel(settings, args) -> int:
    svc = _services(settings)
    overview = svc["analytics"].channel_overview(args.channel_id)
    print(f"Channel {args.channel_id}")
    _print_value(overview.subscriber_count, "subscribers")
    _print_value(overview.video_count, "videos")
    _print_value(overview.view_count, "total views")
    svc["repos"].store.close()
    return 0


def _cmd_analytics_video(settings, args) -> int:
    svc = _services(settings)
    eng = svc["analytics"].video_engagement(args.video_id)
    print(f"Video {args.video_id}")
    _print_value(eng.views, "views")
    _print_value(eng.likes, "likes")
    _print_value(eng.comments, "comments")
    _print_value(eng.engagement_rate, "engagement rate")
    _print_value(eng.like_rate, "like rate")
    _print_value(eng.comment_rate, "comment rate")
    svc["repos"].store.close()
    return 0


def _cmd_sample_videos(settings, args) -> int:
    svc = _services(settings)
    spec = SamplingSpec(
        strategy=SamplingStrategy(args.strategy),
        size=args.size,
        seed=args.seed,
        strata=args.strata,
        sample_per_stratum=args.sample_per_stratum,
    )
    result = svc["sampling"].sample_videos(args.channel_id, spec)
    print(
        f"{result.strategy.value} sample: {result.sample_size}/{result.population_size} "
        f"(seed={result.seed}, missing_metric={result.missing_metric_count})"
    )
    for video_id in result.entity_ids:
        print(f"  {video_id}")
    svc["repos"].store.close()
    return 0


def _cmd_sample_comments(settings, args) -> int:
    svc = _services(settings)
    spec = SamplingSpec(
        strategy=SamplingStrategy(args.strategy),
        size=args.size,
        seed=args.seed,
        strata=args.strata,
        sample_per_stratum=args.sample_per_stratum,
    )
    result = svc["sampling"].sample_comments(args.video_id, spec)
    print(
        f"{result.strategy.value} sample: {result.sample_size}/{result.population_size} "
        f"(seed={result.seed})"
    )
    for comment_id in result.entity_ids:
        print(f"  {comment_id}")
    svc["repos"].store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m SocialScienceResearch",
        description="YouTube computational social science: collection, sampling, analytics.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="run a collection workflow")
    collect_sub = collect.add_subparsers(dest="collect_kind", required=True)
    c = collect_sub.add_parser("channel")
    c.add_argument("url")
    c.set_defaults(func=_cmd_collect_channel)
    v = collect_sub.add_parser("video")
    v.add_argument("url")
    v.set_defaults(func=_cmd_collect_video)
    r = collect_sub.add_parser("recommendations")
    r.add_argument("url")
    r.set_defaults(func=_cmd_collect_recommendations)

    runs = sub.add_parser("runs", help="inspect collection runs")
    runs_sub = runs.add_subparsers(dest="runs_kind", required=True)
    rl = runs_sub.add_parser("list")
    rl.set_defaults(func=_cmd_runs_list)
    re_ = runs_sub.add_parser("errors")
    re_.add_argument("run_id")
    re_.set_defaults(func=_cmd_runs_errors)

    analytics = sub.add_parser("analytics", help="compute research analytics")
    analytics_sub = analytics.add_subparsers(dest="analytics_kind", required=True)
    ac = analytics_sub.add_parser("channel")
    ac.add_argument("channel_id")
    ac.set_defaults(func=_cmd_analytics_channel)
    av = analytics_sub.add_parser("video")
    av.add_argument("video_id")
    av.set_defaults(func=_cmd_analytics_video)

    sample = sub.add_parser("sample", help="reproducible research sampling")
    sample_sub = sample.add_subparsers(dest="sample_kind", required=True)
    sv = sample_sub.add_parser("videos")
    sv.add_argument("channel_id")
    sv.add_argument("--strategy", required=True)
    sv.add_argument("--size", type=int, default=None)
    sv.add_argument("--seed", type=int, default=None)
    sv.add_argument("--strata", default=None)
    sv.add_argument("--sample-per-stratum", type=int, default=None)
    sv.set_defaults(func=_cmd_sample_videos)
    sc = sample_sub.add_parser("comments")
    sc.add_argument("video_id")
    sc.add_argument("--strategy", required=True)
    sc.add_argument("--size", type=int, default=None)
    sc.add_argument("--seed", type=int, default=None)
    sc.add_argument("--strata", default=None)
    sc.add_argument("--sample-per-stratum", type=int, default=None)
    sc.set_defaults(func=_cmd_sample_comments)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = SocialScienceSettings()
    try:
        return args.func(settings, args)
    except KeyboardInterrupt:
        log_error("Interrupted by user.")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        log_error(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
