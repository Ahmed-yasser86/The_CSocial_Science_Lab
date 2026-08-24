"""Stress-test seeder: fills a scratch SQL database with a large synthetic
YouTube research corpus so heavy analytics endpoints can be benchmarked
before snapshot / commenter-network features are built on top.

Deterministic (seeded RNG, fixed ids): re-running against the same scratch
database is idempotent (all inserts use ``ON CONFLICT DO NOTHING``).

The synthetic graph is deliberately skewed (Zipf/power-law-ish degree
distribution over videos AND commenters) with channel-shaped communities, so
centrality/community metrics have real structure to chew on.

IMPORTANT: never point this at ``data/`` or the production database - pass an
explicit ``--db`` URL pointing at a scratch database, e.g.::

    python scripts/stress_seed.py \
        --db postgresql://postgres:123456@localhost:5432/social_science_stress

Run:  .venv\\Scripts\\python.exe -m SocialScienceResearch.scripts.stress_seed ...
or    .venv\\Scripts\\python.exe SocialScienceResearch\\scripts\\stress_seed.py ...
(from the repository root so the ``SocialScienceResearch`` package imports).

NOTE: despite the historical "scratch SQLite" naming, the persistence layer is
PostgreSQL-only (psycopg 3: ANY(...), RETURNING xmax, JSONB); SQLite URLs are
not supported anywhere in ``persistence/sql``.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

# Allow running as a plain script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from SocialScienceResearch.domain.dataset_models import Dataset, Project  # noqa: E402
from SocialScienceResearch.domain.enums import (  # noqa: E402
    CollectionStatus,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.models import (  # noqa: E402
    Channel,
    ChannelObservation,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.serialization import headers_for  # noqa: E402
from SocialScienceResearch.persistence.sql.database import SqlDatabase  # noqa: E402
from SocialScienceResearch.persistence.sql.mapping import _params  # noqa: E402

#: Fixed wall-clock anchor so timestamps are reproducible across seeds/runs.
ANCHOR = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
SPREAD_DAYS = 90


def _bulk_insert(db: SqlDatabase, table: str, key_col: str, models: list) -> int:
    """Idempotent batch insert of domain models into ``table``.

    Uses a dedicated psycopg connection + ``cursor.executemany`` because
    ``SqlDatabase.executemany`` calls a non-existent
    ``Connection.executemany`` (psycopg 3 exposes it on the cursor).
    """
    if not models:
        return 0
    cols = headers_for(type(models[0]))
    col_sql = ", ".join(f'"{c}"' for c in cols)
    ph = ", ".join(f"%({c})s" for c in cols)
    sql = (
        f'INSERT INTO "{table}" ({col_sql}) VALUES ({ph}) '
        f'ON CONFLICT ("{key_col}") DO NOTHING'
    )
    with psycopg.connect(db.url) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, [_params(m) for m in models])
        conn.commit()
    return len(models)


class ZipfPicker:
    """Sample indices with a skewed (power-law-ish) distribution."""

    def __init__(self, n: int, alpha: float = 1.1, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        weights = [1.0 / (i + 1) ** alpha for i in range(n)]
        total = sum(weights)
        self._cum: list[float] = []
        acc = 0.0
        for w in weights:
            acc += w / total
            self._cum.append(acc)

    def pick(self) -> int:
        x = self._rng.random()
        lo, hi = 0, len(self._cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self._cum[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        return lo


def build_corpus(
    *,
    videos: int,
    edges_per_video: int,
    commenters: int,
    comments_per_video: int,
    runs: int,
    rng: random.Random,
):
    run_ids = [f"stress_run_{i + 1:03d}" for i in range(runs)]
    n_channels = max(4, videos // 20)
    channel_ids = [f"ch_{i:04d}" for i in range(n_channels)]
    video_ids = [f"vid_{i:06d}" for i in range(videos)]
    commenter_ids = [f"usr_{i:05d}" for i in range(commenters)]

    # Channel == community: contiguous blocks of videos per channel.
    channel_of: dict[str, str] = {}
    for i, vid in enumerate(video_ids):
        channel_of[vid] = channel_ids[i % n_channels]
    videos_by_channel: dict[str, list[str]] = {}
    for vid, ch in channel_of.items():
        videos_by_channel.setdefault(ch, []).append(vid)

    # ~10% unscraped: no outgoing recommendation edges, recommendations_scraped=False.
    unscraped = {v for v in video_ids if rng.random() < 0.10}

    ts_base = ANCHOR - timedelta(days=SPREAD_DAYS)

    def spread_ts() -> datetime:
        return ts_base + timedelta(
            days=rng.uniform(0, SPREAD_DAYS), seconds=rng.uniform(0, 86_400)
        )

    def upload_ts() -> datetime:
        return ANCHOR - timedelta(days=rng.uniform(30, 900))

    # --- Runs -------------------------------------------------------------
    rows_runs = [
        CollectionRun(
            run_id=rid,
            run_type=RunType.RECOMMENDATION,
            target_url=f"https://example.invalid/stress/{rid}",
            started_at=ANCHOR - timedelta(days=SPREAD_DAYS, minutes=i),
            finished_at=ANCHOR - timedelta(days=SPREAD_DAYS, minutes=i - 5),
            status=CollectionStatus.SUCCESS,
            provider="stress-seed",
            entities_discovered=edges_per_video * (videos // runs),
            entities_succeeded=edges_per_video * (videos // runs),
            name=f"Stress slice {i + 1}/{runs}",
        )
        for i, rid in enumerate(run_ids)
    ]

    # --- Channels ---------------------------------------------------------
    rows_channels = [
        Channel(
            channel_id=cid,
            url=f"https://example.invalid/channel/{cid}",
            title=f"Stress Channel {cid}",
            description=f"Synthetic stress community {cid}",
            handle=f"@{cid}",
            joined_date=(ANCHOR - timedelta(days=365 * rng.uniform(1, 8))).date(),
            first_observed_run_id=run_ids[0],
        )
        for cid in channel_ids
    ]
    rows_channel_obs = [
        ChannelObservation(
            observation_id=f"obs_ch_{i:05d}",
            collection_run_id=run_ids[i % runs],
            channel_id=cid,
            observed_at=spread_ts(),
            subscriber_count=rng.randrange(1_000, 5_000_000),
            video_count=len(videos_by_channel[cid]),
            view_count=rng.randrange(10_000, 900_000_000),
        )
        for i, cid in enumerate(channel_ids)
    ]

    # --- Videos -----------------------------------------------------------
    rows_videos: list[Video] = []
    rows_video_obs: list[VideoObservation] = []
    for i, vid in enumerate(video_ids):
        rid = run_ids[i % runs]
        rows_videos.append(
            Video(
                video_id=vid,
                url=f"https://example.invalid/watch/{vid}",
                channel_id=channel_of[vid],
                title=f"Stress video {vid} about topic {i % 37}",
                description="Synthetic corpus row for benchmarking.",
                duration=int(rng.uniform(60, 3600)),
                upload_date=upload_ts().date(),
                upload_timestamp=upload_ts(),
                tags=[f"tag{i % 11}", f"topic{i % 37}"],
                categories=["Science", "Tech"][: 1 + i % 2],
                language="en",
                live_status="not_live",
                availability="available",
                is_short=bool(i % 17 == 0),
                thumbnail_url=f"https://example.invalid/thumb/{vid}.jpg",
                transcript_status="missing" if i % 3 else "available",
                transcript_lang="en",
                first_observed_run_id=rid,
                recommendations_scraped=vid not in unscraped,
            )
        )
        views = int(abs(rng.gauss(50_000, 40_000))) + 100
        rows_video_obs.append(
            VideoObservation(
                observation_id=f"obs_vid_{i:06d}",
                collection_run_id=rid,
                video_id=vid,
                observed_at=spread_ts(),
                view_count=views,
                like_count=int(views * rng.uniform(0.01, 0.08)),
                comment_count=comments_per_video,
                favorite_count=None,
            )
        )

    # --- Recommendation edges (skewed targets, cross-community hubs) ------
    global_picker = ZipfPicker(videos, alpha=1.1, rng=rng)
    rows_edges: list[RecommendationObservation] = []
    seq = 0
    for i, src in enumerate(video_ids):
        if src in unscraped:
            continue
        rid = run_ids[i % runs]
        home = videos_by_channel[channel_of[src]]
        targets: set[str] = set()
        while len(targets) < min(edges_per_video, videos - 1):
            # 70% preferential (global hubs), 30% within-channel community.
            if rng.random() < 0.7:
                tgt = video_ids[global_picker.pick()]
            else:
                tgt = home[rng.randrange(len(home))]
            if tgt != src:
                targets.add(tgt)
        for pos, tgt in enumerate(sorted(targets)):
            seq += 1
            rows_edges.append(
                RecommendationObservation(
                    observation_id=f"edge_{seq:07d}",
                    collection_run_id=rid,
                    source_video_id=src,
                    recommended_video_id=tgt,
                    position=pos,
                    status=RecommendationStatus.OBSERVED,
                    channel_id=channel_of[tgt],
                    channel_name=f"Stress Channel {channel_of[tgt]}",
                    title=f"Stress video {tgt} about topic {int(tgt[-6:]) % 37}",
                    observed_at=spread_ts(),
                )
            )

    # --- Comments (skewed authors, some reply chains) ----------------------
    author_picker = ZipfPicker(commenters, alpha=1.3, rng=rng)
    rows_comments: list[Comment] = []
    rows_comment_obs: list[CommentObservation] = []
    cseq = 0
    for i, vid in enumerate(video_ids):
        rid = run_ids[i % runs]
        roots: list[str] = []
        for c in range(comments_per_video):
            cseq += 1
            cid = f"cmt_{cseq:08d}"
            parent: str | None = None
            root: str | None = None
            is_reply = bool(roots) and rng.random() < 0.15
            if is_reply:
                parent = roots[rng.randrange(len(roots))]
                root = parent
            published = spread_ts()
            author = commenter_ids[author_picker.pick()]
            rows_comments.append(
                Comment(
                    comment_id=cid,
                    video_id=vid,
                    author_name=f"commenter {author}",
                    author_id=author,
                    comment_text=f"Synthetic comment #{c} on {vid}: "
                    + "lorem ipsum dolor sit amet " * (1 + cseq % 5),
                    published_at=published,
                    is_reply=is_reply,
                    parent_comment_id=parent,
                    root_comment_id=root,
                    is_author=False,
                    first_observed_run_id=rid,
                )
            )
            rows_comment_obs.append(
                CommentObservation(
                    observation_id=f"obs_cmt_{cseq:08d}",
                    collection_run_id=rid,
                    comment_id=cid,
                    observed_at=published + timedelta(hours=1),
                    like_count=int(abs(rng.gauss(5, 15))),
                    reply_count=0,
                    is_removed=rng.random() < 0.02,
                )
            )
            if not is_reply:
                roots.append(cid)
                # Cap root-chain memory per video.
                if len(roots) > 50:
                    roots = roots[-50:]

    # --- Minimal dataset + project ----------------------------------------
    rows_datasets = [
        Dataset(
            dataset_id="stress_dataset",
            name="Stress corpus",
            description="Synthetic stress-benchmark corpus",
            entity_type="video",
            created_at=ANCHOR,
            member_count=videos,
        )
    ]
    rows_projects = [
        Project(
            project_id="stress_project",
            name="Stress project",
            description="Synthetic stress-benchmark project",
            config_hash="stress",
            created_at=ANCHOR,
            updated_at=ANCHOR,
        )
    ]

    return {
        "runs": rows_runs,
        "channels": rows_channels,
        "channel_observations": rows_channel_obs,
        "videos": rows_videos,
        "video_observations": rows_video_obs,
        "recommendations": rows_edges,
        "comments": rows_comments,
        "comment_observations": rows_comment_obs,
        "datasets": rows_datasets,
        "projects": rows_projects,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="Scratch PostgreSQL database URL")
    ap.add_argument("--videos", type=int, default=800)
    ap.add_argument("--edges-per-video", type=int, default=12)
    ap.add_argument("--commenters", type=int, default=1500)
    ap.add_argument("--comments-per-video", type=int, default=20)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--manifest",
        help="Where to write the manifest JSON (default: <db>.manifest.json "
        "next to this script's cwd output dir)",
    )
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    print(f"Building synthetic corpus (seed={args.seed}) ...")
    t0 = datetime.now()
    corpus = build_corpus(
        videos=args.videos,
        edges_per_video=args.edges_per_video,
        commenters=args.commenters,
        comments_per_video=args.comments_per_video,
        runs=args.runs,
        rng=rng,
    )
    print(f"Corpus built in {(datetime.now() - t0).total_seconds():.1f}s")

    db = SqlDatabase(args.db)
    try:
        db.create_schema()
        table_keys = {
            "runs": ("collection_runs", "run_id"),
            "channels": ("channels", "channel_id"),
            "channel_observations": ("channel_observations", "observation_id"),
            "videos": ("videos", "video_id"),
            "video_observations": ("video_observations", "observation_id"),
            "recommendations": ("recommendations", "observation_id"),
            "comments": ("comments", "comment_id"),
            "comment_observations": ("comment_observations", "observation_id"),
            "datasets": ("datasets", "dataset_id"),
            "projects": ("projects", "project_id"),
        }
        for name, models in corpus.items():
            t = datetime.now()
            table, key = table_keys[name]
            n = _bulk_insert(db, table, key, models)
            print(f"  {table:<22} {n:>8} rows  ({(datetime.now() - t).total_seconds():.1f}s)")
    finally:
        db.close()

    manifest_path = Path(
        args.manifest
        or (Path("C:/Users/DELL/AppData/Local/Temp/opencode/ssr_stress") / "stress_manifest.json")
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "db": args.db,
        "seed": args.seed,
        "runs": [r.run_id for r in corpus["runs"]],
        "channels": [c.channel_id for c in corpus["channels"][:5]],
        "counts": {name: len(models) for name, models in corpus.items()},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nDone. Row counts:")
    total = 0
    for name, models in corpus.items():
        print(f"  {name:<22} {len(models):>8}")
        total += len(models)
    print(f"  {'TOTAL':<22} {total:>8}")
    print(f"\nManifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
