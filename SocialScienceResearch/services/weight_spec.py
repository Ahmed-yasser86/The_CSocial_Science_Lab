"""Weight-spec grammar, parser and catalog for the network-analysis expansion.

A *weight spec* describes how recommendation (or, later, audience) edges are
weighted before any graph algorithm runs. It is the single source of truth
shared by ``/network/graph``, ``/network/export`` and ``/network/centralities``
so weights cannot diverge between surfaces (parity by construction).

Canonical serialized form (query param, snapshot recipe, export metadata,
reproducibility footer)::

    edge_type:weight_mode[:param=value,...][:norm=<n>]

e.g. ``co_comment:jaccard:min_shared=2:norm=min_max`` or, for the default
recommendation weighting, ``recommendation:observation_count``.

Responses always echo the fully-expanded object so clients never have to
re-parse the token.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

#: Normalization operators applied after aggregation.
NORMALIZATIONS: tuple[str, ...] = ("none", "min_max", "log1p")

#: Bounded params accepted on the weight token, with their coerced dtype.
WEIGHT_PARAM_SCHEMA: dict[str, type] = {
    "min_shared": int,
    "top_n": int,
    "position_decay": float,
}

#: Known weight modes per edge family. ``signal`` names the raw observation
#: attribute the mode depends on (used for availability + the
#: ``weight_provenance.unavailable_signals`` contract). ``None`` means the mode
#: is always available (it only needs the structural edge count).
WEIGHT_MODES: dict[str, dict[str, dict[str, Any]]] = {
    "recommendation": {
        "observation_count": {
            "signal": None,
            "description": "Count of recommendation observations (today's default weighting).",
        },
        "reciprocal_position": {
            "signal": "position",
            "description": "Reciprocal of each observation's recommendation position (1/position).",
        },
    },
    "co_comment": {
        "jaccard": {
            "signal": "comments.author_id",
            "description": "Jaccard overlap of commenter video-sets (bridge detection).",
        },
        "overlap_coefficient": {
            "signal": "comments.author_id",
            "description": "Szymkiewicz-Simpson overlap of commenter video-sets.",
        },
        "intersection": {
            "signal": "comments.author_id",
            "description": "Shared-video count between commenters (co-comment volume).",
        },
        "counts": {
            "signal": "comments.author_id",
            "description": "Shared-video count between commenters.",
        },
    },
}


class WeightSpecError(ValueError):
    """Raised when a weight spec token/object is invalid."""


class WeightSpec(BaseModel):
    edge_type: str
    weight_mode: str
    params: dict[str, Any] = {}
    normalization: str = "none"

    def to_token(self) -> str:
        segs = [self.edge_type, self.weight_mode]
        for key, val in self.params.items():
            segs.append(f"{key}={val}")
        if self.normalization and self.normalization != "none":
            segs.append(f"norm={self.normalization}")
        return ":".join(segs)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _coerce_param(name: str, value: Any) -> Any:
    dtype = WEIGHT_PARAM_SCHEMA.get(name)
    if dtype is None:
        return value
    try:
        return dtype(value)
    except (TypeError, ValueError) as exc:
        raise WeightSpecError(
            f"weight param '{name}' must be {dtype.__name__}, got '{value}'"
        ) from exc


def _validate(
    edge_type: str | None,
    weight_mode: str | None,
    params: dict[str, Any],
    normalization: str,
) -> WeightSpec:
    if edge_type is None:
        raise WeightSpecError(
            "weight spec missing edge_type. Legal edge_types: "
            + ", ".join(WEIGHT_MODES)
        )
    if edge_type not in WEIGHT_MODES:
        raise WeightSpecError(
            f"unknown edge_type '{edge_type}'. Legal edge_types: "
            + ", ".join(WEIGHT_MODES)
        )
    modes = WEIGHT_MODES[edge_type]
    if weight_mode is None:
        raise WeightSpecError(
            f"weight spec for '{edge_type}' missing weight_mode. Legal modes: "
            + ", ".join(modes)
        )
    if weight_mode not in modes:
        raise WeightSpecError(
            f"unknown weight_mode '{weight_mode}' for edge_type '{edge_type}'. "
            f"Legal modes: {', '.join(modes)}"
        )
    if normalization not in NORMALIZATIONS:
        raise WeightSpecError(
            f"unknown normalization '{normalization}'. Legal normalizations: "
            + ", ".join(NORMALIZATIONS)
        )
    for key, val in list(params.items()):
        if key not in WEIGHT_PARAM_SCHEMA:
            raise WeightSpecError(
                f"unknown weight param '{key}'. Legal params: "
                + ", ".join(WEIGHT_PARAM_SCHEMA)
            )
        params[key] = _coerce_param(key, val)
    return WeightSpec(
        edge_type=edge_type,
        weight_mode=weight_mode,
        params=params,
        normalization=normalization,
    )


def parse_weight_spec(raw: Any) -> WeightSpec:
    """Parse a weight spec from a token string, a dict, or a ``WeightSpec``.

    Raises :class:`WeightSpecError` (a ``ValueError`` subclass) with a message
    that lists the legal options when the input is invalid.
    """
    if isinstance(raw, WeightSpec):
        return raw
    if isinstance(raw, dict):
        edge_type = raw.get("edge_type")
        weight_mode = raw.get("weight_mode")
        params = dict(raw.get("params") or {})
        normalization = raw.get("normalization") or "none"
        return _validate(edge_type, weight_mode, params, normalization)

    if isinstance(raw, str):
        token = raw.strip()
        if not token:
            raise WeightSpecError("weight spec token must not be empty")
        parts = token.split(":")
        edge_type = parts[0] or None
        weight_mode = parts[1] if len(parts) > 1 else None
        params: dict[str, Any] = {}
        normalization = "none"
        for seg in parts[2:]:
            if seg.startswith("norm="):
                normalization = seg[5:]
            elif "=" in seg:
                key, val = seg.split("=", 1)
                params[key] = _coerce_param(key, val)
            elif seg in NORMALIZATIONS:
                normalization = seg
            elif seg == "":
                continue
            else:
                raise WeightSpecError(
                    f"unknown weight segment '{seg}'. Legal normalizations: "
                    + ", ".join(NORMALIZATIONS)
                )
        return _validate(edge_type, weight_mode, params, normalization)

    raise WeightSpecError("weight spec must be a token string or an object")


def _availability(
    edge_type: str,
    mode: str,
    meta: dict[str, Any],
    repos: Any,
    run_id: str | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Best-effort availability for a weight mode given the active repos.

    The Audience family (``co_comment``) is implemented; the per-scope coverage
    of individual signals is surfaced at computation time via
    ``weight_provenance.unavailable_signals`` (the authoritative contract), so
    this catalog only needs coarse gating.
    """
    if edge_type == "co_comment":
        return True, []
    signal = meta["signal"]
    if signal is None:
        return True, []
    if repos is None:
        return True, []
    try:
        edges = repos.recommendations.list_recommendation_edges(run_id=run_id)
    except Exception:
        return True, []
    if not edges:
        return False, [{"signal": "recommendation_edges", "coverage": 0.0}]
    if signal == "position":
        has_position = any(
            getattr(edge, "position", None) is not None for edge in edges
        )
        if not has_position:
            return False, [{"signal": "position", "coverage": 0.0}]
    return True, []


def weight_options_catalog(
    repos: Any = None, run_id: str | None = None
) -> list[dict[str, Any]]:
    """Catalog of legal ``edge_type × weight_mode`` combos for UI dropdowns."""
    options: list[dict[str, Any]] = []
    for edge_type, modes in WEIGHT_MODES.items():
        for mode, meta in modes.items():
            available, missing = _availability(edge_type, mode, meta, repos, run_id)
            options.append(
                {
                    "edge_type": edge_type,
                    "weight_mode": mode,
                    "description": meta["description"],
                    "signal": meta["signal"],
                    "normalizations": list(NORMALIZATIONS),
                    "params": [
                        {"name": name, "type": dtype.__name__}
                        for name, dtype in WEIGHT_PARAM_SCHEMA.items()
                    ],
                    "available": available,
                    "unavailable_signals": missing,
                }
            )
    return options


def edge_weight_for_mode(mode: str, position: int | None) -> float:
    """Raw (pre-normalization) weight for one observation edge under ``mode``.

    ``observation_count`` is the structural default (every edge = 1.0);
    ``reciprocal_position`` is ``1/position`` (later rail slots weigh less).
    Audience modes (``co_comment``) are computed elsewhere (N2) and fall back
    to the structural weight here.
    """
    if mode == "observation_count":
        return 1.0
    if mode == "reciprocal_position":
        if not position or position <= 0:
            return 1.0
        return 1.0 / position
    return 1.0


def normalize_weights(values: list[float], normalization: str) -> list[float]:
    """Apply a post-aggregation normalization across a set of raw weights."""
    if normalization == "none" or not values:
        return list(values)
    if normalization == "min_max":
        lo, hi = min(values), max(values)
        if hi <= lo:
            return [1.0 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]
    if normalization == "log1p":
        return [math.log1p(v) for v in values]
    return list(values)
