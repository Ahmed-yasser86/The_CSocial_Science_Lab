/** Client-side export helpers for network graphs (edge list, nodes, JSON, XLSX). */

import * as XLSX from "xlsx";

export interface ExportNode {
  id: string;
  title?: string | null;
  channel?: string | null;
  channel_id?: string | null;
  kind?: string;
  in_degree?: number;
  out_degree?: number;
  views?: number | null;
  likes?: number | null;
  duration?: number | null;
  community_id?: number | null;
  recommendations_scraped?: boolean | null;
}

export interface ExportLink {
  source: string;
  target: string;
  position?: number | null;
  run_id?: string | null;
  run_type?: string | null;
  run_name?: string | null;
  title?: string | null;
}

export type GraphExportFormat = "edges-csv" | "nodes-csv" | "json" | "xlsx";

export type MetadataExportFormat = "csv" | "json" | "xlsx";

function triggerDownload(filename: string, content: string | ArrayBuffer, mime: string) {
  const blob = new Blob([content as BlobPart], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function toCSV(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const lines = [headers.map(csvEscape).join(",")];
  for (const row of rows) lines.push(row.map(csvEscape).join(","));
  return lines.join("\r\n");
}

function edgeRows(nodes: ExportNode[], links: ExportLink[]) {
  const titleById = new Map(nodes.map((n) => [n.id, n.title ?? ""]));
  return links.map((l) => [
    l.source,
    l.target,
    titleById.get(l.source) ?? "",
    titleById.get(l.target) ?? "",
    l.run_id ?? "",
    l.run_type ?? "",
    l.position == null ? "" : l.position + 1,
  ]);
}

function nodeRows(nodes: ExportNode[]) {
  return nodes.map((n) => [
    n.id,
    n.title ?? "",
    n.kind ?? "",
    n.in_degree ?? 0,
    n.out_degree ?? 0,
    n.channel_id ?? "",
  ]);
}

export interface BuiltExport {
  filename: string;
  content: string | ArrayBuffer;
  mime: string;
}

export function buildGraphExport(
  format: GraphExportFormat,
  nodes: ExportNode[],
  links: ExportLink[],
  baseName: string,
): BuiltExport {
  switch (format) {
    case "edges-csv": {
      const headers = [
        "source_video_id",
        "target_video_id",
        "source_title",
        "target_title",
        "run_id",
        "run_type",
        "position",
      ];
      return {
        filename: `${baseName}-edges.csv`,
        content: toCSV(headers, edgeRows(nodes, links)),
        mime: "text/csv;charset=utf-8",
      };
    }
    case "nodes-csv": {
      const headers = ["video_id", "title", "kind", "in_degree", "out_degree", "channel_id"];
      return {
        filename: `${baseName}-nodes.csv`,
        content: toCSV(headers, nodeRows(nodes)),
        mime: "text/csv;charset=utf-8",
      };
    }
    case "json": {
      const data = {
        exported_at: new Date().toISOString(),
        nodes,
        links,
      };
      return {
        filename: `${baseName}-graph.json`,
        content: JSON.stringify(data, null, 2),
        mime: "application/json",
      };
    }
    case "xlsx": {
      const titleById = new Map(nodes.map((n) => [n.id, n.title ?? ""]));
      const edgesSheet = links.map((l) => ({
        source_video_id: l.source,
        target_video_id: l.target,
        source_title: titleById.get(l.source) ?? "",
        target_title: titleById.get(l.target) ?? "",
        run_id: l.run_id ?? "",
        run_type: l.run_type ?? "",
        position: l.position == null ? "" : l.position + 1,
      }));
      const nodesSheet = nodes.map((n) => ({
        video_id: n.id,
        title: n.title ?? "",
        kind: n.kind ?? "",
        in_degree: n.in_degree ?? 0,
        out_degree: n.out_degree ?? 0,
        channel_id: n.channel_id ?? "",
      }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(edgesSheet), "Edges");
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(nodesSheet), "Nodes");
      const out = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      return {
        filename: `${baseName}-graph.xlsx`,
        content: out,
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      };
    }
  }
}

export function exportGraph(
  format: GraphExportFormat,
  nodes: ExportNode[],
  links: ExportLink[],
  baseName: string,
): void {
  const built = buildGraphExport(format, nodes, links, baseName);
  triggerDownload(built.filename, built.content, built.mime);
}

const METADATA_HEADERS = [
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
] as const;

function metadataRows(nodes: ExportNode[]) {
  return nodes.map((n) => [
    n.id,
    n.title ?? "",
    n.kind ?? "",
    n.channel ?? "",
    n.channel_id ?? "",
    n.in_degree ?? 0,
    n.out_degree ?? 0,
    n.views ?? "",
    n.likes ?? "",
    n.duration ?? "",
    n.community_id ?? "",
    n.recommendations_scraped == null ? "" : String(n.recommendations_scraped),
  ]);
}

/** Build a flat per-video metadata export (all nodes in the current network). */
export function buildVideoMetadataExport(
  format: MetadataExportFormat,
  nodes: ExportNode[],
  baseName: string,
): BuiltExport {
  switch (format) {
    case "csv":
      return {
        filename: `${baseName}-metadata.csv`,
        content: toCSV(METADATA_HEADERS as unknown as string[], metadataRows(nodes)),
        mime: "text/csv;charset=utf-8",
      };
    case "json":
      return {
        filename: `${baseName}-metadata.json`,
        content: JSON.stringify(
          {
            exported_at: new Date().toISOString(),
            videos: nodes,
          },
          null,
          2,
        ),
        mime: "application/json",
      };
    case "xlsx": {
      const sheet = nodes.map((n) => ({
        video_id: n.id,
        title: n.title ?? "",
        kind: n.kind ?? "",
        channel: n.channel ?? "",
        channel_id: n.channel_id ?? "",
        in_degree: n.in_degree ?? 0,
        out_degree: n.out_degree ?? 0,
        views: n.views ?? "",
        likes: n.likes ?? "",
        duration: n.duration ?? "",
        community_id: n.community_id ?? "",
        recommendations_scraped: n.recommendations_scraped ?? "",
      }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(
        wb,
        XLSX.utils.json_to_sheet(sheet),
        "Metadata",
      );
      const out = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      return {
        filename: `${baseName}-metadata.xlsx`,
        content: out,
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      };
    }
  }
}

export function exportVideoMetadata(
  format: MetadataExportFormat,
  nodes: ExportNode[],
  baseName: string,
): void {
  const built = buildVideoMetadataExport(format, nodes, baseName);
  triggerDownload(built.filename, built.content, built.mime);
}
