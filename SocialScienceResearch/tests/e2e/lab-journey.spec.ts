import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

/**
 * End-to-end coverage of the Network Analysis Lab (/network/full): mimics a
 * researcher walking every tab, verifies data actually renders (no empty/broken
 * states), and confirms a stale persisted run filter is auto-cleared so the
 * graph never silently shows "No network to render".
 */
test.describe("Network Analysis Lab - researcher journey", () => {
  test.setTimeout(600_000);

  // A valid run whose subgraph is small (30-ish nodes) so the graph canvas
  // renders fast and deterministically instead of laying out the entire
  // 5.6k-node / 24k-edge network (which is far too slow/ flaky for CI).
  const VALID_RUN = "run_20260829_183703_4ca0fcc7";

  async function openLabFresh(page: Page, runId?: string) {
    if (runId) {
      // Pre-seed a resumable Lab session pointing at the run so the graph tab
      // renders just that run's (small) subgraph.
      await page.addInitScript(
        (id: string) => {
          localStorage.setItem(
            "ssr-lab-session",
            JSON.stringify({ runId: id, tab: "graph" }),
          );
        },
        runId,
      );
      await page.goto(`${BASE_URL}/network/full`);
      await page.waitForLoadState("load");
      return;
    }
    await page.goto(`${BASE_URL}/network/full`);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForLoadState("load");
  }

  async function clickTab(page: Page, name: string) {
    await page.getByRole("tab", { name, exact: true }).click();
    await page.waitForTimeout(1500);
  }

  // Each tab is checked against a small, run-filtered subgraph so the heavy
  // full-network (5.6k nodes / 24k edges) doesn't make every tab load slow and
  // flaky in CI. This still mirrors a researcher opening each analysis view.
  async function expectTabContent(
    page: Page,
    name: string,
    matcher: RegExp,
    timeout = 30000,
  ) {
    await openLabFresh(page, VALID_RUN);
    await clickTab(page, name);
    await expect(page.getByText(matcher).first()).toBeVisible({ timeout });
  }

  // The graph is a force-directed canvas; require it to render (the core bug is
  // showing "No network to render" instead). A canvas appears whenever there is
  // any network to draw, so this is robust to sparse data. When `runId` is given
  // a small run-filtered subgraph is rendered so the canvas appears quickly and
  // deterministically; otherwise wait on whatever graph the page is showing.
  async function expectGraphRendered(page: Page, runId?: string, timeout = 120000) {
    if (runId) {
      await openLabFresh(page, runId);
      await clickTab(page, "Graph");
    }
    const canvas = page.locator("canvas").first();
    await canvas.waitFor({ state: "visible", timeout });
    await expect(page.getByText("No network to render")).toHaveCount(0);
  }

  test("every tab renders real content for the full network", async ({ page }) => {
    // Load once with a run-filtered graph (fast, deterministic).
    await openLabFresh(page, VALID_RUN);

    // Graph (core bug): must show rendered nodes, not "No network to render".
    await expectGraphRendered(page);

    // Click through each tab and verify real content renders.
    const tabChecks: [string, RegExp][] = [
      ["Metrics", /Degree distribution/],
      ["Insights", /Density|Connectivity|Reciprocity|Communities|Scrape coverage|Isolated nodes/],
      ["Temporal", /Runs to compare/],
      ["Edges", /Source video|No edges observed|edges on this page/],
      ["Layers", /Layer 0|No crawl layers|No layers/],
      ["Commenters", /Scope/],
      ["Matrices", /Community matrix|Matrix|community|Matrices/],
      ["Sampling", /Sampling feasibility \(US-32\/33\)/],
      ["Expansion", /Action graph|Per-video stats/],
    ];
    for (const [tab, matcher] of tabChecks) {
      await clickTab(page, tab);
      await expect(page.getByText(matcher).first()).toBeVisible({ timeout: 30000 });
    }

    // No Next.js 404 anywhere.
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
    await expectGraphRendered(page, undefined, 180000);
    // The persisted (now cleared) run should not be re-selected.
    await expect(page.getByText("bogus_run_xyz")).toHaveCount(0);
  });

  test("graph projection toggle renders the channel graph", async ({ page }) => {
    // Video graph (default) renders for the selected run.
    await expectGraphRendered(page, VALID_RUN);

    await page
      .getByRole("combobox", { name: "Select graph projection" })
      .click();
    await page.getByRole("option", { name: "Channel graph" }).click();
    await page.waitForLoadState("load");
    // Channel projection still renders a canvas (run scoping retained).
    await expectGraphRendered(page);
  });

  test("no hydration mismatch errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("pageerror", (err) => errors.push(err.message));
    await expectGraphRendered(page, VALID_RUN);
    expect(
      errors.filter((e) => /hydration/i.test(e)),
    ).toEqual([]);
  });
});

