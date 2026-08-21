import { describe, expect, it } from "vitest";
import {
  runColorFor,
  communityColorFor,
  filterGraphNodes,
  type GraphNode,
} from "@/components/features/network-graph";

const nodes: GraphNode[] = [
  {
    id: "A",
    title: "Alpha video",
    channel: "Channel One",
    kind: "source",
    in_degree: 0,
    out_degree: 5,
    community_id: 0,
  },
  {
    id: "B",
    title: "Beta video",
    channel: "Channel One",
    kind: "both",
    in_degree: 3,
    out_degree: 3,
    community_id: 0,
  },
  {
    id: "C",
    title: "Gamma clip",
    channel: "Channel Two",
    kind: "target",
    in_degree: 8,
    out_degree: 0,
    community_id: 1,
  },
  {
    id: "D",
    title: "Delta video",
    channel: "Channel Two",
    kind: "other",
    in_degree: 1,
    out_degree: 1,
    community_id: null,
  },
];

describe("network graph color helpers", () => {
  it("assigns a stable color per run id", () => {
    expect(runColorFor("run_a")).toBe(runColorFor("run_a"));
    expect(runColorFor("run_b")).toBe(runColorFor("run_b"));
  });

  it("different run ids can resolve to distinct colors", () => {
    const seen = new Set(
      Array.from({ length: 20 }, (_, i) => runColorFor(`run_${i}`)),
    );
    expect(seen.size).toBeGreaterThan(1);
  });

  it("assigns a stable community color per community id", () => {
    expect(communityColorFor(0)).toBe(communityColorFor(0));
    expect(communityColorFor(1)).toBe(communityColorFor(1));
    expect(communityColorFor(0)).not.toBe(communityColorFor(1));
  });
});

describe("filterGraphNodes", () => {
  it("returns all nodes with no filters", () => {
    expect(filterGraphNodes(nodes, {})).toHaveLength(4);
  });

  it("filters by minimum degree", () => {
    const result = filterGraphNodes(nodes, { minDegree: 5 });
    expect(result.map((n) => n.id).sort()).toEqual(["A", "B", "C"]);
    expect(filterGraphNodes(nodes, { minDegree: 6 }).map((n) => n.id).sort()).toEqual(["B", "C"]);
  });

  it("filters by node kind", () => {
    const result = filterGraphNodes(nodes, { kinds: ["source", "target"] });
    expect(result.map((n) => n.id).sort()).toEqual(["A", "C"]);
  });

  it("filters by community", () => {
    const result = filterGraphNodes(nodes, { communityId: 0 });
    expect(result.map((n) => n.id).sort()).toEqual(["A", "B"]);
  });

  it("filters by search across id, title and channel", () => {
    expect(filterGraphNodes(nodes, { search: "gamma" }).map((n) => n.id)).toEqual(["C"]);
    expect(filterGraphNodes(nodes, { search: "channel two" }).map((n) => n.id).sort()).toEqual(["C", "D"]);
    expect(filterGraphNodes(nodes, { search: "beta" }).map((n) => n.id).sort()).toEqual(["B"]);
  });

  it("combines filters with AND semantics", () => {
    const result = filterGraphNodes(nodes, { communityId: 0, kinds: ["both"] });
    expect(result.map((n) => n.id)).toEqual(["B"]);
  });
});