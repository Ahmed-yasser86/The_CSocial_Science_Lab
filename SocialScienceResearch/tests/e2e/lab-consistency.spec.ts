import { test, expect, type Page } from "@playwright/test";

async function openLab(page: Page) {
  await page.goto("http://127.0.0.1:3000/network/full", { waitUntil: "networkidle" });
  await page.getByText("NETWORK SLICE").waitFor({ timeout: 30000 });
}

test.describe("Lab consistency scenarios", () => {
  test("Matrices tab shows channel names, not just IDs", async ({ page }: { page: Page }) => {
    await openLab(page);
    await page.getByRole("tab", { name: "Matrices" }).click();
    // The community matrix header cells carry the channel id in `title` and the
    // human channel name as visible text.
    // The matrices payload is large on the production corpus; allow a
    // generous wait (react-query also retries transient proxy 5xx).
    const header = page.locator("table thead th[title^='UC']").first();
    // Cold path: first hit compiles the Matrices tab AND computes the
    // O(channels^2) overlap on the production corpus — allow a generous wait.
    await expect(header).toBeVisible({ timeout: 120000 });
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
    await expect(page.getByText(/No expansion actions yet/)).toHaveCount(0, { timeout: 20000 });
    await expect(page.getByText(/Open auto-project|Select expansion action/)).toBeVisible({
      timeout: 20000,
    });
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
    await expect(
      page.getByRole("button", { name: "Expand community matrix" }),
    ).toBeVisible({ timeout: 120000 });
    await page.getByRole("button", { name: "Expand community matrix" }).click();
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
    // pick two channels as the overlap scope
    const chips = page.locator("button[aria-pressed]");
    await chips.first().waitFor({ timeout: 20000 });
    await chips.nth(0).click();
    await chips.nth(1).click();
    // Scope to <main>: the top nav now also has an "Analyze" hub trigger and
    // strict mode forbids the ambiguity.
    await page
      .locator("main")
      .getByRole("button", { name: "Analyze" })
      .click();
    // Overlap computation streams a large corpus; allow a generous wait.
    await page.getByTestId("commenter-overlap-results").waitFor({ timeout: 45000 });
    // channels projection guarantees >= 2 entities so the panels render.
    // Scope to the results container: the outer Lab tab list also has a
    // "Channels" tab and strict mode forbids the ambiguity.
    await page
      .getByTestId("commenter-overlap-results")
      .getByRole("tab", { name: "Channels" })
      .click();
    await expect(
      page.getByRole("button", { name: "Expand Overlap heatmap" }),
    ).toBeVisible({ timeout: 20000 });
    await page.getByRole("button", { name: "Expand Overlap heatmap" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 20000 });
    await expect(dialog.getByText("Overlap heatmap")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0, { timeout: 20000 });

    // Top shared pairs entities resolve to clickable channel links (names, not raw ids)
    await page.getByRole("button", { name: "Expand Top shared pairs" }).click();
    const pairsDialog = page.getByRole("dialog");
    await expect(pairsDialog).toBeVisible({ timeout: 20000 });
    const channelLink = pairsDialog
      .locator('a[href*="channel_ids=UC"]')
      .first();
    await expect(channelLink).toBeVisible({ timeout: 20000 });
    await page.keyboard.press("Escape");
    await expect(pairsDialog).toHaveCount(0, { timeout: 20000 });
  });
});
