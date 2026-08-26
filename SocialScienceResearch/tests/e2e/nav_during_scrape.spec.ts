import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";

/**
 * Nav-during-scrape regression E2E (fully MOCKED backend).
 *
 * While a recommendation scrape runs, the jobs tray detail dialog must NOT
 * mark the whole app shell inert/aria-hidden (Base UI modal behaviour used
 * to make the navbar disappear for the entire crawl). The dialog is now
 * non-modal, so the nav stays visible and clickable while a job runs.
 */

const JOB_ID = "job_e2e_nav";
const WS_ID = "ws_mock";
const WS_NAME = "Mock Workspace";

function runningJob() {
  return {
    job_id: JOB_ID,
    kind: "recommendation",
    status: "running",
    created_at: new Date().toISOString(),
    progress: {
      stage: "recommendation/batch/progress",
      discovered: 4,
      succeeded: 2,
      failed: 0,
      message: "Scraping recommendations",
    },
    cancel_requested: false,
    runs: [],
  };
}

async function mockBackend(page: Page) {
  await page.route("**/session/context", async (route) =>
    route.fulfill({
      json: {
        active_workspace_id: WS_ID,
        active_project_id: null,
        active_dataset_id: null,
        updated_at: new Date().toISOString(),
      },
    }),
  );
  await page.route(`**/workspaces/${WS_ID}`, async (route) =>
    route.fulfill({
      json: {
        workspace_id: WS_ID,
        name: WS_NAME,
        research_topic: null,
        is_legacy: false,
        active: true,
        created_at: new Date().toISOString(),
        last_opened_at: new Date().toISOString(),
        stats: { runs: 0, videos: 0, channels: 0, comments: 0, datasets: 0, samples: 0, projects: 0 },
      },
    }),
  );
  await page.route("**/jobs?**", async (route) =>
    route.fulfill({
      json: {
        items: [runningJob()],
        next_cursor: null,
        has_more: false,
        total: 1,
      },
    }),
  );
  await page.route(/\/jobs\/job_e2e_nav\/stream$/, async (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      // One progress event then stay open (running job).
      body: `data: ${JSON.stringify(runningJob())}\n\n`,
    }),
  );
  await page.route(/\/jobs\/job_e2e_nav$/, async (route) =>
    route.fulfill({ json: runningJob() }),
  );
}

async function gotoWorkspacePage(page: Page, path: string) {
  await page.addInitScript(
    ([id]) => {
      window.localStorage.setItem(
        "ssr-active-workspace",
        JSON.stringify({ workspaceId: id, updatedAt: new Date().toISOString() }),
      );
    },
    [WS_ID] as unknown as string[],
  );
  await page.goto(`${BASE_URL}${path}`);
}

test.describe("Nav stays usable during scrapes", () => {
  test.setTimeout(120_000);

  test("navbar stays visible and clickable while a recommendation job runs", async ({ page }) => {
    await mockBackend(page);
    await gotoWorkspacePage(page, "/network/echo-chambers");

    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav).toBeVisible();

    // The app shell must never be marked inert by a background job.
    const shell = page.locator("div.flex.min-h-screen");
    await expect(shell).toBeVisible();
    await expect(shell).not.toHaveAttribute("aria-hidden", /true/i);
    await expect(shell).not.toHaveAttribute("data-base-ui-inert", /.+/);

    // Nav links actually navigate while the job runs.
    await page.getByRole("link", { name: "Docs" }).click();
    await expect(page).toHaveURL(/\/docs$/);
    await expect(nav).toBeVisible();
  });

  test("job detail dialog does not inert the shell; nav works with it open", async ({ page }) => {
    await mockBackend(page);
    await gotoWorkspacePage(page, "/network/echo-chambers");

    // Open the jobs tray and the job's detail dialog.
    await page.getByRole("button", { name: "Jobs tray" }).click();
    await page.getByTitle("Open job details").first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Non-modal dialog: no backdrop inerting the app shell.
    const shell = page.locator("div.flex.min-h-screen");
    await expect(shell).not.toHaveAttribute("aria-hidden", /true/i);
    await expect(shell).not.toHaveAttribute("data-base-ui-inert", /.+/);

    // The navbar remains interactive WITH the dialog open.
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav).toBeVisible();
    await page.getByRole("link", { name: "Collect" }).click();
    await expect(page).toHaveURL(/\/collect$/);
    await expect(nav).toBeVisible();
  });
});
