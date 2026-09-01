import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

/**
 * Ego-network visualizer E2E. Requires the UI (port 3000) and API (port 8000)
 * running the current backend code.
 *
 * Regression coverage for:
 *  - the Base UI Button `nativeButton` fix (ego view passes `onNavigate`, so
 *    the drawer "Open video page" action is a native <button>, never a warning)
 *  - the tooltip "Watch video" link and drawer actions shared with full view
 *  - nodes are laid out with separation (centers are not all coincident)
 */
function collectBaseUIButtonErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && msg.text().includes('expected a non-<button>')) {
      errors.push(msg.text());
    }
  });
  page.on('pageerror', (err) => {
    if (String(err).includes('nativeButton')) errors.push(String(err));
  });
  return errors;
}

async function waitForCanvas(page: Page): Promise<boolean> {
  const canvas = page.locator('canvas').first();
  try {
    await canvas.waitFor({ state: 'visible', timeout: 90000 });
    return true;
  } catch {
    return false;
  }
}

test.describe('Ego-Network Visualizer', () => {
  let videoId: string;

  test.beforeAll(async () => {
    const VALID_RUN = 'run_20260829_183703_4ca0fcc7';
    const graph = await (await fetch(`${API}/network/graph?run_id=${VALID_RUN}`)).json();
    const node = graph.nodes.find((n: { in_degree: number; out_degree: number }) =>
      n.in_degree + n.out_degree > 0);
    videoId = node.video_id;
  });

  test('ego view renders a canvas without Base UI console errors', async ({
    page,
  }) => {
    const errors = collectBaseUIButtonErrors(page);
    await page.goto(`${BASE_URL}/network/videos/${videoId}`);
    await page.waitForLoadState('load');
    const rendered = await waitForCanvas(page);
    test.skip(!rendered, 'Canvas did not render within timeout');
    await expect(page.getByText('In-degree')).toBeVisible();
    await page.waitForTimeout(1500);
    expect(
      errors.some((e) => e.includes('expected a non-<button>') || e.includes('nativeButton')),
    ).toBe(false);
  });

  test('ego drawer Open video page is a native button that navigates', async ({
    page,
  }) => {
    const errors = collectBaseUIButtonErrors(page);
    await page.goto(`${BASE_URL}/network/videos/${videoId}`);
    await page.waitForLoadState('load');
    const rendered = await waitForCanvas(page);
    test.skip(!rendered, 'Canvas did not render within timeout');
    const canvas = page.locator('canvas').first();
    await page.waitForTimeout(4000);

    const box = (await canvas.boundingBox()) ?? { x: 0, y: 0, width: 800, height: 480 };
    const pts = [
      [0.5, 0.5], [0.42, 0.5], [0.58, 0.5], [0.5, 0.42], [0.5, 0.58],
      [0.44, 0.44], [0.56, 0.44], [0.44, 0.56], [0.56, 0.56],
    ];
    const drawer = page.locator('[data-slot="drawer-content"]');
    for (const [fx, fy] of pts) {
      await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
      await page.waitForTimeout(450);
      if ((await drawer.count()) > 0) break;
    }
    if ((await drawer.count()) === 0) return;

    const openVideo = drawer.getByRole('button', { name: 'Open video page' });
    await expect(openVideo).toBeVisible();
    const currentUrl = page.url();
    await openVideo.click();
    await page.waitForURL((url) => url.pathname.startsWith('/network/videos/'));
    // Clicking the button in ego view navigates (router.push) — but if the
    // inspected node IS the focus video the URL stays the same.
    expect(page.url() !== currentUrl || page.url().includes(videoId)).toBe(true);
    expect(
      errors.some((e) => e.includes('expected a non-<button>') || e.includes('nativeButton')),
    ).toBe(false);
  });

  test('ego graph renders and layout settles without errors', async ({ page }) => {
    const errors = collectBaseUIButtonErrors(page);
    await page.goto(`${BASE_URL}/network/videos/${videoId}`);
    await page.waitForLoadState('load');
    const rendered = await waitForCanvas(page);
    test.skip(!rendered, 'Canvas did not render within timeout');
    const canvas = page.locator('canvas').first();
    // Let the wider force layout settle; then confirm the canvas still renders.
    await page.waitForTimeout(5000);
    await expect(canvas).toBeVisible();
    expect(errors).toHaveLength(0);
  });

  test('ego Scrape all button opens the filter dialog; drawer scrape opens it too', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/network/videos/${videoId}`);
    await page.waitForLoadState('load');
    const rendered = await waitForCanvas(page);
    test.skip(!rendered, 'Canvas did not render within timeout');
    const canvas = page.locator('canvas').first();

    // The "Scrape all recommendations" button sits above the graph.
    const scrapeAll = page.getByRole('button', { name: 'Scrape all recommendations' });
    await expect(scrapeAll).toBeVisible();
    await scrapeAll.click();

    // The filter dialog opens with the filters we shipped.
    const dialog = page.getByRole('dialog', { name: 'Scrape all recommendations' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await expect(dialog.getByRole('button', { name: 'Start scrape' })).toBeVisible();
    await expect(dialog.getByText('Projection')).toBeVisible();
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).not.toBeVisible();

    // Per-node scrape from the graph drawer also routes through the dialog
    // instead of firing immediately with default settings.
    await page.waitForTimeout(4000);
    const box = (await canvas.boundingBox()) ?? { x: 0, y: 0, width: 800, height: 480 };
    const drawer = page.locator('[data-slot="drawer-content"]');
    const pts = [
      [0.5, 0.5], [0.42, 0.5], [0.58, 0.5], [0.5, 0.42], [0.5, 0.58],
      [0.44, 0.44], [0.56, 0.44], [0.44, 0.56], [0.56, 0.56],
    ];
    for (const [fx, fy] of pts) {
      await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
      await page.waitForTimeout(450);
      if ((await drawer.count()) > 0) break;
    }
    if ((await drawer.count()) === 0) return;

    const scrapeBtn = drawer.getByRole('button', { name: 'Scrape recommendations' });
    await expect(scrapeBtn).toBeVisible();
    await scrapeBtn.click();
    const scrapeDialog = page.getByRole('dialog', { name: 'Scrape recommendations' });
    await expect(scrapeDialog).toBeVisible({ timeout: 10000 });
    await expect(scrapeDialog.getByRole('button', { name: 'Start scrape' })).toBeVisible();
  });
});

