import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "fs";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1/social-science";

const VALID_RUN = 'run_20260829_183703_4ca0fcc7';

let wsId = "";

test.beforeAll(async ({ request }) => {
  try {
    const resp = await request.get(`${API}/workspaces`);
    if (resp.ok()) {
      const workspaces = (await resp.json()).items ?? [];
      if (workspaces.length) {
        wsId = workspaces[0].workspace_id;
        return;
      }
    }
  } catch {
    /* fall through */
  }
  wsId = "ws_e2e_export_nav";
});

async function gotoLab(page: Page, runId = VALID_RUN) {
  await page.addInitScript(
    ([runIdArg, wsIdArg]: string[]) => {
      localStorage.setItem('ssr-lab-session', JSON.stringify({ runId: runIdArg, tab: 'graph' }));
      localStorage.setItem('ssr-active-workspace', JSON.stringify({ workspaceId: wsIdArg, updatedAt: new Date().toISOString() }));
    },
    [runId, wsId] as unknown as string[],
  );
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('load');
}

/**
 * Connects the previously orphaned surfaces (Lab / Compare / Query / Data) and
 * the "Export project to Excel" button introduced in Sprint 0/1 of the unified
 * journey work. Requires the UI (3000) and API (8000) to be running.
 */
test.describe("Unified journey connectors", () => {
  test.setTimeout(180_000);

  // The navbar groups its links into hub dropdowns (Analyze ▾ / Data ▾), so
  // each connector opens the hub menu first, then clicks the child item.
  const connectors: Array<[string, string, string]> = [
    ["Analyze", "Lab", "/network/full"],
    ["Analyze", "Compare", "/compare"],
    ["Analyze", "Query", "/query"],
    ["Data", "Coverage", "/data"],
  ];

  for (const [hub, item, path] of connectors) {
    test(`top-nav ${hub} ▾ "${item}" opens ${path} without a 404`, async ({ page }) => {
      await gotoLab(page);

      const hubButton = page.getByRole("button", { name: hub, exact: true });
      await hubButton.waitFor({ state: "visible", timeout: 30_000 });
      await hubButton.click();
      const menuItem = page.getByRole("menuitem", { name: item });
      await menuItem.waitFor({ state: "visible", timeout: 30_000 });
      await menuItem.click();
      await page.waitForLoadState("load");

      await expect(page).toHaveURL(new RegExp(`${path.replace(/\//g, "\\/")}(\\/|$)`));
      await expect(page.getByText("This page could not be found")).toHaveCount(0);
    });
  }

  test("project detail exports a multi-sheet Excel workbook", async ({ request, page }) => {
    // Guarantee a project exists without depending on seeded data.
    const list = await request.get(`${API}/projects`);
    let projectId: string;
    if ((await list.json()).items?.length) {
      projectId = (await list.json()).items[0].project_id;
    } else {
      const created = await request.post(`${API}/projects`, {
        data: {
          name: "e2e export project",
          targets: [{ kind: "channel", url: "https://www.youtube.com/@UC_e2e" }],
        },
      });
      expect(created.ok()).toBeTruthy();
      projectId = (await created.json()).project_id;
    }

    await page.goto(`${BASE_URL}/projects/${projectId}`);
    await page.waitForLoadState("load");

    const exportButton = page.getByRole("button", { name: /Export project to Excel/i });
    await exportButton.waitFor({ state: "visible", timeout: 30000 });

    const downloadPromise = page.waitForEvent("download", { timeout: 60000 });
    await exportButton.click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    const localPath = await download.path();
    expect(localPath).toBeTruthy();
    // openpyxl-free sanity check: xlsx is a non-empty zip.
    const buf = readFileSync(localPath!);
    expect(buf.length).toBeGreaterThan(0);
    expect(buf.slice(0, 2).toString("latin1")).toBe("PK");
  });
});

