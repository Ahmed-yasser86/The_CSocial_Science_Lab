"""Network matrices (US-60/61): structural matrices for science reporting.

Two matrices are provided:

* ``community_matrix`` - channel x channel shared-commenter counts (audience
  duplication across channels). Reuses :class:`CommenterOverlapService` so the
  numbers are identical to the Echo-chamber analysis (single source of truth).
* ``layer_matrix`` - recommendation-edge structure per crawl layer: outgoing
  edge count, unique source videos, unique recommended videos and unique target
  channels per ``layer_index``. This summarises how each expansion layer
  contributes edges to the recommendation graph.

All data derives from persisted comments / recommendation observations; no new
persistence and no estimation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.commenter_overlap_service import (
    CommenterOverlapService,
)


class NetworkMatrixService:
    """Structural matrix builder over the persisted corpus."""

    # Cap on the number of channels considered for the default (unscoped)
    # community matrix, to keep the O(channels^2) overlap responsive.
    _MAX_DEFAULT_CHANNELS = 75

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def community_matrix(
        self,
        *,
        channel_ids: list[str] | None = None,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """Channel x channel shared-commenter count matrix.

        Returns ``{labels, matrix, totals}`` where ``matrix[a][b]`` is the number
        of distinct commenters active on both channels (symmetric, diagonal 0).
        """
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        service = CommenterOverlapService(self._repos)
        if channel_ids is None:
            # The default (all-channels) community matrix is O(channels^2);
            # cap to the first channels (sorted for determinism) so the default
            # view stays responsive. Scope to explicit channels for a focused
            # matrix.
            all_channels = self._repos.channels.list_channels()
            all_channels.sort(key=lambda c: c.channel_id)
            channel_ids = [c.channel_id for c in all_channels[: self._MAX_DEFAULT_CHANNELS]]
        if not channel_ids:
            return {"labels": [], "matrix": {}, "totals": {}}
        result = service.overlap(
            channel_ids=channel_ids,
            metric="intersection",
            min_entities=1,
            min_shared=1,
            top_n=top_n,
        )
        channels = result.channels
        if channels is None:
            return {"labels": [], "matrix": {}, "totals": {}}
        labels = [e.entity_id for e in channels.entities]
        matrix: dict[str, dict[str, int]] = {label: {} for label in labels}
        for p in channels.pairs:
            matrix.setdefault(p.entity_a, {})[p.entity_b] = p.intersection_size
            matrix.setdefault(p.entity_b, {})[p.entity_a] = p.intersection_size
        totals = {
            e.entity_id: e.commenter_count for e in channels.entities
        }
        channel_names = {
            c.channel_id: (c.title or "") for c in self._repos.channels.list_channels()
        }
        label_meta = {
            label: channel_names.get(label, "") or label for label in labels
        }
        return {
            "labels": labels,
            "matrix": matrix,
            "totals": totals,
            "label_meta": label_meta,
        }

    def layer_matrix(
        self,
        *,
        run_ids: list[str] | None = None,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """Recommendation-edge structure per crawl layer.

        Returns ``{labels, rows}`` where each row carries the edge count and
        unique source / recommended / target-channel counts for a layer.
        """
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=run_ids
        )
        channel_of = {
            c.channel_id: c.channel_id
            for c in self._repos.channels.list_channels()
        }
        video_channel = {
            v.video_id: v.channel_id for v in self._repos.videos.list_videos()
        }

        per_layer: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "edge_count": 0,
                "sources": set(),
                "targets": set(),
                "target_channels": set(),
            }
        )
        for e in edges:
            layer = e.layer_index if e.layer_index is not None else -1
            row = per_layer[layer]
            row["edge_count"] += 1
            row["sources"].add(e.source_video_id)
            row["targets"].add(e.recommended_video_id)
            tgt_ch = video_channel.get(e.recommended_video_id)
            if tgt_ch is not None:
                row["target_channels"].add(tgt_ch)

        labels = sorted(per_layer.keys())
        rows = [
            {
                "layer_index": layer,
                "edge_count": per_layer[layer]["edge_count"],
                "unique_sources": len(per_layer[layer]["sources"]),
                "unique_targets": len(per_layer[layer]["targets"]),
                "unique_target_channels": len(per_layer[layer]["target_channels"]),
            }
            for layer in labels[:top_n]
        ]
        return {"labels": labels, "rows": rows}
