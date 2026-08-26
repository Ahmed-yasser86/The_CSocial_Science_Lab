"""Echo-chamber detector domain models (echo_chamber_detector_plan.md §4).

An :class:`EchoDetection` owns one crawl family: a seed video, the layered
recommendation crawl chained from it (``LayerRun`` anchors via the existing
layer-scrape service) and an append-only per-layer timeline of OBSERVED
signal snapshots plus a transparent composite score. Every signal value is
computed from stored observations only; a signal that could not be observed
carries ``status="unavailable"`` and a ``null`` value (never fabricated).

The ``layers`` timeline is append-only: previously computed snapshots never
change retroactively when more layers are appended (pitfall A5). Snapshots
and the score travel as plain JSON (the plan stores cached snapshots that
remain recomputable from observations).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_RESPONSE_CONFIG = ConfigDict(extra="allow")

#: Detection lifecycle. ``exhausted`` = frontier exhausted (natural stop),
#: ``unsupported_stop`` = a layer observed zero edges (natural stop).
EchoDetectionStatus = str  # pending|running|completed|exhausted|stopped|unsupported_stop|failed


class EchoDetection(BaseModel):
    """The full detection record: spec + append-only timeline + latest score."""

    model_config = _RESPONSE_CONFIG

    detection_id: str
    seed_video_id: str | None = None
    seed_run_id: str | None = None
    root_layer_run_id: str | None = None
    job_id: str | None = None
    status: str = "pending"
    params: dict[str, Any] = Field(default_factory=dict)
    #: Append-only per-layer snapshots (plan §4 layer shape), frozen at
    #: computation time: {layer_run_id, layer_index, nodes_discovered,
    #: edges_observed, nodes_total, signals:{s1..s5}, computed_at}.
    layers: list[dict[str, Any]] = Field(default_factory=list)
    #: Latest composite score payload (plan §2.2): {value, band, verdict,
    #: components[], computed_at} with every component's effective weight.
    score: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
