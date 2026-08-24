"""Opaque cursor-based pagination for the read API.

List endpoints never expose raw offsets - they return an opaque ``cursor``
token that encodes the *last item's* sort-key tuple. Clients pass the token
back verbatim to fetch the next page; the server decodes it and resumes the
walk. Because a cursor always ends with the entity's primary key, tokens are
stable and unique even when sort keys collide.

Encoding
--------
``encode_cursor((k1, k2, ..., pk))`` serializes the keys as a JSON array of
strings (URL-safe base64). ``decode_cursor(token, n_keys)`` reverses it and
raises :class:`CursorError` for malformed, empty or wrong-arity tokens.

Sorting contract
----------------
Callers hand :func:`page_sorted` a list already sorted ascending by
``key_func(item)``, where ``key_func`` returns the *same* tuple of string
values that was (or will be) encoded into the cursor. The binary search
compares item keys to the decoded cursor keys directly.

``total`` semantics: supplied when the full list is already materialized in
memory (research scale - the Excel repositories return lists); pass ``None``
when computing the total would be expensive.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Callable, Generic, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

#: Maximum number of keys a cursor may carry (sort keys + primary key).
_MAX_CURSOR_KEYS = 8


class CursorError(Exception):
    """Raised when a cursor token is missing, malformed or wrong-arity."""


def encode_cursor(keys: tuple[Any, ...]) -> str:
    """Encode a sort-key tuple into an opaque, URL-safe cursor string."""
    payload = json.dumps([str(k) for k in keys], ensure_ascii=False)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(token: str, n_keys: int) -> tuple[str, ...]:
    """Decode an opaque cursor back into its string key tuple.

    Raises :class:`CursorError` for empty/malformed tokens and for tokens that
    do not carry exactly ``n_keys`` keys.
    """
    if not token:
        raise CursorError("cursor token is empty")
    if n_keys < 1 or n_keys > _MAX_CURSOR_KEYS:
        raise CursorError(f"expected between 1 and {_MAX_CURSOR_KEYS} cursor keys, got {n_keys}")
    try:
        payload = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        values = json.loads(payload)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise CursorError(f"invalid cursor token") from exc
    if not isinstance(values, list) or len(values) != n_keys:
        raise CursorError(
            f"cursor token carries {len(values) if isinstance(values, list) else 'unknown'} "
            f"keys; expected {n_keys}"
        )
    return tuple(str(v) for v in values)


class Paginated(BaseModel, Generic[T]):
    """Uniform paginated response envelope.

    ``total`` is best-effort: populated when the caller already materialized
    the full list (research scale), otherwise ``None``.
    """

    model_config = ConfigDict(extra="allow")

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None


def _lower_bound(
    items: Sequence[T], keys: tuple[str, ...], key_func: Callable[[T], tuple[str, ...]]
) -> int:
    """First index whose cursor key tuple strictly exceeds ``keys``."""
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if key_func(items[mid]) <= keys:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _lower_bound_inclusive(
    items: Sequence[T], keys: tuple[str, ...], key_func: Callable[[T], tuple[str, ...]]
) -> int:
    """First index whose cursor key tuple is greater than or equal to ``keys``."""
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if key_func(items[mid]) < keys:
            lo = mid + 1
        else:
            hi = mid
    return lo


def page_sorted(
    items: list[T],
    *,
    cursor: str | None,
    page_size: int,
    key_func: Callable[[T], tuple[str, ...]],
    total: int | None = None,
    reverse: bool = False,
) -> Paginated[T]:
    """Slice an already-sorted list into one page.

    ``items`` must be sorted ascending by ``key_func``. ``total`` defaults to
    ``len(items)`` (in-memory list); pass ``None`` explicitly to signal that
    counting is expensive.

    When ``reverse`` is True the pages are yielded newest-first (descending
    order) while still using stable cursor-based navigation: internally the
    ascending list is walked from the end, and each emitted page is reversed so
    callers receive items in descending order.
    """
    page_size = max(1, int(page_size))
    if not items:
        return Paginated(items=[], next_cursor=None, has_more=False, total=total or 0)

    if not reverse:
        start = 0
        if cursor is not None:
            n_keys = len(key_func(items[0]))
            keys = decode_cursor(cursor, n_keys)
            start = _lower_bound(items, keys, key_func)

        page = items[start : start + page_size]
        has_more = start + page_size < len(items)
        next_cursor = encode_cursor(key_func(page[-1])) if page and has_more else None
        return Paginated(
            items=page,
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(items) if total is None else total,
        )

    # Reverse (descending) pagination: walk the ascending list from the end.
    # The cursor encodes the smallest key already returned; the next page
    # covers items strictly before it (first index with key >= cursor).
    if cursor is None:
        end = len(items)
        start = max(0, len(items) - page_size)
    else:
        n_keys = len(key_func(items[0]))
        keys = decode_cursor(cursor, n_keys)
        end = _lower_bound_inclusive(items, keys, key_func)
        start = max(0, end - page_size)
    page = list(reversed(items[start:end]))
    has_more = start > 0
    next_cursor = encode_cursor(key_func(items[start])) if page and has_more else None
    return Paginated(
        items=page,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(items) if total is None else total,
    )
