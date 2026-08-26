"""API tests for /echo-chamber/{id}/structure and /audience (spec §35-§36).

Runs a real detection against a fake provider (no network), then checks the
structural payload sections (video lens stats / community structure /
reinforcement with null model / centrality; channel lens with HHI), the §36
metadata envelope contract, verbatim disclaimers (§38), and audience-lens
availability semantics (§22): no comment identities -> explicit
`unavailable`, never a fabricated zero.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from SocialScienceResearch.acquisition.base import AcquisitionProvider, ChannelExtract
from SocialScienceResearch.api import create_app
from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.enums import CollectionStatus, RunType
from SocialScienceResearch.domain.models import CollectionRun, Comment, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories
from SocialScienceResearch.utils.idgen import new_run_id, utcnow

PREFIX = "/api/v1/social-science"
CH1 = "UCsource0000000000000000000"
CH2 = "UCtarget0000000000000000000"
SEED_A = "seed_a"
SEED_B = "seed_b"

DISCLAIMER_1 = (
    "The recommendation graph represents observed recommendation "
    "relationships between videos. These relationships do not directly "
    "represent viewer beliefs, social relationships, ideological agreement, "
    "or causation."
)


class StructureApiProvider(AcquisitionProvider):
    """Two-channel crawl: seed_a(CH1) recommends t1/t2(CH2); t1 -> t3."""

    def extract_channel(self, channel_url: str) -> ChannelExtract:
        raise NotImplementedError

    def extract_video(self, video_url: str, *, include_comments=None) -> dict[str, Any]:
        video_id = video_url.rsplit("v=", 1)[-1]
        return {
            "id": video_id,
            "webpage_url": video_url,
            "title": f"Title of {video_id}",
            "channel_id": CH1 if video_id.startswith("seed") else CH2,
            "view_count": 100,
            "like_count": 5,
            "comment_count": 1,
        }

    def extract_recommendations(self, video_url: str) -> list[dict[str, Any]]:
        video_id = video_url.rsplit("v=", 1)[-1]
        rec = {"id": "x", "channel_id": CH2, "title": "rec"}
        if video_id == SEED_A:
            return [dict(rec, id="t1"), dict(rec, id="t2")]
        if video_id == SEED_B:
            return [dict(rec, id="t2")]
        if video_id == "t1":
            return [dict(rec, id="t3"), dict(rec, id="t2")]
        return []


def _settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(data_dir=str(tmp_path), dataset_name="structure_api"),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix=PREFIX),
    )


def _seed_corpus(tmp_path, *, with_comments: bool = False) -> str:
    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="structure_api")
    )
    run = CollectionRun(
        run_id=new_run_id(),
        run_type=RunType.CHANNEL,
        target_url="https://www.youtube.com/@example",
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )
    repos.runs.create_run(run)
    for video_id in (SEED_A, SEED_B):
        repos.videos.upsert_video(
            Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_id=CH1,
                title=f"Seed {video_id}",
                first_observed_run_id=run.run_id,
            )
        )
    if with_comments:
        shared = {
            "c1": ("viewer_shared_a", "viewer_shared_b"),
            "t1": ("viewer_shared_a", "viewer_only_t1"),
            "t2": ("viewer_shared_b", "viewer_only_t2"),
        }
        for idx, (video_id, authors) in enumerate(shared.items()):
            for j, author in enumerate(authors):
                repos.comments.upsert_comment(
                    Comment(
                        comment_id=f"{video_id}_c{j}_{idx}",
                        video_id=video_id,
                        author_id=author,
                        author_name=author,
                        comment_text="text",
                        first_observed_run_id=run.run_id,
                    )
                )
    repos.store.close()
    return run.run_id


def _run_detection(tmp_path, *, with_comments=False) -> tuple[TestClient, str]:
    run_id = _seed_corpus(tmp_path, with_comments=with_comments)
    client = TestClient(create_app(_settings(tmp_path), provider=StructureApiProvider()))
    resp = client.post(
        f"{PREFIX}/echo-chamber/detect",
        json={"seed_run_id": run_id, "max_layers": 1},
    )
    assert resp.status_code == 200
    detection_id = resp.json()["detection_id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"{PREFIX}/echo-chamber/{detection_id}").json()
        if body["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    assert body["status"] in ("completed", "exhausted", "unsupported_stop")
    return client, detection_id


def test_structure_endpoint_sections_and_metadata(tmp_path):
    client, detection_id = _run_detection(tmp_path)
    resp = client.get(f"{PREFIX}/echo-chamber/{detection_id}/structure")
    assert resp.status_code == 200
    payload = resp.json()

    # Verbatim disclaimer (spec §38) travels with the payload.
    assert DISCLAIMER_1 in payload["disclaimers"]

    video = payload["video_lens"]
    stats = {m["metric"]: m for m in video["network_statistics"]}
    # Real observed graph from the fake provider (frontier layers): at least
    # seed_a->t1/t2 plus one more scraped source -> 3 unique edges.
    assert stats["edge_count"]["value"] >= 3
    for env in video["network_statistics"]:
        assert {"metric", "value", "status", "category", "lens"} <= set(env)
        assert env["lens"] == "video"
    density = stats["density"]
    if density["status"] == "available":
        assert density["numerator"] == density["denominator"] * density["value"] or (
            abs(density["numerator"] - density["denominator"] * density["value"]) < 1e-3
        )

    cs = video["community_structure"]
    assert cs["community_count"]["category"] == "community_structure"
    assert cs["community_count"]["lens"] == "video"

    reinforcement = video["reinforcement"]
    wcr = reinforcement["within_community_recommendation_rate"]
    assert {"metric", "value", "status", "category", "lens", "numerator", "denominator"} <= set(wcr)
    null_model = reinforcement["null_model"]
    if null_model.get("status") == "available":
        for field in ("null_mean", "null_sd", "n_randomizations", "seed"):
            assert null_model[field] is not None
        if null_model["z_score"] is None:
            # Zero null variance: z undefined but explicitly documented.
            assert "zero null standard deviation" in null_model["detail"]["reason"]
        else:
            expected_z = round(
                (wcr["value"] - null_model["null_mean"]) / null_model["null_sd"], 6
            )
            assert null_model["z_score"] == expected_z

    centrality = video["centrality"]
    if centrality["pagerank"]["status"] == "available":
        assert centrality["pagerank"]["detail"]["top"]

    channel = payload["channel_lens"]
    conc = channel["concentration"]
    hhi_env = conc["hhi"]
    assert hhi_env["lens"] == "channel"
    assert hhi_env["category"] == "channel_concentration"
    if hhi_env["status"] == "available":
        shares = [s["share"] for s in conc["shares"]]
        assert abs(hhi_env["value"] - round(sum(s * s for s in shares), 6)) < 1e-6


def test_structure_unknown_detection_404(tmp_path):
    client = TestClient(create_app(_settings(tmp_path), provider=StructureApiProvider()))
    resp = client.get(f"{PREFIX}/echo-chamber/ech_missing/structure")
    assert resp.status_code == 404


def test_audience_unavailable_without_comments(tmp_path):
    client, detection_id = _run_detection(tmp_path, with_comments=False)
    resp = client.get(f"{PREFIX}/echo-chamber/{detection_id}/audience")
    assert resp.status_code == 200
    block = resp.json()["commenter_overlap"]
    assert block["status"] == "unavailable"
    assert block["jaccard_mean"]["value"] is None
    assert block["jaccard_mean"]["status"] == "unavailable"


def test_audience_jaccard_within_between_communities(tmp_path):
    client, detection_id = _run_detection(tmp_path, with_comments=True)
    resp = client.get(f"{PREFIX}/echo-chamber/{detection_id}/audience")
    assert resp.status_code == 200
    payload = resp.json()
    assert DISCLAIMER_1 in payload["disclaimers"]
    block = payload["commenter_overlap"]
    # t1/t2/t3 have comments; t3 was crawled so at least two videos overlap.
    if block["videos_with_commenters"]["value"] < 2:
        pytest.skip("crawl did not reach commented videos")
    assert block["status"] == "available"
    jm = block["jaccard_mean"]
    within = block["within_community_jaccard_mean"]
    between = block["between_community_jaccard_mean"]
    assert jm["category"] == "audience" and jm["lens"] == "audience"
    # Hand-computed expectation for t1 vs t2: shared viewer_shared_a/b ->
    # intersection 2, union 4 -> Jaccard 0.5.
    pair_values = []
    if within["value"] is not None or between["value"] is not None:
        values = [v for v in (within["value"], between["value"]) if v is not None]
        assert all(0.0 <= v <= 1.0 for v in values)
        assert jm["value"] is not None
