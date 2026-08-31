# Echo Chamber Detection

> Five observable signals (S1–S5) computed **only from edges the system actually observed** — never estimated. Implemented in `SocialScienceResearch/services/echo_chamber_service.py` (1270 lines, committed).

## Design principle

The echo-chamber service is a *thin orchestration layer* over `LayerScrapeService`: it crawls successive layers around a seed video (`discovery_mode="frontier"`) as one async job, and after each completed layer computes **five observed signal snapshots** over the accumulated crawl-family graph (`echo_chamber_service.py:1-20`). Caveat in the code: *"NO parallel graph math"* — the recursion is honest about what it can and cannot measure.

Signals that cannot be observed carry `status="unavailable"` and `null` values — **never fabricated** (`:3-9`). The per-layer timeline is append-only: snapshots are frozen at computation time and never recomputed retroactively (`:13-14`).

## Parameters & lifecycle

| Constant | Value | Source |
|---|---|---|
| `MAX_LAYERS_TOTAL` | `10` | `echo_chamber_service.py:39` |
| `DEFAULT_MAX_LAYERS` | `5` | `echo_chamber_service.py:42` |
| `S5_TOP_K` | `5` | `echo_chamber_service.py:45` (top recommended videos fed to S5) |

```
POST /api/v1/social-science/echo-chamber/detect    # start a detection (returns {detection_id, job_id})
GET  /api/v1/social-science/echo-chamber/{id}      # status + cumulative signals
GET  /api/v1/social-science/echo-chamber/{id}/lens # choose projection: video | channel
GET  /api/v1/social-science/echo-chamber/{id}/structure
POST /api/v1/social-science/echo-chamber/{id}/continue   # add layers (≤ 10 total)
POST /api/v1/social-science/echo-chamber/{id}/stop       # cooperative stop between layers
```

A detection can end `completed | exhausted | stopped | unsupported_stop | failed` — `exhausted` is an honest natural stop when no unscraped videos remain and is distinguished "from a verdict" (`:318-322`).

## The five signals

### S1 — Frontier collapse ratio (`_signal_s1`, `:417`)
Share of new edges whose **target** an earlier layer already knew. Reported **per-layer and cumulative**; the cumulative value is the scored one. Undefined before layer 2 → `unavailable` (`:466-469`).

### S2 — Seed-community concentration (`_signal_s2`, `:528`; channel variant `_signal_s2_channel`, `:480`)
- **Video lens:** Louvain(`seed=42`) community share of the seed video, normalized: `concentration = comm_share / (comm_size / n_nodes)`, clamped to `[0,1]` (`:549-577`).
- **Channel lens:** share of family edges whose recommended video belongs to the seed video's channel (`:513-517`).

### S3 — Top-channel share (`_signal_s3`, `:580`)
Weighted in-degree shares on the **channel projection**: `top1 = ranked[0]/total` is the scored value; `top3 = sum(ranked[:3])/total` also reported; full observed share distribution sorted desc (`:593-616`).

### S4 — Cross-layer repetition (`_signal_s4`, `:628`)
Distinct `(source, target)` pairs observed in ≥ 2 layers / distinct pairs (`:656-660`). Requires ≥ 2 layers. A channel-stability analog (`channel_repeat`) is carried in `detail`.

### S5 — Commenter-overlap reinforcement (`_signal_s5`, `:675`)
Mean Jaccard overlap between the seed's commenters and the top `S5_TOP_K` recommended videos' commenters (`:690-708`). Available **only when** comments were collected **and** at least one top video has persisted commenters — otherwise explicitly `unavailable` (never a fabricated `0`) (`:682-705`).

## Reporting honesty

- Each signal is wrapped with `status: available | unavailable` and `detail`, so a publication can state exactly which signals were measurable for a given detection and why.
- The `computed_at` timestamp and per-layer snapshot rows make the evolution auditable.

## What a reviewer should verify

Read `SocialScienceResearch/services/echo_chamber_service.py` yourself — the S1–S5 definitions, the `available | unavailable` wrapping, and the append-only timeline are all in committed code. Tests asserting the semantics live in `SocialScienceResearch/tests/test_echo_chamber_service.py` and `test_echo_structure_api.py`.

---

Previous: [Network Science](network.md) · Next: [Sampling](sampling.md)
