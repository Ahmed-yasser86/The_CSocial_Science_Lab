"""Tests for the aggregated AuthorRepository projection (ADR-0010).

Exercises the read-side aggregation: one profile per author (id, with a name
fallback), comment counts, distinct videos, first/last seen ordering, run
attribution and the union of raw author metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from SocialScienceResearch.domain.models import Comment


def _comment(
    comment_id: str,
    author_id: str,
    author_name: str,
    video_id: str,
    published_at: str,
    run_id: str = "run_1",
    is_author: bool = False,
    raw_json: dict | None = None,
) -> Comment:
    return Comment(
        comment_id=comment_id,
        video_id=video_id,
        author_id=author_id,
        author_name=author_name,
        comment_text="body",
        published_at=datetime.fromisoformat(published_at).replace(tzinfo=timezone.utc),
        is_author=is_author,
        first_observed_run_id=run_id,
        raw_json=raw_json or {},
    )


@pytest.fixture
def authors_repo(tmp_path):
    """Author repository over a temporary workbook with a seeded corpus."""
    from SocialScienceResearch.config.settings import RepositorySettings
    from SocialScienceResearch.persistence.excel_repository import build_excel_repositories

    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="authors")
    )
    repos.comments.upsert_comment(
        _comment(
            "c_1", "author_a", "Alice", "v_1", "2026-01-01T10:00:00",
            run_id="run_1", raw_json={"author": "Alice", "author_is_verified": True},
        )
    )
    repos.comments.upsert_comment(
        _comment(
            "c_2", "author_a", "Alice", "v_2", "2026-01-03T09:00:00",
            run_id="run_2", is_author=True,
        )
    )
    repos.comments.upsert_comment(
        _comment(
            "c_3", "author_b", "Bob", "v_1", "2026-01-02T12:00:00",
            run_id="run_1", raw_json={"author": "Bob", "author_thumbnail": "x"},
        )
    )
    repos.comments.upsert_comment(
        _comment(
            "c_4", None, "NoIdAuthor", "v_3", "2026-01-04T08:00:00",
            run_id="run_1",
        )
    )
    repos.store.save()
    return repos.authors


def test_list_authors_groups_by_author_id(authors_repo) -> None:
    authors = authors_repo.list_authors()
    ids = [a.author_id for a in authors]
    assert sorted(ids) == ["NoIdAuthor", "author_a", "author_b"]


def test_aggregation_counts_and_videos(authors_repo) -> None:
    alice = authors_repo.get_author("author_a")
    assert alice is not None
    assert alice.author_name == "Alice"
    assert alice.comment_count == 2
    assert alice.video_ids == ["v_1", "v_2"]
    assert alice.is_author is True
    assert alice.first_seen_run_id == "run_1"
    assert alice.first_seen_at.date().isoformat() == "2026-01-01"
    assert alice.last_seen_at.date().isoformat() == "2026-01-03"


def test_name_fallback_groups_when_no_id(authors_repo) -> None:
    author = authors_repo.get_author("NoIdAuthor")
    assert author is not None
    assert author.author_name == "NoIdAuthor"
    assert author.comment_count == 1
    assert author.video_ids == ["v_3"]


def test_author_id_ordering(authors_repo) -> None:
    authors = authors_repo.list_authors()
    ids = [a.author_id for a in authors]
    assert ids == sorted(ids)


def test_raw_json_union_of_author_keys(authors_repo) -> None:
    alice = authors_repo.get_author("author_a")
    assert alice is not None
    assert alice.raw_json.get("author") == "Alice"
    assert alice.raw_json.get("author_is_verified") is True


def test_get_author_missing_returns_none(authors_repo) -> None:
    assert authors_repo.get_author("nobody") is None


def test_empty_corpus_lists_zero_authors(tmp_path) -> None:
    from SocialScienceResearch.config.settings import RepositorySettings
    from SocialScienceResearch.persistence.excel_repository import build_excel_repositories

    repos = build_excel_repositories(
        RepositorySettings(data_dir=str(tmp_path), dataset_name="empty")
    )
    repos.store.save()
    assert repos.authors.list_authors() == []
