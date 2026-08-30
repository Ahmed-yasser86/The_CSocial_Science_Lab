import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

/**
 * Sprint 2/3/4 Lab shell checks: layout presets, the Matrices tab (US-60/61)
 * and the Sampling feasibility panel (US-32/33). Requires UI (3000) + API (8000).
 */
test.describe("Network Analysis Lab shell", () => {
  test.setTimeout(180_000);

  test("layout presets switch the active analysis", async ({ page }) => {
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState("load");

    // "Matrices" preset drives the tab to the matrices view. The matrices
    // query is heavy on the production corpus; allow a generous wait.
    await page.getByRole("button", { name: "Matrices", exact: true }).click();
    await expect(
      page.getByText("Community matrix (shared commenters)").first(),
    ).toBeVisible({ timeout: 60000 });

    // "Sampling" preset / tab shows the feasibility planner.
    await page.getByRole("button", { name: "Sampling", exact: true }).click();
    await expect(
      page.getByText("Sampling feasibility (US-32/33)"),
    ).toBeVisible({ timeout: 30000 });
  });

  test("researcher identity + notes panel toggles", async ({ page }) => {
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState("load");

    await page.getByRole("button", { name: /Notes & identity/i }).click();
    const researcher = page.getByPlaceholder(/Your name \/ handle/i);
    await expect(researcher).toBeVisible();
    await researcher.fill("Dr. Test");
    await expect(researcher).toHaveValue("Dr. Test");
  });

  test("lab session persists the chosen tab across reload", async ({ page }) => {
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState("load");

    await page.getByRole("button", { name: "Matrices", exact: true }).click();
    await expect(
      page.getByText("Community matrix (shared commenters)").first(),
    ).toBeVisible({ timeout: 60000 });

    await page.reload();
    await page.waitForLoadState("load");
    // localStorage session restored -> still on the Matrices view.
    await expect(
      page.getByText("Community matrix (shared commenters)").first(),
    ).toBeVisible({ timeout: 60000 });
  });
});

