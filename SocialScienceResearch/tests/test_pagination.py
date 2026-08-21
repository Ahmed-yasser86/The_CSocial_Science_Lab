"""Tests for the opaque cursor pagination module."""

from __future__ import annotations

import pytest

from SocialScienceResearch.services.pagination import (
    CursorError,
    Paginated,
    decode_cursor,
    encode_cursor,
    page_sorted,
)


# ----------------------------------------------------------------------
# Cursor codec
# ----------------------------------------------------------------------
def test_encode_decode_round_trip() -> None:
    keys = ("2026-08-10T12:00:00+00:00", "dst_legacy", "obs_1")
    token = encode_cursor(keys)
    assert isinstance(token, str) and token != ""
    assert decode_cursor(token, n_keys=3) == keys


def test_decode_single_key_round_trip() -> None:
    token = encode_cursor(("api_v1",))
    assert decode_cursor(token, n_keys=1) == ("api_v1",)


def test_decode_empty_token_raises() -> None:
    with pytest.raises(CursorError):
        decode_cursor("", n_keys=1)


def test_decode_malformed_token_raises() -> None:
    with pytest.raises(CursorError):
        decode_cursor("!!!not-base64!!!", n_keys=1)


def test_decode_wrong_arity_raises() -> None:
    token = encode_cursor(("a", "b"))
    with pytest.raises(CursorError):
        decode_cursor(token, n_keys=1)
    with pytest.raises(CursorError):
        decode_cursor(token, n_keys=3)


def test_decode_garbage_json_raises() -> None:
    import base64

    token = base64.urlsafe_b64encode(b"not json at all").decode("ascii")
    with pytest.raises(CursorError):
        decode_cursor(token, n_keys=2)


# ----------------------------------------------------------------------
# page_sorted
# ----------------------------------------------------------------------
def _items(n: int) -> list[str]:
    return [f"id_{i:03d}" for i in range(n)]


def _key(item: str) -> tuple[str, ...]:
    return (item,)


def test_first_page_no_more() -> None:
    page = page_sorted(
        _items(3), cursor=None, page_size=10, key_func=_key, total=None
    )
    assert [item for item in page.items] == _items(3)
    assert page.next_cursor is None
    assert page.has_more is False
    assert page.total == 3  # in-memory list -> total computed


def test_walking_all_pages_collects_everything_once() -> None:
    items = _items(10)
    collected: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        page = page_sorted(
            items, cursor=cursor, page_size=3, key_func=_key, total=len(items)
        )
        collected.extend(page.items)
        pages += 1
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert collected == items
    assert pages == 4  # 10 items / 3 per page -> 4 pages


def test_has_more_reflects_remaining() -> None:
    first = page_sorted(_items(7), cursor=None, page_size=3, key_func=_key)
    assert first.has_more is True
    assert first.next_cursor is not None
    assert len(first.items) == 3
    last = page_sorted(
        _items(7), cursor=first.next_cursor, page_size=3, key_func=_key
    )
    assert len(last.items) == 3


def test_total_none_is_preserved() -> None:
    page = page_sorted(_items(3), cursor=None, page_size=2, key_func=_key, total=None)
    assert page.total == 3  # none given -> falls back to in-memory length


def test_empty_list() -> None:
    page = page_sorted([], cursor=None, page_size=10, key_func=_key, total=None)
    assert page.items == []
    assert page.next_cursor is None
    assert page.has_more is False
    assert page.total == 0


def test_stable_tiebreak_by_primary_key() -> None:
    """Rows sharing a sort key still page uniquely thanks to the pk suffix."""
    rows = [("same", f"pk_{i}") for i in range(5)]

    def key(row) -> tuple[str, ...]:
        return row

    collected = []
    cursor = None
    while True:
        page = page_sorted(rows, cursor=cursor, page_size=2, key_func=key, total=None)
        collected.extend(page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert collected == rows


def test_paginated_is_serializable_pydantic() -> None:
    page = Paginated(items=["a", "b"], next_cursor="tok", has_more=True, total=2)
    assert page.model_dump() == {
        "items": ["a", "b"],
        "next_cursor": "tok",
        "has_more": True,
        "total": 2,
    }