import { test, expect, type Page } from "@playwright/test";

const VALID_RUN = 'run_20260829_183703_4ca0fcc7';

async function gotoLab(page: Page, runId = VALID_RUN) {
  await page.addInitScript(
    (id: string) => {
      localStorage.setItem('ssr-lab-session', JSON.stringify({ runId: id, tab: 'graph' }));
    },
    runId,
  );
  await page.goto("http://127.0.0.1:3000/network/full");
  await page.waitForLoadState('load');
}

async function readyLab(page: Page) {
  await gotoLab(page);
  await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
}

async function openLabGraph(page: Page) {
  await readyLab(page);
  const graphTab = page.getByRole("tab", { name: "Graph" });
  await graphTab.waitFor({ state: "visible", timeout: 10000 });
  await graphTab.click();
  await expect(graphTab).toHaveAttribute("data-active", "", { timeout: 10000 });
  await expect(page.getByText("Projection")).toBeVisible({ timeout: 20000 });
}

test.describe("Lab Graph tab — multi-select channels/videos + never lose control", () => {
  test("selecting multiple channels keeps the graph and controls visible", async ({ page }) => {
    await openLabGraph(page);

    await page.locator('[data-slot="popover-trigger"]').filter({ hasText: "Channels" }).click();
    const pop = page.locator('[data-slot="popover-content"]');
    await expect(pop.getByPlaceholder("Search channels…")).toBeVisible({ timeout: 10000 });
    const labels = pop.locator("label");
    const labelCount = await labels.count();
    if (labelCount < 2) {
      await page.keyboard.press("Escape");
      await expect(page.getByText("Projection", { exact: true })).toBeVisible();
      return;
    }
    await expect(labels.first()).toBeVisible();
    await labels.nth(0).click();
    await labels.nth(1).click();
    await page.keyboard.press("Escape");

    await expect(page.getByText("Node list")).toBeVisible({ timeout: 60000 });
    await expect(page.getByText(/No network data for the current filters/)).toHaveCount(0);
    await expect(page.getByText("Projection", { exact: true })).toBeVisible();
    await expect(page.getByText("Layer", { exact: true })).toBeVisible();
  });

  test("empty video filter shows recovery and Clear all filters restores the graph", async ({ page }) => {
    await openLabGraph(page);

    // Wait for graph to finish loading before interacting with filters.
    const canvas = page.locator("canvas").first();
    await expect(canvas.or(page.getByText("Node list")).first()).toBeVisible({ timeout: 120000 });

    const videoInput = page.getByLabel("Add video IDs");
    await videoInput.fill("ZZZZ_does_not_exist");
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(page.getByText(/No network data for the current filters/)).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole("button", { name: "Clear all filters" }).first()).toBeVisible();

    await page.getByRole("button", { name: "Clear all filters" }).first().click();
    await expect(page.getByText(/No network data for the current filters/)).toHaveCount(0);
    await expect(page.getByText("Loading network graph…")).toBeHidden({ timeout: 60000 });
    await expect(canvas.or(page.getByText("Node list")).first()).toBeVisible({ timeout: 120000 });
  });

  test("Layers and Expansion tabs render without crashing", async ({ page }) => {
    await readyLab(page);
    await page.getByRole("tab", { name: "Layers" }).click();
    // Sparse runs may not have layers — verify tab rendered without crashing.
    const layerPanel = page.getByRole("tabpanel", { name: "Layers" });
    await expect(layerPanel).toBeVisible({ timeout: 60000 });
    await page.getByRole("tab", { name: "Expansion" }).click();
    const expansionPanel = page.getByRole("tabpanel", { name: "Expansion" });
    await expect(expansionPanel).toBeVisible({ timeout: 60000 });
  });
});
