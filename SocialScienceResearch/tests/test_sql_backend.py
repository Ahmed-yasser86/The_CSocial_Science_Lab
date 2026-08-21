"""SQL-backend tests: all repositories + services against a dedicated test DB.

These tests exercise the ``persistence/sql`` implementation end-to-end against
a *dedicated* test PostgreSQL database (``social_science_test`` by default) so
they never touch the live ``social_science`` database used by the running app.
Override the test database via ``SOCIAL_TEST_DATABASE_URL``.

Isolation: an autouse fixture truncates every entity table before each test,
so the suite is order-independent and safe to run repeatedly against the same
test database. The suite does NOT require any Excel files.
"""

from __future__ import annotations

import os

import pytest

from SocialScienceResearch.persistence.sql.database import SqlDatabase

TEST_DATABASE_URL = os.environ.get(
    "SOCIAL_TEST_DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/social_science_test",
)

from SocialScienceResearch.config.settings import (
    ApiSettings,
    CollectionSettings,
    RepositorySettings,
    ScraperSettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.dataset_models import Dataset, Project, ProjectItem
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    RunType,
    TranscriptStatus,
)
from SocialScienceResearch.domain.layer_models import LayerRun
from SocialScienceResearch.domain.models import (
    Channel,
    ChannelObservation,
    CollectionError,
    CollectionRun,
    Comment,
    CommentObservation,
    RecommendationObservation,
    TranscriptRecord,
    Video,
    VideoObservation,
)
from SocialScienceResearch.domain.sample_models import Sample
from SocialScienceResearch.persistence.sql.repositories import build_sql_repositories
from SocialScienceResearch.services.dataset_service import DatasetService
from SocialScienceResearch.services.project_item_service import ProjectItemService
from SocialScienceResearch.services.project_service import ProjectService
from SocialScienceResearch.services.sample_service import SampleService
from SocialScienceResearch.utils.idgen import utcnow

_ALL_TABLES = [
    "channels",
    "channel_observations",
    "videos",
    "video_observations",
    "comments",
    "comment_observations",
    "collection_runs",
    "collection_errors",
    "recommendations",
    "transcripts",
    "datasets",
    "dataset_members",
    "projects",
    "project_items",
    "samples",
    "layer_runs",
]


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    db = SqlDatabase(TEST_DATABASE_URL)
    try:
        db.create_schema()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_db():
    db = SqlDatabase(TEST_DATABASE_URL)
    try:
        for table in _ALL_TABLES:
            db.execute(f'TRUNCATE TABLE "{table}" CASCADE')
    finally:
        db.close()
    yield


@pytest.fixture
def repos():
    """Real SQL repositories against the dedicated test PostgreSQL database."""
    repos = build_sql_repositories(TEST_DATABASE_URL)
    try:
        yield repos
    finally:
        repos.close()


@pytest.fixture
def settings(tmp_path) -> SocialScienceSettings:
    return SocialScienceSettings(
        repository=RepositorySettings(
            data_dir=str(tmp_path),
            dataset_name="sql_test",
            backend="sql",
            database_url=TEST_DATABASE_URL,
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
        collection=CollectionSettings(collect_comments=False),
        api=ApiSettings(prefix="/api/v1/social-science"),
    )


@pytest.fixture
def run() -> CollectionRun:
    return CollectionRun(
        run_id="run_sql_001",
        run_type=RunType.CHANNEL,
        target_url="https://www.youtube.com/@sql",
        target_channel_id="UCsql0000000000000000000",
        started_at=utcnow(),
        status=CollectionStatus.SUCCESS,
    )


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class TestChannelRepository:
    def test_upsert_created_flag_and_roundtrip(self, repos, run):
        repos.runs.create_run(run)
        ch = Channel(
            channel_id="UCsql0000000000000000000",
            url="https://www.youtube.com/channel/UCsql0000000000000000000",
            title="SQL Channel",
            handle="@sql",
            raw_json={"name": "raw channel", "stats": {"videos": 3}},
            first_observed_run_id="run_sql_001",
        )
        result = repos.channels.upsert_channel(ch)
        assert result.created is True
        assert result.entity_type.value == "channel"

        again = repos.channels.upsert_channel(ch)
        assert again.created is False

        stored = repos.channels.get_channel(ch.channel_id)
        assert stored is not None
        assert stored.title == "SQL Channel"
        assert stored.raw_json == {"name": "raw channel", "stats": {"videos": 3}}

    def test_list_channels(self, repos, run):
        repos.runs.create_run(run)
        for i in range(3):
            repos.channels.upsert_channel(
                Channel(
                    channel_id=f"UCsql{i}",
                    url=f"https://www.youtube.com/channel/UCsql{i}",
                    title=f"Channel {i}",
                    first_observed_run_id="run_sql_001",
                )
            )
        assert len(repos.channels.list_channels()) == 3

    def test_observations_latest_batch(self, repos, run):
        repos.runs.create_run(run)
        cid = "UCsql0000000000000000000"
        repos.channels.upsert_channel(
            Channel(channel_id=cid, url="https://y/u", first_observed_run_id="run_sql_001")
        )
        t1, t2, t3 = utcnow(), utcnow(), utcnow()
        repos.channels.save_channel_observation(
            ChannelObservation(
                observation_id="obs1", collection_run_id="run_sql_001",
                channel_id=cid, observed_at=t1, subscriber_count=100,
            )
        )
        repos.channels.save_channel_observation(
            ChannelObservation(
                observation_id="obs2", collection_run_id="run_sql_001",
                channel_id=cid, observed_at=t2, subscriber_count=200,
            )
        )
        repos.channels.save_channel_observation(
            ChannelObservation(
                observation_id="obs3", collection_run_id="run_sql_001",
                channel_id=cid, observed_at=t3, subscriber_count=300,
            )
        )
        assert len(repos.channels.list_channel_observations(cid)) == 3
        latest_single = repos.channels.get_latest_channel_observation(cid)
        assert latest_single is not None
        assert latest_single.subscriber_count == 300
        latest_batch = repos.channels.get_latest_channel_observations([cid])
        assert latest_batch[cid].subscriber_count == 300
        assert latest_batch[cid].observation_id == "obs3"
        assert "UCother" not in latest_batch


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

class TestVideoRepository:
    def _seed(self, repos, run):
        repos.runs.create_run(run)
        repos.channels.upsert_channel(
            Channel(
                channel_id="UCsql0000000000000000000",
                url="https://y/u",
                first_observed_run_id="run_sql_001",
            )
        )
        vids = []
        for i in range(2):
            vid = f"v_sql_{i}"
            vids.append(vid)
            repos.videos.upsert_video(
                Video(
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    channel_id="UCsql0000000000000000000",
                    title=f"Video {i}",
                    tags=["a", "b"],
                    categories=["News"],
                    chapters_json=[{"title": "intro", "start": 0}],
                    raw_json={"title": f"raw {i}"},
                    first_observed_run_id="run_sql_001",
                )
            )
        return vids

    def test_video_upsert_get_list(self, repos, run):
        self._seed(repos, run)
        video = repos.videos.get_video("v_sql_0")
        assert video is not None
        assert video.tags == ["a", "b"]
        assert video.categories == ["News"]
        assert video.chapters_json == [{"title": "intro", "start": 0}]
        assert video.raw_json == {"title": "raw 0"}
        assert len(repos.videos.list_videos()) == 2
        assert len(repos.videos.list_videos(channel_id="UCsql0000000000000000000")) == 2
        assert len(repos.videos.list_videos_by_run("run_sql_001")) == 2

    def test_video_recommendations_scraped_flag(self, repos, run):
        self._seed(repos, run)
        vid = "v_sql_0"
        assert repos.videos.get_video(vid).recommendations_scraped is False
        repos.videos.mark_recommendations_scraped(vid)
        assert repos.videos.get_video(vid).recommendations_scraped is True
        repos.videos.mark_recommendations_scraped("v_missing")  # no-op, no crash

    def test_video_observations_latest(self, repos, run):
        self._seed(repos, run)
        vid = "v_sql_0"
        for i, views in enumerate([10, 20, 30]):
            repos.videos.save_video_observation(
                VideoObservation(
                    observation_id=f"vo_{i}", collection_run_id="run_sql_001",
                    video_id=vid, observed_at=utcnow(), view_count=views,
                )
            )
        assert len(repos.videos.list_video_observations(vid)) == 3
        assert repos.videos.get_latest_video_observation(vid).view_count == 30
        batch = repos.videos.get_latest_video_observations([vid])
        assert batch[vid].observation_id == "vo_2"
        assert repos.videos.get_latest_video_observations(["v_missing"]) == {}


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class TestCommentRepository:
    def _seed(self, repos, run):
        repos.runs.create_run(run)
        repos.videos.upsert_video(
            Video(video_id="v_c", url="https://y/v_c", first_observed_run_id="run_sql_001")
        )
        repos.comments.upsert_comment(
            Comment(
                comment_id="c_root", video_id="v_c", author_name="Alice",
                author_id="auth_a", comment_text="root comment",
                raw_json={"author": "alice"}, first_observed_run_id="run_sql_001",
            )
        )
        repos.comments.upsert_comment(
            Comment(
                comment_id="c_reply", video_id="v_c", author_name="Bob",
                author_id="auth_b", comment_text="reply", is_reply=True,
                parent_comment_id="c_root", root_comment_id="c_root",
                first_observed_run_id="run_sql_001",
            )
        )

    def test_comment_tree(self, repos, run):
        self._seed(repos, run)
        assert repos.comments.get_comment("c_root").comment_text == "root comment"
        assert len(repos.comments.list_comments()) == 2
        assert len(repos.comments.list_comments(video_id="v_c")) == 2
        roots = repos.comments.list_root_comments("v_c")
        assert [c.comment_id for c in roots] == ["c_root"]
        assert [c.comment_id for c in repos.comments.list_replies("c_root")] == ["c_reply"]
        replies_by = repos.comments.list_replies_by_ids(["c_root", "c_other"])
        assert [c.comment_id for c in replies_by["c_root"]] == ["c_reply"]
        assert replies_by["c_other"] == []

    def test_comment_observations(self, repos, run):
        self._seed(repos, run)
        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id="co1", collection_run_id="run_sql_001",
                comment_id="c_root", observed_at=utcnow(), like_count=5,
            )
        )
        repos.comments.save_comment_observation(
            CommentObservation(
                observation_id="co2", collection_run_id="run_sql_001",
                comment_id="c_root", observed_at=utcnow(), like_count=9,
            )
        )
        assert len(repos.comments.list_comment_observations()) == 2
        assert len(repos.comments.list_comment_observations(comment_id="c_root")) == 2
        assert len(repos.comments.list_comment_observations(video_id="v_c")) == 2
        latest = repos.comments.get_latest_comment_observations(["c_root"])
        assert latest["c_root"].like_count == 9


# ---------------------------------------------------------------------------
# Collection runs + errors
# ---------------------------------------------------------------------------

class TestCollectionRunRepository:
    def test_run_lifecycle(self, repos, run):
        repos.runs.create_run(run)
        assert repos.runs.get_run("run_sql_001").status == CollectionStatus.SUCCESS
        assert [r.run_id for r in repos.runs.list_runs()] == ["run_sql_001"]
        assert len(repos.runs.list_runs(run_type=RunType.CHANNEL)) == 1
        assert len(repos.runs.list_runs(run_type=RunType.VIDEO)) == 0

        run.status = CollectionStatus.FAILED
        repos.runs.update_run(run)
        assert repos.runs.get_run("run_sql_001").status == CollectionStatus.FAILED

    def test_errors(self, repos, run):
        repos.runs.create_run(run)
        repos.runs.record_error(
            CollectionError(
                error_id="err1", run_id="run_sql_001",
                entity_type="video", entity_id="v_x",
                error_type="network", message="boom",
                occurred_at=utcnow(), retryable=True,
                details={"status": 500},
            )
        )
        errors = repos.runs.list_errors("run_sql_001")
        assert len(errors) == 1
        assert errors[0].message == "boom"
        assert errors[0].details == {"status": 500}
        assert errors[0].retryable is True


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendationRepository:
    def test_save_and_edges(self, repos, run):
        run2 = run.model_copy(update={"run_id": "run_sql_002"})
        repos.runs.create_run(run)
        repos.runs.create_run(run2)
        for vid in ("v_src_1", "v_src_2"):
            repos.videos.upsert_video(
                Video(video_id=vid, url=f"https://y/{vid}", first_observed_run_id="run_sql_001")
            )
        r1 = repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id="rec1", collection_run_id="run_sql_001",
                source_video_id="v_src_1", recommended_video_id="v_dst_1",
                position=1, status="observed", raw_json={"from": "src"},
            )
        )
        assert r1.created is True
        r1b = repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id="rec1", collection_run_id="run_sql_001",
                source_video_id="v_src_1", recommended_video_id="v_dst_1",
                position=1, status="observed", raw_json={"from": "src"},
            )
        )
        assert r1b.created is False
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id="rec2", collection_run_id="run_sql_002",
                source_video_id="v_src_1", recommended_video_id="v_dst_2",
                position=0, status="observed",
            )
        )
        repos.recommendations.save_recommendation(
            RecommendationObservation(
                observation_id="rec3", collection_run_id="run_sql_001",
                source_video_id="v_src_2", recommended_video_id="v_dst_3",
                position=2, status="observed",
            )
        )
        edges = repos.recommendations.list_recommendation_edges()
        assert len(edges) == 3
        assert len(repos.recommendations.list_recommendation_edges(source_video_id="v_src_1")) == 2
        assert len(repos.recommendations.list_recommendation_edges(run_id="run_sql_001")) == 2
        assert len(repos.recommendations.list_recommendations_for_source("v_src_1", run_id="run_sql_002")) == 1
        assert repos.recommendations.list_source_video_ids() == ["v_src_1", "v_src_2"]
        assert edges[0].raw_json == {"from": "src"}


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

class TestTranscriptRepository:
    def test_transcript_lifecycle(self, repos, run, tmp_path):
        repos.runs.create_run(run)
        repos.videos.upsert_video(
            Video(video_id="v_t", url="https://y/v_t", first_observed_run_id="run_sql_001")
        )
        t1, t2 = utcnow(), utcnow()
        repos.transcripts.save_transcript(
            TranscriptRecord(
                transcript_id="tr1", video_id="v_t", collection_run_id="run_sql_001",
                status=TranscriptStatus.MISSING, message="no captions",
                observed_at=t1,
            )
        )
        repos.transcripts.save_transcript(
            TranscriptRecord(
                transcript_id="tr2", video_id="v_t", collection_run_id="run_sql_001",
                path="v_t.txt", status=TranscriptStatus.AVAILABLE, observed_at=t2,
            )
        )
        latest = repos.transcripts.get_transcript("v_t")
        assert latest is not None
        assert latest.status == TranscriptStatus.AVAILABLE
        assert latest.path == "v_t.txt"
        assert [r.transcript_id for r in repos.transcripts.list_transcripts("v_t")] == ["tr1", "tr2"]
        assert len(repos.transcripts.list_transcripts()) == 2


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

class TestDatasetRepository:
    def test_dataset_crud_and_members(self, repos, run):
        repos.runs.create_run(run)
        d = Dataset(
            dataset_id="dst_sql", name="SQL Dataset", entity_type="video",
            created_at=utcnow(), source_projection={"entity": "video"},
            member_count=2,
        )
        repos.datasets.upsert_dataset(d)
        assert repos.datasets.get_dataset("dst_sql").name == "SQL Dataset"
        assert len(repos.datasets.list_datasets()) == 1

        members = [{"video_id": f"m{i}"} for i in range(5000)]
        chunks = repos.datasets.save_members("dst_sql", members)
        assert chunks == 1
        assert repos.datasets.dataset_member_count("dst_sql") == 5000
        stored = repos.datasets.list_members("dst_sql")
        assert len(stored) == 5000
        assert {m["video_id"] for m in stored} == {f"m{i}" for i in range(5000)}

        repos.datasets.delete_dataset("dst_sql")
        assert repos.datasets.get_dataset("dst_sql") is None
        assert repos.datasets.dataset_member_count("dst_sql") == 0


# ---------------------------------------------------------------------------
# Projects + project items
# ---------------------------------------------------------------------------

class TestProjectRepository:
    def test_project_crud(self, repos, run):
        repos.runs.create_run(run)
        p = Project(
            project_id="p_sql", name="Project", config_hash="hash1",
            targets=[{"kind": "channel", "url": "https://y/@x"}],
            collection_spec={"collect_comments": True},
            sampling_specs=[{"strategy": "random"}],
            research_query={"entity": "video"},
            variable_selection=["video_id", "view_count"],
            created_at=utcnow(), updated_at=utcnow(),
        )
        repos.projects.save_project(p)
        assert repos.projects.get_project("p_sql").name == "Project"
        assert repos.projects.get_project("p_sql").targets == [{"kind": "channel", "url": "https://y/@x"}]
        assert len(repos.projects.list_projects()) == 1
        repos.projects.update_project(p)
        repos.projects.delete_project("p_sql")
        assert repos.projects.get_project("p_sql") is None


class TestProjectItemRepository:
    def test_item_crud(self, repos, run):
        repos.runs.create_run(run)
        repos.projects.save_project(
            Project(project_id="p_i", name="P", config_hash="h",
                    created_at=utcnow(), updated_at=utcnow())
        )
        item = ProjectItem(
            item_id="item_sql", project_id="p_i", name="Item",
            item_type="mixed", sample_ids=["s1"], dataset_ids=["d1"],
            tags=["a"], created_at=utcnow(), updated_at=utcnow(),
        )
        repos.project_items.save_item(item)
        assert repos.project_items.get_item("item_sql").name == "Item"
        assert repos.project_items.get_item("item_sql").sample_ids == ["s1"]
        assert len(repos.project_items.list_items()) == 1
        assert len(repos.project_items.list_items_by_project("p_i")) == 1
        item.tags = ["b"]
        repos.project_items.update_item(item)
        assert repos.project_items.get_item("item_sql").tags == ["b"]
        repos.project_items.delete_item("item_sql")
        assert repos.project_items.get_item("item_sql") is None


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------

class TestSampleRepository:
    def test_sample_crud_and_members(self, repos, run):
        repos.runs.create_run(run)
        sample = Sample(
            sample_id="s_sql", entity_type="video", strategy="random",
            population_query_hash="q", population_size=1000, sample_size=3,
            seed=42, criteria_json={"views": ">100"},
            member_ids=["v1", "v2", "v3"], scope={"channel_ids": ["c1"]},
            labels={"system": {"created_by": "test"}},
            created_by_run_id="run_sql_001",
        )
        stored = repos.samples.save(sample)
        assert stored.overflow is False
        assert repos.samples.get("s_sql").sample_id == "s_sql"
        assert repos.samples.get("s_sql").member_ids == ["v1", "v2", "v3"]
        assert repos.samples.get("s_sql").criteria_json == {"views": ">100"}
        assert repos.samples.list_members("s_sql") == ["v1", "v2", "v3"]
        assert len(repos.samples.list()) == 1
        assert repos.samples.delete("s_sql") is True
        assert repos.samples.get("s_sql") is None
        assert repos.samples.delete("s_sql") is False


# ---------------------------------------------------------------------------
# Layer runs
# ---------------------------------------------------------------------------

class TestLayerRunRepository:
    def test_layer_run_crud(self, repos, run):
        repos.runs.create_run(run)
        layer = LayerRun(
            layer_run_id="lyr_0", layer_index=0, projection="video",
            started_at=utcnow(), status=CollectionStatus.SUCCESS,
            frontier_video_ids=["v1"], discovered_video_ids=["v2"],
            run_ids=["run_sql_001"], summary={"new_videos": 1},
        )
        repos.layers.save_layer_run(layer)
        assert repos.layers.get_layer_run("lyr_0").summary == {"new_videos": 1}
        assert repos.layers.get_layer_run("lyr_0").frontier_video_ids == ["v1"]
        assert len(repos.layers.list_layer_runs()) == 1
        assert repos.layers.list_layer_runs()[0].layer_index == 0


# ---------------------------------------------------------------------------
# Author projection
# ---------------------------------------------------------------------------

class TestAuthorRepository:
    def test_author_projection(self, repos, run):
        repos.runs.create_run(run)
        repos.videos.upsert_video(
            Video(video_id="v_a", url="https://y/v_a", first_observed_run_id="run_sql_001")
        )
        repos.comments.upsert_comment(
            Comment(
                comment_id="c_a1", video_id="v_a", author_id="auth_x",
                author_name="Alice", comment_text="first",
                raw_json={"author": "Alice", "author_is_verified": True},
                first_observed_run_id="run_sql_001",
            )
        )
        repos.comments.upsert_comment(
            Comment(
                comment_id="c_a2", video_id="v_a", author_id="auth_x",
                author_name="Alice", comment_text="second", is_author=True,
                first_observed_run_id="run_sql_001",
            )
        )
        repos.comments.upsert_comment(
            Comment(
                comment_id="c_a3", video_id="v_a", author_name="Bob",
                comment_text="no id", first_observed_run_id="run_sql_001",
            )
        )
        authors = repos.authors.list_authors()
        by_id = {a.author_id: a for a in authors}
        assert "auth_x" in by_id
        assert by_id["auth_x"].comment_count == 2
        assert by_id["auth_x"].is_author is True
        assert by_id["auth_x"].video_ids == ["v_a"]
        assert by_id["auth_x"].raw_json.get("author_is_verified") is True
        assert "Bob" in by_id
        profile = repos.authors.get_author("auth_x")
        assert profile is not None
        assert profile.author_name == "Alice"


# ---------------------------------------------------------------------------
# Services against the SQL backend
# ---------------------------------------------------------------------------

class TestSampleServiceSql:
    def test_save_get_delete(self, repos, run):
        repos.runs.create_run(run)
        service = SampleService(repos)
        saved = service.save(
            Sample(
                sample_id="", entity_type="video", strategy="random", seed=1,
                population_size=10, sample_size=2,
                population_query_hash="h", member_ids=["v1", "v2"],
            )
        )
        assert saved.sample_id
        assert saved.sample_size == 2
        assert service.get_sample(saved.sample_id).sample_id == saved.sample_id
        assert service.list_members(saved.sample_id) == ["v1", "v2"]
        assert service.delete_sample(saved.sample_id) is True
        assert service.get_sample(saved.sample_id) is None


class TestProjectServiceSql:
    def test_create_and_hash(self, repos, run):
        repos.runs.create_run(run)
        service = ProjectService(repos)
        p = Project(
            project_id="p_svc", name="SVC", config_hash="",
            targets=[{"kind": "video", "url": "https://y/x"}],
            created_at=utcnow(), updated_at=utcnow(),
        )
        service.create(p)
        assert p.config_hash  # stamped by service
        fetched = service.get_project("p_svc")
        assert fetched.config_hash == p.config_hash
        assert len(service.list_projects()) == 1
        service.delete_project("p_svc")
        with pytest.raises(ValueError):
            service.get_project("p_svc")


class TestProjectItemServiceSql:
    def test_item_flow(self, repos, run):
        repos.runs.create_run(run)
        service = ProjectItemService(repos)
        from SocialScienceResearch.domain.dataset_models import CreateProjectItemRequest
        repos.projects.save_project(
            Project(project_id="p_svc_i", name="P", config_hash="h",
                    created_at=utcnow(), updated_at=utcnow())
        )
        item = service.create_item(
            "p_svc_i",
            CreateProjectItemRequest(name="Item", item_type="sample_group", sample_ids=["s1"]),
        )
        assert service.get_item(item.item_id).name == "Item"
        assert len(service.list_items("p_svc_i")) == 1
        service.add_samples(item.item_id, ["s2"])
        assert set(service.get_item(item.item_id).sample_ids) == {"s1", "s2"}
        service.delete_item(item.item_id)
        with pytest.raises(ValueError):
            service.get_item(item.item_id)


class TestDatasetServiceSql:
    def test_create_dataset_and_members(self, repos, run, settings):
        repos.runs.create_run(run)
        repos.channels.upsert_channel(
            Channel(
                channel_id="UCsqlsvc", url="https://y/u",
                first_observed_run_id="run_sql_001",
            )
        )
        for i in range(3):
            repos.videos.upsert_video(
                Video(video_id=f"vs{i}", url=f"https://y/vs{i}",
                      channel_id="UCsqlsvc", first_observed_run_id="run_sql_001")
            )
            repos.videos.save_video_observation(
                VideoObservation(
                    observation_id=f"obs_vs{i}", collection_run_id="run_sql_001",
                    video_id=f"vs{i}", observed_at=utcnow(), view_count=(i + 1) * 100,
                )
            )
        service = DatasetService(repos, settings)
        dataset = service.create_dataset("SQL dataset", entity_type="video")
        assert dataset.member_count == 3
        assert dataset.overflow is False
        members = service.members(dataset.dataset_id)
        assert len(members) == 3
        assert service.member_count(dataset.dataset_id) == 3
        report = service.quality(dataset.dataset_id)
        assert report.dataset_id == dataset.dataset_id
        assert service.get_dataset(dataset.dataset_id).dataset_id == dataset.dataset_id
        service.delete_dataset(dataset.dataset_id)
        with pytest.raises(ValueError):
            service.get_dataset(dataset.dataset_id)


# ---------------------------------------------------------------------------
# API wiring against the SQL backend
# ---------------------------------------------------------------------------

class TestApiSql:
    def test_health_and_repos_backend(self, settings):
        from fastapi.testclient import TestClient
        from SocialScienceResearch.api import create_app

        app = create_app(settings=settings)
        with TestClient(app) as client:
            resp = client.get(f"{settings.api.prefix}/channels")
            assert resp.status_code == 200
            assert resp.json()["items"] == []
            assert resp.json()["total"] == 0

    def test_collect_and_query_flow(self, repos, settings):
        from fastapi.testclient import TestClient
        from SocialScienceResearch.api import create_app

        # seed data directly, then confirm the API reads it through SQL
        run = CollectionRun(
            run_id="run_api", run_type=RunType.CHANNEL,
            target_url="https://www.youtube.com/@api", started_at=utcnow(),
            status=CollectionStatus.SUCCESS,
        )
        repos.runs.create_run(run)
        repos.videos.upsert_video(
            Video(video_id="v_api", url="https://y/v_api",
                  first_observed_run_id="run_api")
        )
        repos.close()

        app = create_app(settings=settings)
        with TestClient(app) as client:
            resp = client.get(f"{settings.api.prefix}/runs")
            assert resp.status_code == 200
            run_ids = [r["run_id"] for r in resp.json()["items"]]
            assert "run_api" in run_ids
            resp = client.get(f"{settings.api.prefix}/videos/v_api")
            assert resp.status_code == 200
            assert resp.json()["video_id"] == "v_api"
