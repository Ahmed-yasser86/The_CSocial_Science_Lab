"""Channels router.

Endpoints for listing channels with basic metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from SocialScienceResearch.api.routers.common import get_service, paginated
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.pagination import Paginated

router = APIRouter()

_CHANNELS = "channels"
DEFAULT_PAGE_SIZE = 50


def _channel_service(request: Request):
    return get_service(
        request,
        _CHANNELS,
        lambda: ChannelService(request.app.state.services["repos"]),
    )


def _channel_key(channel) -> tuple[str, ...]:
    return (channel.channel_id,)


class Channel(BaseModel):
    """Lightweight channel representation for listing."""

    model_config = ConfigDict(extra="allow")

    channel_id: str
    title: str | None = None
    handle: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None


class ChannelService:
    """Read-only channel listing service."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def list_channels(self) -> list[Channel]:
        channels = self._repos.channels.list_channels()
        latest = self._repos.channels.get_latest_channel_observations(
            [c.channel_id for c in channels]
        )
        return [
            Channel(
                channel_id=c.channel_id,
                title=c.title,
                handle=c.handle,
                subscriber_count=latest.get(c.channel_id).subscriber_count
                if latest.get(c.channel_id)
                else None,
                video_count=latest.get(c.channel_id).video_count
                if latest.get(c.channel_id)
                else None,
                view_count=latest.get(c.channel_id).view_count
                if latest.get(c.channel_id)
                else None,
            )
            for c in channels
        ]


@router.get(
    "/channels",
    tags=["channels"],
    response_model=Paginated[Channel],
)
def list_channels(
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
    q: str | None = Query(None, description="Case-insensitive text search over channel title and handle"),
):
    """List all channels with basic metadata (subscriber count, video count, etc.)."""
    service = _channel_service(request)
    items = service.list_channels()
    if q:
        q_lower = q.lower()
        items = [c for c in items if q_lower in (c.title or "").lower() or q_lower in (c.handle or "").lower()]
    return paginated(items, cursor=cursor, page_size=page_size, key=_channel_key)


@router.get(
    "/channels/{channel_id}",
    tags=["channels"],
    response_model=Channel,
)
def get_channel(
    channel_id: str,
    request: Request,
):
    """Get a single channel's basic metadata (title, handle)."""
    service = _channel_service(request)
    for channel in service.list_channels():
        if channel.channel_id == channel_id:
            return channel
    return JSONResponse(status_code=404, content={"detail": "Channel not found"})