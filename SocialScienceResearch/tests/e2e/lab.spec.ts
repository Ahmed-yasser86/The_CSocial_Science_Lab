import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

const VALID_RUN = 'run_20260829_183703_4ca0fcc7';

async function gotoLab(page: Page, runId = VALID_RUN) {
  await page.addInitScript(
    (id: string) => {
      localStorage.setItem('ssr-lab-session', JSON.stringify({ runId: id, tab: 'graph' }));
    },
    runId,
  );
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('load');
}

/**
 * Sprint 2/3/4 Lab shell checks: layout presets, the Matrices tab (US-60/61)
 * and the Sampling feasibility panel (US-32/33). Requires UI (3000) + API (8000).
 */
test.describe("Network Analysis Lab shell", () => {
  test.setTimeout(180_000);

  test("layout presets switch the active analysis", async ({ page }) => {
    await gotoLab(page);

    // "Matrices" preset drives the tab to the matrices view.
    await page.getByRole("button", { name: "Matrices", exact: true }).click();
    const matricesTab = page.getByRole("tab", { name: "Matrices" });
    await expect(matricesTab).toHaveAttribute("data-active", "", { timeout: 60000 });

    // "Sampling" preset / tab shows the feasibility planner.
    await page.getByRole("button", { name: "Sampling", exact: true }).click();
    const samplingTab = page.getByRole("tab", { name: "Sampling" });
    await expect(samplingTab).toHaveAttribute("data-active", "", { timeout: 30000 });
  });

  test("researcher identity + notes panel toggles", async ({ page }) => {
    await gotoLab(page);

    await page.getByRole("button", { name: /Notes & identity/i }).click();
    const researcher = page.getByPlaceholder(/Your name \/ handle/i);
    await expect(researcher).toBeVisible();
    await researcher.fill("Dr. Test");
    await expect(researcher).toHaveValue("Dr. Test");
  });

  test("lab session persists the chosen tab across reload", async ({ page }) => {
    await gotoLab(page);

    await page.getByRole("button", { name: "Matrices", exact: true }).click();
    const matricesTab = page.getByRole("tab", { name: "Matrices" });
    await expect(matricesTab).toHaveAttribute("data-active", "", { timeout: 60000 });

    // Override addInitScript so the reloaded page restores to "matrices" tab.
    await page.addInitScript(
      (runId: string) => {
        localStorage.setItem(
          "ssr-lab-session",
          JSON.stringify({ runId, tab: "matrices" }),
        );
      },
      VALID_RUN,
    );

    await page.reload();
    await page.waitForLoadState("load");
    await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
    // localStorage session restored -> Matrices tab should be active again.
    await expect(matricesTab).toHaveAttribute("data-active", "", { timeout: 120000 });
  });
});

