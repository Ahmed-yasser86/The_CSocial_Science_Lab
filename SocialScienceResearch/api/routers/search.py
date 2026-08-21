"""E2: global entity search router.

* ``GET {prefix}/search`` - free-text search across every registered entity
  (channel, video, comment, author, recommendation) with a unified result
  projection, relevance ranking and cursor pagination. ``entity`` restricts
  the search to one entity; unknown entities return HTTP 400.

Owned by the E2 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from SocialScienceResearch.api.routers.common import get_service
from SocialScienceResearch.services.pagination import Paginated
from SocialScienceResearch.services.search_service import ALL_ENTITIES, SearchHit, SearchService

router = APIRouter()

#: Default page size for search results.
DEFAULT_PAGE_SIZE = 50


def _search(request: Request) -> SearchService:
    return get_service(
        request,
        "search",
        lambda: SearchService(request.app.state.services["repos"]),
    )


@router.get(
    "/search",
    response_model=Paginated[SearchHit],
    tags=["search"],
)
def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Free-text query (tokenized, case-insensitive)"),
    entity: str | None = Query(None, description=f"Restrict to one entity: {', '.join(ALL_ENTITIES)}"),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """Search every registered entity and return a relevance-ranked page."""
    return _search(request).search(
        q=q,
        entity=entity,
        cursor=cursor,
        page_size=page_size,
    )
