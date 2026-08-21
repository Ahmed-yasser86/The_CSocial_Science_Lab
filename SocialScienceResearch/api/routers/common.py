"""Shared helpers for Phase B-D routers.

Provides:
* :func:`get_service` - lazily build/cache a service on ``app.state``;
* :func:`paginated` - cursor-page a materialized list (redirects to the
  `services.pagination` module used by ``api/app.py``);
* :func:`value_payload` - the ``{value, availability}`` envelope;
* cursor key helpers for entity sorts.

Routers must never import from ``api.app`` (module-level app construction
happens there and would create an import cycle); everything they need lives in
this module or in the service layer.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

from fastapi import Request

from SocialScienceResearch.services.pagination import Paginated, page_sorted

T = TypeVar("T")


def get_service(request: Request, name: str, factory: Callable[[], Any]) -> Any:
    """Return the service with ``name`` from ``app.state.services``.

    The service is built on first access via ``factory()`` and cached on
    ``app.state`` so concurrent/parallel builds share one instance and Excel
    repositories open a single store.
    """
    services = request.app.state.services
    if name not in services:
        services[name] = factory()
    return services[name]


def paginated(
    entities: Sequence[T],
    *,
    cursor: str | None,
    page_size: int,
    key: Callable[[T], tuple[str, ...]],
    total: int | None = None,
) -> Paginated[Any]:
    """Slice a materialized entity list into a ``Paginated`` envelope.

    ``total`` is always populated for in-memory lists (research scale); pass
    ``None`` explicitly only when counting is expensive and you want it absent.
    """
    full = sorted(entities, key=key)
    page = page_sorted(
        full, cursor=cursor, page_size=page_size, key_func=key, total=total
    )
    return Paginated(
        items=[e if isinstance(e, dict) else e.model_dump() for e in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
        total=page.total,
    )


def value_payload(value) -> dict[str, Any]:
    """Serialize an availability-wrapped value into ``{value, availability}``."""
    return {
        "value": value.value,
        "availability": value.availability.value,
    }