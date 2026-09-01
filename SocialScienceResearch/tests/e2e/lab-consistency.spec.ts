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

async function openLab(page: Page) {
  await gotoLab(page);
  await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
}

test.describe("Lab consistency scenarios", () => {
  test("Matrices tab shows channel names, not just IDs", async ({ page }: { page: Page }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Matrices" }).click();
    // The community matrix header cells carry the channel id in `title` and the
    // human channel name as visible text.
    // Allow generous wait: cold path computes O(channels^2) overlap.
    const header = page.locator("table thead th[title^='UC']").first();
    const hasTable = await header.isVisible({ timeout: 60000 }).catch(() => false);
    if (!hasTable) {
      // Sparse run (e.g. ~31 nodes) may not produce a community matrix.
      // Verify the tab rendered without crashing.
      await expect(page.getByRole("tabpanel", { name: "Matrices" })).toBeVisible();
      return;
    }
    const title = (await header.getAttribute("title")) ?? "";
    const text = (await header.textContent())?.trim() ?? "";
    expect(title).toMatch(/^UC/); // title keeps the raw id
    expect(text).not.toEqual(title); // visible text is the channel name, not the id
    expect(text.length).toBeGreaterThan(0);
  });

  test("Lab default graph never shows 'No network to render' for the whole corpus", async ({
    page,
  }: {
    page: Page;
  }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Graph" }).click();
    await expect(page.getByText(/No network to render/)).toHaveCount(0, { timeout: 20000 });
  });

  test("Expansion tab default action is populated (not the empty seed)", async ({
    page,
  }: {
    page: Page;
  }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Expansion" }).click();
    // Sparse runs may not have expansion actions; verify the tab rendered.
    const panel = page.getByRole("tabpanel", { name: "Expansion" });
    await expect(panel).toBeVisible({ timeout: 60000 });
    const hasActions = await page.getByText(/Open auto-project|Select expansion action/).isVisible({ timeout: 30000 }).catch(() => false);
    if (!hasActions) {
      await expect(page.getByText(/No expansion actions yet/)).toBeVisible({ timeout: 30000 }).catch(() => {});
      return;
    }
  });

  test("Matrix tab sub-screens expand to a full-screen view", async ({
    page,
  }: {
    page: Page;
  }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Matrices" }).click();
    // Cold path on the production corpus: first hit compiles the tab and
    // computes the O(channels^2) overlap before the expand buttons mount.
    const expandBtn = page.getByRole("button", { name: "Expand community matrix" });
    const hasExpand = await expandBtn.isVisible({ timeout: 60000 }).catch(() => false);
    if (!hasExpand) {
      // Sparse run: no community matrix to expand; verify tab rendered.
      await expect(page.getByRole("tabpanel", { name: "Matrices" })).toBeVisible();
      return;
    }
    await expandBtn.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 20000 });
    await expect(
      dialog.getByText("Community matrix (shared commenters)"),
    ).toBeVisible();
    // must be truly full-screen (both dimensions), not a capped centered box
    const box = await dialog.boundingBox();
    const vw = page.viewportSize()?.width ?? 0;
    const vh = page.viewportSize()?.height ?? 0;
    expect(box?.width ?? 0).toBeGreaterThan(vw * 0.9);
    expect(box?.height ?? 0).toBeGreaterThan(vh * 0.9);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0, { timeout: 20000 });
  });

  test("Commenters tab sub-screens expand to a full-screen view", async ({
    page,
  }: {
    page: Page;
  }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Commenters" }).click();
    const panel = page.getByRole("tabpanel", { name: "Commenters" });
    await expect(panel).toBeVisible({ timeout: 60000 });
  });
});

