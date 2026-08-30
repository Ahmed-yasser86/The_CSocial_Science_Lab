import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

/**
 * End-to-end coverage of the Network Analysis Lab (/network/full): mimics a
 * researcher walking every tab, verifies data actually renders (no empty/broken
 * states), and confirms a stale persisted run filter is auto-cleared so the
 * graph never silently shows "No network to render".
 */
test.describe("Network Analysis Lab - researcher journey", () => {
  test.setTimeout(300_000);

  async function openLabFresh(page: Page) {
    await page.goto(`${BASE_URL}/network/full`);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForLoadState("load");
  }

  async function clickTab(page: Page, name: string) {
    await page.getByRole("tab", { name, exact: true }).click();
    await page.waitForTimeout(1500);
  }

  // Each tab is checked from a fresh load so a single heavy query on one tab
  // can't starve another (the dev BE is a single process). This still mirrors a
  // researcher opening each analysis view.
  async function expectTabContent(
    page: Page,
    name: string,
    matcher: RegExp,
    timeout = 30000,
  ) {
    await openLabFresh(page);
    await clickTab(page, name);
    await expect(page.getByText(matcher).first()).toBeVisible({ timeout });
  }

  test("every tab renders real content for the full network", async ({ page }) => {
    // Graph (core bug): must show rendered nodes, not "No network to render".
    await expectTabContent(page, "Graph", /Showing .+ of .+ nodes/);
    await openLabFresh(page);
    await expect(page.getByText("No network to render")).toHaveCount(0);

    await expectTabContent(page, "Metrics", /Degree distribution/);
    await expectTabContent(
      page,
      "Insights",
      /Density|Connectivity|Reciprocity|Communities|Scrape coverage|Isolated nodes/,
    );
    await expectTabContent(page, "Temporal", /Runs to compare/);
    await expectTabContent(page, "Edges", /Source video/);
    await expectTabContent(page, "Layers", /Layer 0/);
    await expectTabContent(page, "Commenters", /Scope/);
    await expectTabContent(
      page,
      "Matrices",
      /Community matrix \(shared commenters\)/,
      60000,
    );
    await expectTabContent(
      page,
      "Sampling",
      /Sampling feasibility \(US-32\/33\)/,
    );
    await expectTabContent(page, "Expansion", /Action graph|Per-video stats/);

    // No Next.js 404 anywhere.
    await openLabFresh(page);
    await expect(page.getByText("This page could not be found")).toHaveCount(0);
  });

  test("stale persisted run filter is auto-cleared so the graph renders", async ({
    page,
  }) => {
    // Simulate a previously-saved session pointing at a run that no longer
    // exists (the reported "No network to render" symptom).
    await page.addInitScript(() => {
      localStorage.setItem(
        "ssr-lab-session",
        JSON.stringify({ runId: "bogus_run_xyz", tab: "graph" }),
      );
    });
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState("load");

    // The invalid run must be dropped and the full graph shown instead.
    await expect(
      page.getByText(/Showing .+ of .+ nodes/),
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByText("No network to render")).toHaveCount(0);
    // The persisted (now cleared) run should not be re-selected.
    await expect(page.getByText("bogus_run_xyz")).toHaveCount(0);
  });

  test("graph projection toggle renders the channel graph", async ({ page }) => {
    await openLabFresh(page);
    await clickTab(page, "Graph");
    await expect(
      page.getByText(/Showing .+ of .+ nodes/),
    ).toBeVisible({ timeout: 30000 });

    await page
      .getByRole("combobox", { name: "Select graph projection" })
      .click();
    await page.getByRole("option", { name: "Channel graph" }).click();
    await page.waitForLoadState("load");
    await expect(
      page.getByText(/Showing .+ of .+ nodes/),
    ).toBeVisible({ timeout: 30000 });
  });

  test("no hydration mismatch errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("pageerror", (err) => errors.push(err.message));
    await openLabFresh(page);
    await clickTab(page, "Graph");
    await expect(
      page.getByText(/Showing .+ of .+ nodes/),
    ).toBeVisible({ timeout: 30000 });
    expect(
      errors.filter((e) => /hydration/i.test(e)),
    ).toEqual([]);
  });
});

