"""Echo-chamber score + verdict bands (echo plan §2.2) — pure functions.

The composite score is a weighted mean over the AVAILABLE components only
(weights renormalized over what was actually observed). A missing core signal
(S1..S4) makes the verdict ``inconclusive`` while the indicative score is
still shown and labeled. Bands are documented constants; the verdict text
describes observed structure only — never belief, never causation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

#: Default component weights (plan §2.2). Renormalized over available comps.
DEFAULT_WEIGHTS: dict[str, float] = {
    "s1": 0.35,
    "s2": 0.30,
    "s3": 0.20,
    "s4": 0.15,
    "s5": 0.15,
}

#: Human labels per component key (emitted verbatim on every response).
COMPONENT_LABELS: dict[str, str] = {
    "s1": "Frontier collapse ratio",
    "s2": "Seed-community concentration",
    "s3": "Top-channel share",
    "s4": "Cross-layer repetition",
    "s5": "Commenter-overlap reinforcement",
}

#: Core signals: any of these missing -> inconclusive verdict.
CORE_KEYS = ("s1", "s2", "s3", "s4")

BAND_NO_CHAMBER_YET = "no_chamber_yet"
BAND_WEAK = "weak"
BAND_MODERATE = "moderate"
BAND_STRONG = "strong"
VERDICT_INCONCLUSIVE = "inconclusive"


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_band(value: float | None) -> str | None:
    """Verdict band for a composite score (plan §2.2 thresholds), or ``None``.

    < 0.40 no_chamber_yet | 0.40-0.60 weak | 0.60-0.75 moderate | > 0.75 strong.
    """
    if value is None:
        return None
    if value < 0.40:
        return BAND_NO_CHAMBER_YET
    if value <= 0.60:
        return BAND_WEAK
    if value <= 0.75:
        return BAND_MODERATE
    return BAND_STRONG


def compute_score(
    signals: dict[str, float | None],
    *,
    weights: dict[str, float] | None = None,
    computed_at: datetime | None = None,
) -> dict[str, Any]:
    """Transparent composite over available signals (plan §2.2).

    ``signals`` maps component keys to observed values (``None`` when the
    signal could not be observed). Returns the full payload:
    ``{value, band, verdict, components[], computed_at}`` where every
    component carries its effective weight and availability status.
    """
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    values = {key: signals.get(key) for key in ("s1", "s2", "s3", "s4", "s5")}
    total_weight = sum(
        w.get(key, 0.0) for key, value in values.items() if value is not None
    )
    components: list[dict[str, Any]] = []
    weight_sum = 0.0
    weighted_total = 0.0
    core_missing = False
    for key, value in values.items():
        available = value is not None
        if available:
            effective = w.get(key, 0.0)
            weight_sum += effective
            weighted_total += effective * float(value)
            normalized = round(effective / total_weight, 6) if total_weight > 0 else 0.0
        else:
            effective = 0.0
            normalized = 0.0
            if key in CORE_KEYS:
                core_missing = True
        components.append(
            {
                "key": key,
                "label": COMPONENT_LABELS[key],
                "value": float(value) if available else None,
                "weight_effective": normalized,
                "status": "available" if available else "unavailable",
            }
        )
    value = round(weighted_total / weight_sum, 6) if weight_sum > 0 else None
    band = score_band(value)
    if core_missing or band is None:
        verdict = VERDICT_INCONCLUSIVE
    else:
        verdict = band
    return {
        "value": value,
        "band": band,
        "verdict": verdict,
        "components": components,
        "computed_at": computed_at,
    }
