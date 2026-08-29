import { describe, expect, it } from "vitest";
import {
  canContinue,
  isTerminalDetection,
  shapeTimeline,
  type EchoDetection,
  type EchoLayerSnapshot,
} from "@/lib/echo-chamber";

describe("shapeTimeline", () => {
  const snap = (overrides: Partial<EchoLayerSnapshot>): EchoLayerSnapshot => ({
    layer_run_id: "lyr_x",
    layer_index: 0,
    nodes_discovered: 2,
    edges_observed: 3,
    nodes_total: 5,
    signals: {
      s1: { value: null, status: "unavailable" },
      s2: { value: null, status: "unavailable" },
      s3: { value: null, status: "unavailable" },
      s4: { value: null, status: "unavailable" },
      s5: { value: null, status: "unavailable" },
    },
    computed_at: "2026-08-25T00:00:00Z",
    ...overrides,
  });

  it("flattens snapshots into render rows sorted by layer index", () => {
    const layers = [
      snap({ layer_index: 1 }),
      snap({ layer_index: 0 }),
    ];
    const rows = shapeTimeline(layers);
    expect(rows.map((r) => r.layerIndex)).toEqual([0, 1]);
  });

  it("keeps unavailable signals as null (never fabricated zeros)", () => {
    const rows = shapeTimeline([
      snap({
        layer_index: 2,
        signals: {
          s1: { value: 0.5, status: "available", detail: {} },
          s2: {
            value: 0.9,
            status: "available",
            detail: { community_share: 0.7 },
          },
          s3: { value: null, status: "unavailable" },
          s4: { value: 0.1, status: "available", detail: {} },
          s5: { value: null, status: "unavailable" },
        },
      }),
    ]);
    const row = rows[0];
    expect(row.collapsePercent).toBe(0.5);
    expect(row.communityShare).toBe(0.7);
    expect(row.topChannelShare).toBeNull();
    expect(row.commenterOverlap).toBeNull();
    expect(row.statuses.s5).toBe("unavailable");
  });

  it("returns an empty timeline for a fresh detection", () => {
    expect(shapeTimeline([])).toEqual([]);
  });
});

describe("detection state helpers", () => {
  const base = {
    detection_id: "ech_1",
    seed_video_id: null,
    seed_run_id: null,
    root_layer_run_id: null,
    job_id: null,
    status: "completed",
    params: {},
    layers: [],
    score: null,
    error: null,
    created_at: null,
    updated_at: null,
  } satisfies EchoDetection;

  it("treats natural stops and completion as terminal", () => {
    for (const status of ["completed", "exhausted", "stopped", "unsupported_stop", "failed"]) {
      expect(isTerminalDetection(status)).toBe(true);
    }
    for (const status of ["pending", "running"]) {
      expect(isTerminalDetection(status)).toBe(false);
    }
  });

  it("offers Continue only on continuable finished states", () => {
    expect(canContinue({ ...base, status: "completed" })).toBe(true);
    expect(canContinue({ ...base, status: "exhausted" })).toBe(true);
    expect(canContinue({ ...base, status: "stopped" })).toBe(true);
    expect(canContinue({ ...base, status: "running" })).toBe(false);
    // unsupported_stop means there is nothing left to crawl.
    expect(canContinue({ ...base, status: "unsupported_stop" })).toBe(false);
    expect(canContinue({ ...base, status: "failed" })).toBe(false);
  });
});
