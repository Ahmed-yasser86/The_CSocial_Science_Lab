import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

/**
 * Workspace bootstrap journey (W0/W1): pure chooser landing page,
 * provisioning a new workspace, entering it, the empty state of a fresh
 * database, reload persistence and the context-bar switcher. Requires the
 * UI (3000) and API (8000) to be running. Creating a workspace provisions
 * an additive Postgres database + data directory; nothing destructive.
 */
test.describe.serial("Workspace bootstrap", () => {
  test.setTimeout(180_000);

  const suffix = Date.now().toString(36);
  const workspaceName = `E2E Bootstrap ${suffix}`;

  async function openChooser(page: import("@playwright/test").Page) {
    await page.goto(`${BASE_URL}/`);
    await page
      .getByTestId("workspace-chooser")
      .waitFor({ state: "visible", timeout: 60_000 });
  }

  test("landing page is a pure workspace chooser", async ({ page }) => {
    await openChooser(page);

    // The legacy workspace must always be listed.
    await expect(page.getByTestId("workspace-card")).not.toHaveCount(0);
    await expect(
      page.getByTestId("workspace-card-name").filter({ hasText: "Legacy" }),
    ).toBeVisible();
    await expect(page.getByTestId("workspace-new-button")).toBeVisible();

    // The old global surfaces are gone from "/".
    await expect(page.getByTestId("welcome-panel")).toHaveCount(0);
    await expect(page.getByTestId("recent-runs-panel")).toHaveCount(0);
  });

  test("create workspace provisions, enters it and shows the empty state", async ({
    page,
  }) => {
    await openChooser(page);

    await page.getByTestId("workspace-new-button").click();
    await page
      .getByTestId("new-workspace-name")
      .waitFor({ state: "visible", timeout: 30_000 });
    await page.getByTestId("new-workspace-name").fill(workspaceName);
    await page.getByTestId("new-workspace-submit").click();

    // Provisioning a fresh DB can take a while; enter the workspace home.
    await page.waitForURL(/\/w$/, { timeout: 120_000 });
    await expect(page.getByTestId("workspace-home-title")).toHaveText(
      workspaceName,
      { timeout: 60_000 },
    );

    // A brand-new database has no runs yet.
    await expect(page.getByTestId("runs-empty-state")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("workspace-home-stats")).toContainText(
      "0 runs",
    );
  });

  test("active workspace persists across reload", async ({ page }) => {
    await page.goto(`${BASE_URL}/w`);
    await expect(page.getByTestId("workspace-home-title")).toHaveText(
      workspaceName,
      { timeout: 60_000 },
    );

    await page.reload();
    await expect(page.getByTestId("workspace-home-title")).toHaveText(
      workspaceName,
      { timeout: 60_000 },
    );
  });

  test("context-bar chip switches workspaces", async ({ page }) => {
    await page.goto(`${BASE_URL}/w`);
    await page
      .getByTestId("workspace-home-title")
      .filter({ hasText: workspaceName })
      .waitFor({ state: "visible", timeout: 60_000 });

    await page.getByTestId("workspace-chip").click();
    const menu = page.getByTestId("workspace-switcher");
    await expect(menu).toBeVisible();

    await menu
      .getByTestId("workspace-switch-option")
      .filter({ hasText: "Legacy" })
      .click();

    await expect(page.getByTestId("workspace-home-title")).toHaveText("Legacy", {
      timeout: 60_000,
    });
  });
});
