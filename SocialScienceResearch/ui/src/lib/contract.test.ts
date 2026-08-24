import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { findOrphans } from "../../scripts/find-orphans.mjs";

const SNAPSHOT = path.resolve(
  __dirname,
  "../../../api/openapi.json",
);
const live = JSON.parse(readFileSync(SNAPSHOT, "utf8")) as {
  paths: Record<string, Record<string, unknown>>;
};

const PATH = "/api/v1/social-science";

/**
 * Paths the frontend actually calls (mirror of services/api.ts request paths).
 * Each must exist in the generated contract types so backend renames fail CI.
 */
const USED_PATHS: Array<[string, "get" | "post"]> = [
  ["/collect/channel", "post"],
  ["/collect/video", "post"],
  ["/collect/recommendations", "post"],
  ["/collect", "post"],
  ["/jobs", "get"],
  ["/jobs/{job_id}", "get"],
  ["/jobs/{job_id}/cancel", "post"],
  ["/jobs/{job_id}/result", "get"],
  ["/runs", "get"],
  ["/runs/{run_id}", "get"],
  ["/runs/{run_id}/errors", "get"],
  ["/coverage", "get"],
  ["/dataset/summary", "get"],
  ["/channels/{channel_id}/overview", "get"],
  ["/channels/{channel_id}/videos", "get"],
  ["/channels/{channel_id}/videos/count", "get"],
  ["/channels/{channel_id}/videos/top", "get"],
  ["/channels/{channel_id}/videos/sample", "post"],
  ["/videos/{video_id}", "get"],
  ["/videos/{video_id}/observations", "get"],
  ["/videos/{video_id}/raw", "get"],
  ["/videos/{video_id}/comments/threads", "get"],
  ["/videos/{video_id}/comments/sample", "post"],
  ["/videos/{video_id}/engagement", "get"],
  ["/videos/{video_id}/comments/percentiles", "get"],
  ["/videos/{video_id}/comments/velocity", "get"],
  ["/videos/{video_id}/comments", "get"],
  ["/videos/{video_id}/recommendations", "get"],
  ["/network/recommendations/summary", "get"],
  ["/network/recommendations/{video_id}", "get"],
  ["/network/graph", "get"],
  ["/network/scrape/video", "post"],
  ["/network/scrape/run", "post"],
  ["/network/scrape/channel", "post"],
  ["/research/variables", "get"],
  ["/research/operators", "get"],
  ["/research/query/preview", "post"],
  ["/research/query/resolve", "post"],
  ["/search", "get"],
];

describe("contract: generated-api types", () => {
  it("exposes every path the frontend calls", () => {
    for (const [path, method] of USED_PATHS) {
      const full = `${PATH}${path}`;
      const op = live.paths[full];
      expect(op, `missing path ${full}`).toBeDefined();
      expect(op?.[method], `missing ${method.toUpperCase()} ${full}`).toBeDefined();
    }
  });
});

describe("contract: orphaned services", () => {
  it("flags no orphans beyond the known/approved set", () => {
    const orphans = findOrphans();
    const known = new Set([
      "services\\api.ts:getVideoObservations",
      "services\\api.ts:getVideoRaw",
      "services\\api.ts:getChannelTopVideos",
      "services\\api.ts:getCommentThreads",
      "services\\api.ts:fetchAllPages",
      "services\\queries.ts:useCollect",
      "services\\queries.ts:useDatasetSummary",
      "services\\queries.ts:useCommentStats",
      "services\\queries.ts:useCreateDataset",
      "services\\queries.ts:useUpdateDataset",
      "services\\queries.ts:useDeleteDataset",
    ]);
    const unexpected = orphans.filter((o) => !known.has(o));
    expect(unexpected).toEqual([]);
  });
});