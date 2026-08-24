"""B3: Comment analytics + longitudinal/history router.

Endpoints for comment participation/replies/velocity decay analytics
(``CommentAnalyticsService``) and longitudinal channel/video histories, run
deltas and observation gaps (``LongitudinalService``). Comment selection goes
through ``QueryService`` (wiring the previously-unwired ``CommentFilter``).

Routes are declared as relative paths; the app includes this router under
``settings.api.prefix`` (e.g. ``/api/v1/social-science``). List endpoints use
opaque cursor pagination and return the ``{items, next_cursor, has_more,
total}`` envelope.

Owned by the B3 module agent. Do NOT edit ``api/app.py`` from here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from SocialScienceResearch.api.routers.common import get_service, paginated
from SocialScienceResearch.api.schemas import CommentTreePayload
from SocialScienceResearch.services.comment_analytics_service import (
    CommentAnalyticsService,
    ParticipationAnalytics,
    ReplyMetrics,
    VelocityDecay,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.longitudinal_service import (
    ChannelHistoryPoint,
    LongitudinalService,
    RunDeltaReport,
    VideoHistoryPoint,
)
from SocialScienceResearch.services.pagination import Paginated

router = APIRouter()

#: Default page size for cursor-paginated list endpoints (matches api/app.py).
DEFAULT_PAGE_SIZE = 50


def _comment_analytics(request: Request) -> CommentAnalyticsService:
    return get_service(
        request,
        "comment_analytics",
        lambda: CommentAnalyticsService(request.app.state.services["repos"]),
    )


def _longitudinal(request: Request) -> LongitudinalService:
    return get_service(
        request,
        "longitudinal",
        lambda: LongitudinalService(request.app.state.services["repos"]),
    )


def _history_key(point) -> tuple[str, ...]:
    return (point.observed_at.isoformat(), point.observation_id)


# ----------------------------------------------------------------------
# Comment analytics
# ----------------------------------------------------------------------
@router.get(
    "/videos/{video_id}/comments/analytics/participation",
    tags=["analytics"],
    response_model=ParticipationAnalytics,
)
def participation_analytics(video_id: str, request: Request):
    """Unique vs repeat author participation for a video's comments."""
    return _comment_analytics(request).participation(video_id)


@router.get(
    "/videos/{video_id}/comments/analytics/replies",
    tags=["analytics"],
    response_model=ReplyMetrics,
)
def reply_analytics(video_id: str, request: Request):
    """Reply rate and thread-size distribution for a video's comments."""
    return _comment_analytics(request).reply_metrics(video_id)


@router.get(
    "/videos/{video_id}/comments/{comment_id}/tree",
    tags=["analytics"],
    response_model=CommentTreePayload,
)
def comment_tree(video_id: str, comment_id: str, request: Request):
    """Full comment tree with all nested replies for a root comment."""
    repos: Repositories = request.app.state.services["repos"]
    return _build_comment_tree(repos, video_id, comment_id)


@router.get(
    "/videos/{video_id}/comments/analytics/velocity",
    tags=["analytics"],
    response_model=VelocityDecay,
)
def velocity_decay_analytics(
    video_id: str, request: Request, bucket: str = Query("day")
):
    """Comment counts per hour/day bucket plus upload-relative decay shares."""
    return _comment_analytics(request).velocity_decay(video_id, bucket=bucket)


# ----------------------------------------------------------------------
# Longitudinal histories
# ----------------------------------------------------------------------
@router.get(
    "/channels/{channel_id}/history",
    tags=["corpus"],
    response_model=Paginated[ChannelHistoryPoint],
)
def channel_history(
    channel_id: str,
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """All channel observations, oldest first, with per-step growth %."""
    points = _longitudinal(request).channel_history(channel_id)
    return paginated(points, cursor=cursor, page_size=page_size, key=_history_key)


@router.get(
    "/videos/{video_id}/history",
    tags=["corpus"],
    response_model=Paginated[VideoHistoryPoint],
)
def video_history(
    video_id: str,
    request: Request,
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=500),
):
    """All video observations, oldest first, with per-step growth %."""
    points = _longitudinal(request).video_history(video_id)
    return paginated(points, cursor=cursor, page_size=page_size, key=_history_key)


# ----------------------------------------------------------------------
# Run deltas (longitudinal)
# ----------------------------------------------------------------------
@router.get("/runs/delta", tags=["runs"], response_model=RunDeltaReport)
def run_delta(request: Request, from_run: str = Query(...), to_run: str = Query(...)):
    """Diff two run snapshots: per-metric change + growth, new/disappeared."""
    return _longitudinal(request).run_deltas(from_run, to_run)


@router.get("/runs/{run_id}/deltas", tags=["runs"], response_model=RunDeltaReport)
def single_run_deltas(run_id: str, request: Request):
    """Diff one run against the previous run of the same type."""
    return _longitudinal(request).run_entity_deltas(run_id)


# ----------------------------------------------------------------------
# Comment tree helper
# ----------------------------------------------------------------------

#: Maximum recursion depth when expanding a thread. Deeper replies stay
#: reachable in the corpus but are not walked further; the deepest node of a
#: cut subtree is flagged with ``truncated=True`` instead of being dropped.
MAX_DEPTH = 50


def _build_comment_tree(repos: Repositories, video_id: str, root_comment_id: str) -> CommentTreePayload:
    """Build a full comment tree with all nested replies for a root comment."""
    # Get the root comment
    root_comment = repos.comments.get_comment(root_comment_id)
    if root_comment is None or root_comment.video_id != video_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Comment {root_comment_id} not found in video {video_id}")

    latest_obs = repos.comments.get_latest_comment_observations([root_comment_id])

    def enrich_comment(comment):
        payload = comment.model_dump()
        obs = latest_obs.get(comment.comment_id)
        if obs:
            payload["like_count"] = obs.like_count
            payload["reply_count"] = obs.reply_count
            payload["is_removed"] = obs.is_removed
        return payload

    # Walk the tree breadth-first, batch-fetching each level's replies in one
    # scan per level (``list_replies_by_ids``) instead of one per node.
    nodes: dict[str, Any] = {root_comment_id: root_comment}
    levels: dict[str, list[Any]] = {}
    frontier = [root_comment_id]
    depth = 0
    truncated_ids: set[str] = set()
    while frontier and depth < MAX_DEPTH:
        batches = repos.comments.list_replies_by_ids(frontier)
        next_frontier: list[str] = []
        for parent_id in frontier:
            replies = batches.get(parent_id, [])
            levels[parent_id] = replies
            for reply in replies:
                if reply.comment_id not in nodes:
                    nodes[reply.comment_id] = reply
                    next_frontier.append(reply.comment_id)
        frontier = next_frontier
        depth += 1
    # Depth cap hit: the frontier nodes' subtrees are unexplored - flag them.
    truncated_ids = set(frontier)

    reply_obs = repos.comments.get_latest_comment_observations(list(nodes))
    latest_obs.update(reply_obs)

    def build_tree(comment_id: str, depth: int) -> CommentTreePayload | None:
        comment = nodes.get(comment_id)
        if comment is None:
            return None

        replies = levels.get(comment_id, [])
        children = []
        for reply in replies:
            child_tree = build_tree(reply.comment_id, depth + 1)
            if child_tree:
                children.append(child_tree)

        return CommentTreePayload(
            comment=enrich_comment(comment),
            replies=children,
            total_replies=len(replies),
            max_depth=depth if not children else max(c.max_depth for c in children) + 1,
            truncated=comment_id in truncated_ids,
        )

    tree = build_tree(root_comment_id, 0)
    if tree is None:
        # Deleted between the existence check and the walk - return an
        # explicit empty payload rather than ``None``.
        tree = CommentTreePayload(
            comment=enrich_comment(root_comment),
            replies=[],
            total_replies=0,
            max_depth=0,
            truncated=False,
        )
    return tree