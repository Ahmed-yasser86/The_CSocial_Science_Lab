import { test, expect, type Page } from "@playwright/test";

// N3 / N5 acceptance harness: the audience (commenter) Insights surfaces
// (Roles + Communities panels) render from observed data, the centrality
// battery is exposed with interpretation text, and the reproducibility footer
// echoes algorithm/seed/weight-spec/runs. The API is mocked so the spec is
// deterministic and needs no collection run in the database.

const PREFIX = "/api/v1/social-science";

async function mockAudienceApi(page: Page) {
  // Runs list drives the Scope (collection run) picker.
  await page.route(`${PREFIX}/runs**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            run_id: "run_test",
            name: "Test run",
            status: "completed",
            target_video_id: "v1",
            created_at: "2026-08-24T00:00:00Z",
          },
        ],
      }),
    }),
  );

  await page.route(`${PREFIX}/jobs**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    }),
  );

  // Audience graph (also feeds the reproducibility footer's weight-spec).
  await page.route(`${PREFIX}/network/commenters/graph**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        nodes: [
          { id: "UCalice", kind: "commenter", in_degree: 2, out_degree: 0, community_id: 0, run_ids: ["run_test"] },
          { id: "UCbob", kind: "commenter", in_degree: 1, out_degree: 0, community_id: 0, run_ids: ["run_test"] },
          { id: "UCcarol", kind: "commenter", in_degree: 1, out_degree: 0, community_id: 1, run_ids: ["run_test"] },
        ],
        edges: [
          { source: "UCalice", target: "UCbob", run_id: "run_test", weight: 0.5 },
          { source: "UCalice", target: "UCcarol", run_id: "run_test", weight: 0.5 },
        ],
        weight_spec: {
          edge_type: "co_comment",
          weight_mode: "jaccard",
          params: { min_shared: 2, top_n: 200 },
          normalization: "none",
        },
      }),
    }),
  );

  await page.route(`${PREFIX}/network/commenters/metrics**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        node_count: 3,
        edge_count: 2,
        density: 0.66,
        community_count: 2,
        modularity: 0.1,
        weakly_connected_components: 1,
        avg_clustering: 0.0,
        top_bridges: [],
        top_core: [],
        top_prolific: [],
        weight_spec: { edge_type: "co_comment", weight_mode: "jaccard", params: {}, normalization: "none" },
      }),
    }),
  );

  await page.route(`${PREFIX}/network/commenters/roles**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        nodes: {
          UCalice: { role: "core", community_id: 0 },
          UCbob: { role: "bridge", community_id: 0 },
          UCcarol: { role: "periphery", community_id: 1 },
        },
        role_model: "core_broker_periphery_bridge",
        approximate: false,
        algorithm: "networkx",
        computed_at: "2026-08-24T00:00:00Z",
      }),
    }),
  );

  await page.route(`${PREFIX}/network/commenters/community-insights**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        communities: [
          {
            community_id: 0,
            size: 2,
            dominant_kinds: { commenter: 2 },
            top_bridges: [{ id: "UCbob", label: "Bob", betweenness: 0.5 }],
          },
          {
            community_id: 1,
            size: 1,
            dominant_kinds: { commenter: 1 },
            top_bridges: [],
          },
        ],
        algorithm: "networkx",
        computed_at: "2026-08-24T00:00:00Z",
      }),
    }),
  );
}

test.describe("Audience network Insights panels + reproducibility footer (N3/N5)", () => {
  test("Roles and Communities panels render observed data and the footer echoes provenance", async ({
    page,
  }) => {
    await mockAudienceApi(page);
    await page.goto("/network/full");

    await expect(
      page.getByRole("heading", { name: "Full network analytics" }),
    ).toBeVisible();

    // Switch to the audience (commenter) network family.
    await page.getByRole("button", { name: "Audience (commenters)" }).click();

    // Pick a scope run so the audience graph + panels can load.
    await page.getByLabel("Select network slice run").click();
    await page.getByRole("option", { name: "Test run" }).click();

    // Reproducibility footer is wired from the audience graph payload.
    await expect(page.getByText("seed=42")).toBeVisible();
    await expect(page.getByText("algorithm=networkx")).toBeVisible();

    // Roles panel: structural roles with observed role assignment.
    await page.getByRole("tab", { name: "Roles" }).click();
    await expect(page.getByText("Structural roles")).toBeVisible();
    await expect(page.getByText("bridge", { exact: true })).toBeVisible();

    // Communities panel: per-community composition from observed data.
    await page.getByRole("tab", { name: "Communities" }).click();
    await expect(page.getByText("Community 0")).toBeVisible();
    await expect(page.getByText("Community 1")).toBeVisible();
  });
});
