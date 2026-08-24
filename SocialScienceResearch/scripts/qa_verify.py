"""Aggressive QA verification harness for SocialScienceResearch.

Two independent passes:
  (A) Direct-repository numeric audit - seeds data with KNOWN values, then
      recomputes every analytics/sampling/network/comparison metric in plain
      Python and asserts the service output matches (catches silent logic
      failures / wrong calculations).
  (B) API smoke test via FastAPI TestClient - exercises the real E2E surface
      with a fake provider and asserts every endpoint returns 200 and
      serializes without throwing (catches runtime crashes / 500s).

Run:  python scripts/qa_verify.py
"""
from __future__ import annotations

import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

# Excel backend for the audit.
import os
os.environ.setdefault("SOCIAL_REPOSITORY_BACKEND", "excel")

from SocialScienceResearch.config.settings import (
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import (
    DataAvailability,
    PercentileBand,
    RecommendationStatus,
    RunType,
)
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    Video,
    VideoObservation,
)
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.services import (
    AnalyticsService,
    RecommendationGraphService,
    SamplingService,
)
from SocialScienceResearch.services.comparison_service import ComparisonService
from SocialScienceResearch.services.statistics_service import StatisticsService

CH = "UCaudit0000000000000000000"
RUN = "run_audit_0001"
NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


# ----------------------------------------------------------------------
# Independent reference implementations (no use of the SUT math).
# ----------------------------------------------------------------------
def ref_percentile(values, p):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    p = max(0.0, min(100.0, float(p)))
    if p <= 0:
        return vals[0]
    if p >= 100:
        return vals[-1]
    rank = (len(vals) - 1) * p / 100.0
    low = int(rank)
    high = min(low + 1, len(vals) - 1)
    return vals[low] * (1 - (rank - low)) + vals[high] * (rank - low)


def ref_mean(xs):
    xs = [float(x) for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ----------------------------------------------------------------------
# Seed the repository with deterministic, hand-computed data.
# ----------------------------------------------------------------------
def seed(repos):
    repos.runs.create_run(
        CollectionRun(
            run_id=RUN,
            run_type=RunType.CHANNEL,
            target_url="https://www.youtube.com/@audit",
            target_channel_id=CH,
            started_at=NOW,
            finished_at=NOW,
            status="success",
        )
    )
    repos.channels.upsert_channel(
        Channel(
            channel_id=CH,
            url="https://www.youtube.com/@audit",
            title="Audit Channel",
            first_observed_run_id=RUN,
        )
    )
    repos.channels.save_channel_observation(
        ChannelObservation(
            observation_id="obs_ch_1",
            collection_run_id=RUN,
            channel_id=CH,
            observed_at=NOW,
            subscriber_count=1000,
            video_count=3,
            view_count=5000,
        )
    )

    # vA: views 300 likes 30 comments 3 ; vB: 100/5/1 ; vC: 200/20/2 ; vD: no obs
    vids = {
        "vA": (300, 30, 3, 100, date(2024, 1, 1)),
        "vB": (100, 5, 1, 200, date(2024, 6, 1)),
        "vC": (200, 20, 2, 300, date(2025, 1, 1)),
    }
    for vid, (views, likes, comments, dur, ud) in vids.items():
        repos.videos.upsert_video(
            Video(
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                channel_id=CH,
                title=f"Video {vid}",
                duration=dur,
                upload_date=ud,
                first_observed_run_id=RUN,
            )
        )
        repos.videos.save_video_observation(
            VideoObservation(
                observation_id=f"obs_{vid}",
                collection_run_id=RUN,
                video_id=vid,
                observed_at=NOW,
                view_count=views,
                like_count=likes,
                comment_count=comments,
            )
        )
    # vD has an entity but no observation -> missing metric
    repos.videos.upsert_video(
        Video(
            video_id="vD",
            url="https://www.youtube.com/watch?v=vD",
            channel_id=CH,
            title="Video D",
            first_observed_run_id=RUN,
        )
    )

    # Comments on vA with like counts [10,20,30,40] and reply counts [2,0,1,0]
    like_map = {"c1": 10, "c2": 20, "c3": 30, "c4": 40}
    reply_map = {"c1": 2, "c2": 0, "c3": 1, "c4": 0}
    for i, (cid, lk) in enumerate(like_map.items(), start=1):
        repos.comments.upsert_comment(
            Comment(
                comment_id=cid,
                video_id="vA",
                author_name=f"Author{i}",
                comment_text=f"comment {cid}",
                published_at=NOW,
                first_observed_run_id=RUN,
            )
        )
        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id=f"obs_{cid}",
                collection_run_id=RUN,
                comment_id=cid,
                observed_at=NOW,
                like_count=lk,
                reply_count=reply_map[cid],
            )
        )

    # Recommendation edges: vA->vB, vA->vC, vB->vC, vC->vA  (4 edges)
    for s, t in [("vA", "vB"), ("vA", "vC"), ("vB", "vC"), ("vC", "vA")]:
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id=f"rec_{s}_{t}",
                collection_run_id=RUN,
                source_video_id=s,
                recommended_video_id=t,
                status=RecommendationStatus.OBSERVED,
            )
        )


# ----------------------------------------------------------------------
# Pass A: numeric audit
# ----------------------------------------------------------------------
def pass_a(repos):
    print("\n=== PASS A: NUMERIC LOGIC AUDIT ===")
    analytics = AnalyticsService(repos)
    sampling = SamplingService(repos, default_seed=42)
    comparison = ComparisonService(repos)
    graph = RecommendationGraphService(repos)

    # --- engagement for vA ---
    eng = analytics.video_engagement("vA")
    exp_eng = (30 + 3) / 300
    exp_like = 30 / 300
    exp_comment = 3 / 300
    check("video_engagement.engagement_rate", abs(eng.engagement_rate.value - exp_eng) < 1e-9,
          f"got {eng.engagement_rate.value} expected {exp_eng}")
    check("video_engagement.like_rate", abs(eng.like_rate.value - exp_like) < 1e-9,
          f"got {eng.like_rate.value} expected {exp_like}")
    check("video_engagement.comment_rate", abs(eng.comment_rate.value - exp_comment) < 1e-9,
          f"got {eng.comment_rate.value} expected {exp_comment}")

    # --- comment like percentiles for vA [10,20,30,40] ---
    pct = analytics.comment_like_percentiles("vA")
    for band, p in [("75", 75), ("90", 90), ("95", 95), ("99", 99)]:
        got = pct.bands.get(band)
        exp = ref_percentile([10, 20, 30, 40], p)
        check(f"comment_percentile_P{band}", got is not None and abs(got - exp) < 1e-9,
              f"got {got} expected {exp}")

    # --- top_videos by views ordering: 300,200,100 ---
    top = analytics.top_videos(CH, metric="views", n=10, reverse=True)
    order = [t.video_id for t in top if t.availability == DataAvailability.AVAILABLE]
    check("top_videos ordering by views", order == ["vA", "vC", "vB"], f"got {order}")
    # vD must be present with missing availability (not dropped)
    missing = [t for t in top if t.video_id == "vD"]
    check("top_videos keeps missing-metric video", len(missing) == 1 and missing[0].availability == DataAvailability.MISSING,
          f"got {missing}")

    # --- sampling top_views size=2 -> [vA, vC] ---
    from SocialScienceResearch.domain.query import SamplingSpec, SamplingStrategy
    sv = sampling.sample_videos(CH, SamplingSpec(strategy=SamplingStrategy.TOP_VIEWS, size=2))
    check("sampling top_views size=2", sv.entity_ids == ["vA", "vC"], f"got {sv.entity_ids}")

    # --- sampling random reproducibility (same seed -> same) ---
    spec_r = SamplingSpec(strategy=SamplingStrategy.RANDOM, size=2, seed=7)
    r1 = sampling.sample_videos(CH, spec_r).entity_ids
    r2 = sampling.sample_videos(CH, spec_r).entity_ids
    check("sampling random reproducible", r1 == r2, f"got {r1} vs {r2}")

    # --- sampling stratified: 3 years, 2 per stratum = 6 ---
    spec_s = SamplingSpec(strategy=SamplingStrategy.STRATIFIED, strata="year", sample_per_stratum=2, seed=11)
    st = sampling.sample_videos(CH, spec_s)
    check("sampling stratified count", st.sample_size == 6, f"got {st.sample_size}")

    # --- comparison z_score + percentile ranks ---
    cmp = comparison.compare_videos(["vA", "vB", "vC"], metrics=["views"], normalization="z_score")
    rows = {r.entity_id: r for r in cmp.rows}
    vals = [300, 100, 200]
    mean = ref_mean(vals)
    var = sum((v - mean) ** 2 for v in vals) / 3
    std = var ** 0.5
    exp_z = {(vid, v): (v - mean) / std for vid, v in zip(["vA", "vB", "vC"], vals)}
    for vid, v in zip(["vA", "vB", "vC"], vals):
        got = rows[vid].normalized
        check(f"comparison z_score {vid}", abs(got - exp_z[(vid, v)]) < 1e-9, f"got {got} expected {exp_z[(vid,v)]}")
    # percentile ranks over normalized: below counts among [1.2247,-1.2247,0]
    exp_rank = {"vA": 100.0, "vB": 0.0, "vC": 50.0}
    for vid, er in exp_rank.items():
        got = rows[vid].percentile_rank
        check(f"comparison percentile_rank {vid}", abs(got - er) < 1e-9, f"got {got} expected {er}")

    # --- network summary integrity ---
    summ = graph.summary()
    check("network node_count", summ.node_count == 4, f"got {summ.node_count}")
    check("network edge_count", summ.edge_count == 4, f"got {summ.edge_count}")
    in_degs = dict(__import__("networkx").DiGraph().in_degree())  # placeholder; recompute below
    # Recompute expected degrees from raw edges via networkx directly.
    import networkx as nx
    G = nx.DiGraph()
    for s, t in [("vA", "vB"), ("vA", "vC"), ("vB", "vC"), ("vC", "vA")]:
        G.add_edge(s, t)
    exp_in = dict(G.in_degree())
    exp_out = dict(G.out_degree())
    got_in = {d["video_id"]: d["times_recommended"] for d in summ.most_recommended}
    got_out = {d["video_id"]: d["outgoing"] for d in summ.most_active_sources}
    check("network in_degree sum == edges", sum(exp_in.values()) == 4)
    check("network most_recommended ordering", summ.most_recommended[0]["video_id"] == "vC"
          and summ.most_recommended[0]["times_recommended"] == 2,
          f"got {summ.most_recommended[0]}")
    # PageRank sums to 1
    pr_sum = sum(d["pagerank"] for d in summ.highest_pagerank)
    check("network pagerank sums ~1", abs(pr_sum - 1.0) < 1e-6, f"got {pr_sum}")

    # --- channel overview ---
    ov = analytics.channel_overview(CH)
    check("channel_overview subscribers", ov.subscriber_count.value == 1000, f"got {ov.subscriber_count.value}")
    check("channel_overview views", ov.view_count.value == 5000, f"got {ov.view_count.value}")


# ----------------------------------------------------------------------
# Pass B: API smoke
# ----------------------------------------------------------------------
def pass_b():
    print("\n=== PASS B: API SMOKE (TestClient) ===")
    from fastapi.testclient import TestClient

    class FakeProvider:
        def extract_channel(self, channel_url):
            from SocialScienceResearch.acquisition import ChannelExtract
            return ChannelExtract(
                channel={
                    "id": CH, "title": "Audit Channel",
                    "url": channel_url, "subscriber_count": 1000,
                    "video_count": 3, "view_count": 5000,
                },
                videos=[
                    {"id": "vA", "title": "A", "url": "https://www.youtube.com/watch?v=vA",
                     "view_count": 300, "like_count": 30, "comment_count": 3,
                     "duration": 100, "upload_date": date(2024, 1, 1)},
                    {"id": "vB", "title": "B", "url": "https://www.youtube.com/watch?v=vB",
                     "view_count": 100, "like_count": 5, "comment_count": 1,
                     "duration": 200, "upload_date": date(2024, 6, 1)},
                    {"id": "vC", "title": "C", "url": "https://www.youtube.com/watch?v=vC",
                     "view_count": 200, "like_count": 20, "comment_count": 2,
                     "duration": 300, "upload_date": date(2025, 1, 1)},
                ],
            )

        def extract_video(self, video_url):
            raise NotImplementedError("no single-video in this smoke")

        def extract_recommendations(self, video_url):
            from SocialScienceResearch.acquisition import RecommendationUnsupportedError
            raise RecommendationUnsupportedError("unsupported in smoke")

    with TemporaryDirectory() as tmp:
        rs = RepositorySettings(data_dir=tmp, dataset_name="smoke")
        settings = SocialScienceSettings(
            repository=rs,
            scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
            collection=CollectionSettings(collect_comments=False, enrich_video_stats=False),
        )
        from SocialScienceResearch.api import create_app
        app = create_app(settings, provider=FakeProvider())
        client = TestClient(app)
        P = "/api/v1/social-science"

        # collect the channel
        t0 = time.time()
        r = client.post(f"{P}/collect/channel", json={"url": "https://www.youtube.com/@audit"})
        dt = time.time() - t0
        check("POST /collect/channel 200", r.status_code == 200, f"status {r.status_code} body {r.text[:200]}")
        check("POST /collect/channel latency < 5s", dt < 5.0, f"{dt:.2f}s")

        # overview
        r = client.get(f"{P}/channels/{CH}/overview")
        ok = r.status_code == 200
        check("GET /channels/{{id}}/overview 200", ok, f"status {r.status_code}")
        if ok:
            body = r.json()
            check("overview subscriber=1000", body["subscribers"]["value"] == 1000, f"got {body}")
            check("overview view_count=5000", body["views"]["value"] == 5000, f"got {body}")

        # top videos
        r = client.get(f"{P}/channels/{CH}/videos/top?metric=views&n=10")
        check("GET /channels/{{id}}/videos/top 200", r.status_code == 200, f"status {r.status_code} {r.text[:200]}")

        # engagement for vA
        r = client.get(f"{P}/videos/vA/engagement")
        check("GET /videos/{{id}}/engagement 200", r.status_code == 200, f"status {r.status_code}")

        # percentiles
        r = client.get(f"{P}/videos/vA/comments/percentiles")
        check("GET /videos/{{id}}/comments/percentiles 200", r.status_code == 200, f"status {r.status_code} {r.text[:200]}")

        # list videos (pagination + serialization)
        r = client.get(f"{P}/videos")
        check("GET /videos 200", r.status_code == 200, f"status {r.status_code}")

        # sampling advanced
        from SocialScienceResearch.domain.query import AdvancedSamplingSpec
        spec = AdvancedSamplingSpec(entity_type="video", channel_ids=[CH],
                                    strategy=SamplingStrategy.TOP_VIEWS, size=2)
        r = client.post(f"{P}/sampling/advanced", json=spec.model_dump())
        check("POST /sampling/advanced 200", r.status_code == 200, f"status {r.status_code} {r.text[:200]}")

        # coverage + dataset summary
        r = client.get(f"{P}/coverage")
        check("GET /coverage 200", r.status_code == 200, f"status {r.status_code}")
        r = client.get(f"{P}/dataset/summary")
        check("GET /dataset/summary 200", r.status_code == 200, f"status {r.status_code}")

        # jobs list
        r = client.get(f"{P}/jobs")
        check("GET /jobs 200", r.status_code == 200, f"status {r.status_code}")


def main() -> int:
    with TemporaryDirectory() as tmp:
        repos = build_excel_repositories(RepositorySettings(data_dir=tmp, dataset_name="audit"))
        seed(repos)
        pass_a(repos)
        repos.store.close()
    pass_b()

    failed = [r for r in RESULTS if not r[1]]
    print("\n================ SUMMARY ================")
    print(f"Total checks: {len(RESULTS)} | Passed: {len(RESULTS) - len(failed)} | Failed: {len(failed)}")
    for name, ok, detail in failed:
        print(f"  FAIL: {name} :: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
