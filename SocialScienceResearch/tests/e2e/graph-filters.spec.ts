import { test, expect, type Page } from "@playwright/test";

async function readyLab(page: Page) {
  await page.goto("http://127.0.0.1:3000/network/full", { waitUntil: "networkidle" });
  await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
}

async function openLabGraph(page: Page) {
  await readyLab(page);
  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByText("Projection", { exact: true })).toBeVisible({ timeout: 20000 });
}

test.describe("Lab Graph tab — multi-select channels/videos + never lose control", () => {
  test("selecting multiple channels keeps the graph and controls visible", async ({ page }) => {
    await openLabGraph(page);

    await page.locator('[data-slot="popover-trigger"]').filter({ hasText: "Channels" }).click();
    const pop = page.locator('[data-slot="popover-content"]');
    await expect(pop.getByPlaceholder("Search channels…")).toBeVisible({ timeout: 10000 });
    const labels = pop.locator("label");
    await expect(labels.first()).toBeVisible();
    await labels.nth(0).click();
    await labels.nth(1).click();
    await page.keyboard.press("Escape");

    await expect(page.getByText("Node list")).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/No network data for the current filters/)).toHaveCount(0);
    await expect(page.getByText("Projection", { exact: true })).toBeVisible();
    await expect(page.getByText("Layer", { exact: true })).toBeVisible();
  });

  test("empty video filter shows recovery and Clear all filters restores the graph", async ({ page }) => {
    await openLabGraph(page);

    await expect(page.getByText("Node list")).toBeVisible({ timeout: 30000 });

    const videoInput = page.getByLabel("Add video IDs");
    await videoInput.fill("ZZZZ_does_not_exist");
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(page.getByText(/No network data for the current filters/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Clear all filters" }).first()).toBeVisible();
    await expect(page.getByText("Projection", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Clear all filters" }).first().click();
    await expect(page.getByText(/No network data for the current filters/)).toHaveCount(0);
    await expect(page.getByText("Node list")).toBeVisible({ timeout: 30000 });
  });

  test("Layers and Expansion tabs render without crashing", async ({ page }) => {
    await readyLab(page);
    await page.getByRole("tab", { name: "Layers" }).click();
    await expect(page.getByText("Layer 0 (seed)")).toBeVisible({ timeout: 20000 });
    await expect(page.getByText(/Layer .* graph/)).toBeVisible();
    await page.getByRole("tab", { name: "Expansion" }).click();
    // default selection must be the newest, populated action (ordering fix),
    // not the empty seed -> the populated action shows an auto-project link.
    await expect(
      page.getByText(/Open auto-project|Select expansion action/),
    ).toBeVisible({ timeout: 20000 });
    await expect(page.getByText(/No expansion actions yet/)).toHaveCount(0);
  });
});
