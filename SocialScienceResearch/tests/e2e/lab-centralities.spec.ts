import { test, expect, type Page } from "@playwright/test";

async function openMetricsTab(page: Page) {
  await page.goto("http://127.0.0.1:3000/network/full", { waitUntil: "load" });
  await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
  await page.getByRole("tab", { name: "Metrics" }).click();
  await expect(page.getByText("Node centralities")).toBeVisible({ timeout: 20000 });
}

test.describe("Lab Metrics tab — node centralities (N0)", () => {
  test("renders a centralities table with centrality columns", async ({ page }) => {
    await openMetricsTab(page);

    const table = page.getByRole("table", { name: "Node centralities" });
    await expect(table).toBeVisible({ timeout: 20000 });

    // Header must expose the core centrality measures computed by the service.
    await expect(table.getByRole("columnheader", { name: "Degree" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Closeness" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Eigenvector" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Betweenness" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "PageRank" })).toBeVisible();

    // At least one node row is present in a populated corpus.
    await expect(table.locator("tbody tr").first()).toBeVisible({ timeout: 20000 });
  });
});

