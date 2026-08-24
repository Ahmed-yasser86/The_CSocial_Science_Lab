import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import {
  buildGraphExport,
  buildVideoMetadataExport,
  type ExportNode,
  type ExportLink,
} from "./export-graph";

// --- Exact live-shape fixtures (NetworkVideoContext -> GraphNode/GraphLink) ---
const node: ExportNode = {
  id: "AAA",
  title: "Root Video",
  kind: "both",
  in_degree: 1,
  out_degree: 2,
};
const edge: ExportLink = {
  source: "AAA",
  target: "BBB",
  run_id: "run_1",
  run_type: "recommendation",
};

// --- Large, deterministic dataset: many videos across many runs ---
const N = 30;
const RUN_IDS = ["run_a", "run_b", "run_c", "run_d", "run_e"];
const nodes: ExportNode[] = Array.from({ length: N }, (_, i) => ({
  id: `VID${String(i).padStart(3, "0")}`,
  // Distinct titles -> a regression that collapses titles to one value is caught.
  title: `Title ${i}`,
  kind: i === 0 ? "both" : i % 2 === 0 ? "source" : "target",
  in_degree: (i * 3) % 7,
  out_degree: (i * 5) % 11,
}));
const titleById = new Map(nodes.map((n) => [n.id, n.title as string]));
const links: ExportLink[] = [];
for (let i = 0; i < N - 1; i++) {
  links.push({
    source: nodes[i].id,
    target: nodes[i + 1].id,
    run_id: RUN_IDS[i % RUN_IDS.length],
    run_type: "recommendation",
    position: (i % 10) + 1,
  });
  if (i % 3 === 0) {
    links.push({
      source: nodes[i].id,
      target: nodes[(i + 5) % N].id,
      run_id: RUN_IDS[(i + 1) % RUN_IDS.length],
      run_type: "manual",
      position: (i % 7) + 1,
    });
  }
}

function parseCsv(text: string): string[][] {
  return text.split("\r\n").map((line) => {
    const out: string[] = [];
    let cur = "";
    let inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else inQ = false;
        } else cur += ch;
      } else if (ch === '"') inQ = true;
      else if (ch === ",") {
        out.push(cur);
        cur = "";
      } else cur += ch;
    }
    out.push(cur);
    return out;
  });
}

describe("buildGraphExport - small edge cases (CSV escaping)", () => {
  it("escapes commas and quotes in titles", () => {
    const special: ExportNode = {
      ...node,
      id: "BBB",
      title: 'Quote, "special" & comma',
    };
    const { content } = buildGraphExport("edges-csv", [node, special], [edge], "t");
    const rows = parseCsv(content as string);
    expect(rows[1]).toEqual([
      "AAA",
      "BBB",
      "Root Video",
      'Quote, "special" & comma',
      "run_1",
      "recommendation",
      "",
    ]);
  });
});

describe("buildGraphExport - many videos / many runs (correctness + uniqueness)", () => {
  it("edge CSV has one row per link with correct, distinct per-edge titles", () => {
    const { content } = buildGraphExport("edges-csv", nodes, links, "big");
    const rows = parseCsv(content as string);
    expect(rows[0]).toEqual([
      "source_video_id",
      "target_video_id",
      "source_title",
      "target_title",
      "run_id",
      "run_type",
      "position",
    ]);
    // One data row per link.
    expect(rows.length).toBe(links.length + 1);

    const sourceTitles = new Set<string>();
    const targetTitles = new Set<string>();
    const runIds = new Set<string>();
    for (let i = 1; i < rows.length; i++) {
      const [s, t, sTitle, tTitle, runId, runType, pos] = rows[i];
      const link = links[i - 1];
      // Titles must resolve to the real node titles, not a constant.
      expect(sTitle).toBe(titleById.get(s));
      expect(tTitle).toBe(titleById.get(t));
      // run_id / run_type preserved from the link (many runs).
      expect(RUN_IDS).toContain(runId);
      expect(["recommendation", "manual"]).toContain(runType);
      // position is the recommendation position + 1 (or "" when absent).
      expect(Number(pos)).toBe(link.position == null ? 0 : link.position + 1);
      sourceTitles.add(sTitle);
      targetTitles.add(tTitle);
      runIds.add(runId);
    }
    // Uniqueness guard: the export must NOT show the same result for all nodes.
    expect(sourceTitles.size).toBeGreaterThan(1);
    expect(targetTitles.size).toBeGreaterThan(1);
    // Many distinct runs are represented.
    expect(runIds.size).toBe(RUN_IDS.length);
  });

  it("node CSV has one row per node with its own title (no collapse)", () => {
    const { content } = buildGraphExport("nodes-csv", nodes, links, "big");
    const rows = parseCsv(content as string);
    expect(rows[0]).toEqual([
      "video_id",
      "title",
      "kind",
      "in_degree",
      "out_degree",
      "channel_id",
    ]);
    expect(rows.length).toBe(nodes.length + 1);

    const titles = new Set<string>();
    for (let i = 1; i < rows.length; i++) {
      const [id, title, kind, inD, outD] = rows[i];
      const expected = nodes[i - 1];
      expect(id).toBe(expected.id);
      expect(title).toBe(expected.title);
      expect(kind).toBe(expected.kind);
      expect(Number(inD)).toBe(expected.in_degree);
      expect(Number(outD)).toBe(expected.out_degree);
      titles.add(title);
    }
    // Every node keeps its unique title -> proves no "same result for all nodes".
    expect(titles.size).toBe(nodes.length);
  });

  it("JSON round-trips nodes/links and keeps per-id identity", () => {
    const { content } = buildGraphExport("json", nodes, links, "big");
    const parsed = JSON.parse(content as string);
    expect(parsed.nodes).toEqual(nodes);
    expect(parsed.links).toEqual(links);
    const ids = parsed.nodes.map((n: ExportNode) => n.id);
    expect(new Set(ids).size).toBe(nodes.length);
  });

  it("XLSX Edges/Nodes sheets carry correct, distinct rows", () => {
    const { content } = buildGraphExport("xlsx", nodes, links, "big");
    const wb = XLSX.read(content as ArrayBuffer, { type: "array" });
    expect(wb.SheetNames).toEqual(["Edges", "Nodes"]);

    const edges = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets["Edges"]);
    expect(edges).toHaveLength(links.length);
    const edgeSourceTitles = new Set(edges.map((e) => e.source_title));
    expect(edgeSourceTitles.size).toBeGreaterThan(1);

    const nodeRowsX = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets["Nodes"]);
    expect(nodeRowsX).toHaveLength(nodes.length);
    const nodeTitles = new Set(nodeRowsX.map((r) => r.title));
    expect(nodeTitles.size).toBe(nodes.length);
    // Spot-check one resolved mapping.
    expect(edges[0]).toMatchObject({
      source_video_id: nodes[0].id,
      target_video_id: nodes[1].id,
      source_title: nodes[0].title,
      target_title: nodes[1].title,
    });
  });
});

describe("buildVideoMetadataExport - all video metadata (correctness)", () => {
  const metaNodes: ExportNode[] = [
    {
      id: "VID000",
      title: "Title 0",
      kind: "both",
      in_degree: 1,
      out_degree: 2,
      views: 1234,
      likes: 56,
      duration: 90,
      channel: "Chan A",
      channel_id: "UC123",
      community_id: 3,
      recommendations_scraped: true,
    },
    {
      id: "VID001",
      title: 'Quote, "odd" & comma',
      kind: "source",
      in_degree: 0,
      out_degree: 5,
      views: null,
      likes: null,
      duration: null,
      channel_id: null,
      community_id: null,
      recommendations_scraped: false,
    },
  ];

  it("CSV has one row per video with the metadata headers", () => {
    const { content } = buildVideoMetadataExport("csv", metaNodes, "meta");
    const rows = parseCsv(content as string);
    expect(rows[0]).toEqual([
      "video_id",
      "title",
      "kind",
      "channel",
      "channel_id",
      "in_degree",
      "out_degree",
      "views",
      "likes",
      "duration",
      "community_id",
      "recommendations_scraped",
    ]);
    expect(rows.length).toBe(metaNodes.length + 1);
    expect(rows[1][0]).toBe("VID000");
    expect(rows[1][7]).toBe("1234");
    expect(rows[1][8]).toBe("56");
    expect(rows[1][10]).toBe("3");
    // Missing values become empty cells, not "null"/"undefined".
    expect(rows[2][7]).toBe("");
    expect(rows[2][8]).toBe("");
    // CSV escaping applies to titles too.
    expect(rows[2][1]).toBe('Quote, "odd" & comma');
  });

  it("JSON wraps videos and round-trips identity", () => {
    const { content } = buildVideoMetadataExport("json", metaNodes, "meta");
    const parsed = JSON.parse(content as string);
    expect(parsed.videos).toEqual(metaNodes);
    expect(new Set(parsed.videos.map((n: ExportNode) => n.id)).size).toBe(
      metaNodes.length,
    );
  });

  it("XLSX Metadata sheet has one row per video", () => {
    const { content } = buildVideoMetadataExport("xlsx", metaNodes, "meta");
    const wb = XLSX.read(content as ArrayBuffer, { type: "array" });
    expect(wb.SheetNames).toEqual(["Metadata"]);
    const sheet = XLSX.utils.sheet_to_json<Record<string, unknown>>(
      wb.Sheets["Metadata"],
    );
    expect(sheet).toHaveLength(metaNodes.length);
    expect(sheet[0]).toMatchObject({ video_id: "VID000", views: 1234 });
    expect(sheet[1]).toMatchObject({ video_id: "VID001", views: "" });
  });
});
