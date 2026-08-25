import { describe, expect, it } from "vitest";
import {
  nodeHitRadius,
  nodeVisualRadius,
  shouldDrawLabel,
} from "@/components/features/network-graph";
import {
  GRAPH_NODE_SIZE_DEFAULT,
  GRAPH_NODE_SIZE_MAX,
  GRAPH_NODE_SIZE_MIN,
  normalizeGraphNodeSize,
} from "@/lib/lab-session";

describe("shouldDrawLabel", () => {
  it("hides labels by default (hover mode)", () => {
    expect(shouldDrawLabel("vid_1", {})).toBe(false);
    expect(
      shouldDrawLabel("vid_1", { hoveredId: "vid_2", matchedIds: new Set() }),
    ).toBe(false);
  });

  it("shows the label for the hovered node only", () => {
    const opts = { hoveredId: "vid_1" };
    expect(shouldDrawLabel("vid_1", opts)).toBe(true);
    expect(shouldDrawLabel("vid_2", opts)).toBe(false);
  });

  it("shows labels for search-matched / selected nodes", () => {
    const matchedIds = new Set(["vid_1", "vid_3"]);
    expect(shouldDrawLabel("vid_1", { matchedIds })).toBe(true);
    expect(shouldDrawLabel("vid_3", { matchedIds })).toBe(true);
    expect(shouldDrawLabel("vid_2", { matchedIds })).toBe(false);
  });

  it("shows every label in always-on mode", () => {
    expect(shouldDrawLabel("vid_1", { mode: "always" })).toBe(true);
    expect(
      shouldDrawLabel("vid_9", { mode: "always", matchedIds: new Set() }),
    ).toBe(true);
  });
});

describe("nodeVisualRadius", () => {
  it("reproduces the legacy 6..18px band at scale 1", () => {
    expect(nodeVisualRadius(0)).toBe(6);
    expect(nodeVisualRadius(1)).toBeCloseTo(8.5);
    expect(nodeVisualRadius(10000)).toBe(18);
  });

  it("grows monotonically with degree until capped", () => {
    let prev = -1;
    for (let d = 0; d <= 40; d += 4) {
      const r = nodeVisualRadius(d);
      expect(r).toBeGreaterThanOrEqual(prev);
      prev = r;
    }
    expect(nodeVisualRadius(1000)).toBe(nodeVisualRadius(999));
  });

  it("scales proportionally with the node-size preference", () => {
    const halfScale =
      GRAPH_NODE_SIZE_DEFAULT / 2 / GRAPH_NODE_SIZE_DEFAULT;
    expect(nodeVisualRadius(9, halfScale)).toBeCloseTo(
      nodeVisualRadius(9) * halfScale,
    );
  });

  it("keeps a positive minimum radius at the smallest preference", () => {
    expect(
      nodeVisualRadius(0, GRAPH_NODE_SIZE_MIN / GRAPH_NODE_SIZE_DEFAULT),
    ).toBeGreaterThan(0);
  });
});

describe("nodeHitRadius", () => {
  it("guarantees a ~14px effective click target regardless of visual size", () => {
    const tinyScale = GRAPH_NODE_SIZE_MIN / GRAPH_NODE_SIZE_DEFAULT;
    expect(nodeHitRadius(0, tinyScale)).toBeGreaterThanOrEqual(7);
    expect(nodeHitRadius(0, 0.01)).toBeGreaterThanOrEqual(7);
  });

  it("never shrinks a large node's hit area below its visual radius", () => {
    expect(nodeHitRadius(25)).toBe(nodeVisualRadius(25));
    expect(nodeHitRadius(25)).toBeGreaterThanOrEqual(7);
  });
});

describe("normalizeGraphNodeSize", () => {
  it("accepts values inside the supported range", () => {
    expect(normalizeGraphNodeSize(GRAPH_NODE_SIZE_DEFAULT)).toBe(
      GRAPH_NODE_SIZE_DEFAULT,
    );
    expect(normalizeGraphNodeSize(17.4)).toBe(17);
  });

  it("clamps out-of-range values into [min, max]", () => {
    expect(normalizeGraphNodeSize(0)).toBe(GRAPH_NODE_SIZE_MIN);
    expect(normalizeGraphNodeSize(-10)).toBe(GRAPH_NODE_SIZE_MIN);
    expect(normalizeGraphNodeSize(999)).toBe(GRAPH_NODE_SIZE_MAX);
  });

  it("falls back to the default for non-numeric input", () => {
    expect(normalizeGraphNodeSize(undefined)).toBe(GRAPH_NODE_SIZE_DEFAULT);
    expect(normalizeGraphNodeSize("abc")).toBe(GRAPH_NODE_SIZE_DEFAULT);
  });
});
