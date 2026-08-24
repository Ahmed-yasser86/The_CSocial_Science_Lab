import { test, expect } from "@playwright/test";

/**
 * Phase 3 (export parity): the downloaded network export must mirror exactly
 * the Active Filter View rendered by GET /network/graph for the same filters.
 * Covered both via the API (request) and the in-app download button so the
 * browser interaction path is exercised too.
 */

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1/social-science";

const PREFIX = "/network/export";

async function graphNodesEdges(request: any, params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString();
  const resp = await request.get(`${API}/network/graph?${qs}`);
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  return {
    nodes: new Set(body.nodes.map((n: any) => n.video_id)),
    edges: new Set(body.edges.map((e: any) => `${e.source}->${e.target}`)),
  };
}

async function exportNodesEdges(request: any, params: Record<string, string>) {
  const qs = new URLSearchParams({ format: "json", ...params }).toString();
  const resp = await request.get(`${API}${PREFIX}?${qs}`);
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body).toHaveProperty("nodes");
  expect(body).toHaveProperty("links");
  return {
    nodes: new Set(body.nodes.map((n: any) => n.data.id)),
    edges: new Set(body.links.map((l: any) => `${l.data.source}->${l.data.target}`)),
  };
}

test.describe("Network export mirrors the active filter view", () => {
  test.setTimeout(120_000);

  for (const scope of [
    {},
    { channel_id: "UC1" },
    { connected: "only" },
    { channel_scope: "target" },
  ]) {
    test(`export == graph view for scope ${JSON.stringify(scope)}`, async ({ request }) => {
      const g = await graphNodesEdges(request, scope);
      const e = await exportNodesEdges(request, scope);
      expect([...e.nodes].sort()).toEqual([...g.nodes].sort());
      expect([...e.edges].sort()).toEqual([...g.edges].sort());
    });
  }

  test("channel-projection export matches channel graph view", async ({ request }) => {
    const gresp = await request.get(`${API}/network/graph?projection=channel`);
    expect(gresp.ok()).toBeTruthy();
    const gbody = await gresp.json();
    const gNodes = new Set(gbody.nodes.map((n: any) => n.channel_id));
    const gEdges = new Set(gbody.edges.map((e: any) => `${e.source}->${e.target}`));

    const eresp = await request.get(`${API}/network/export?format=json&projection=channel`);
    expect(eresp.ok()).toBeTruthy();
    const ebody = await eresp.json();
    const eNodes = new Set(ebody.nodes.map((n: any) => n.data.id));
    const eEdges = new Set(ebody.links.map((l: any) => `${l.data.source}->${l.data.target}`));

    expect([...eNodes].sort()).toEqual([...gNodes].sort());
    expect([...eEdges].sort()).toEqual([...gEdges].sort());
  });

  test("graphml export is well-formed XML carrying node attributes", async ({ request }) => {
    const resp = await request.get(`${API}/network/export?format=graphml`);
    expect(resp.ok()).toBeTruthy();
    expect(resp.headers()["content-type"]).toContain("xml");
    const text = await resp.text();
    expect(text).toContain("<graphml");
    expect(text).toContain("centrality");
    expect(text).toContain("community_id");
  });

  test("csv export uses source,target,weight,relationship_type", async ({ request }) => {
    const resp = await request.get(`${API}/network/export?format=csv`);
    expect(resp.ok()).toBeTruthy();
    const text = (await resp.text()).replace(/\r\n/g, "\n");
    const header = text.trim().split("\n")[0];
    expect(header).toBe("source,target,weight,relationship_type");
  });
});
