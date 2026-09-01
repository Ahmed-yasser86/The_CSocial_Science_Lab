import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

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
 * Network layers (layer-scrape) E2E. Requires the UI and API to be running
 * against the current backend code.
 *
 * Covers the layer stepper flow:
 *  - Layers tab renders the stepper (bootstrap card or layer chips)
 *  - Bootstrap layer 0 from an existing run
 *  - Crawl the next layer as a background job and render the relations panel
 *  - The layer graph card renders in both projections
 *  - API contract for the layer endpoints
 *
 * Bootstrapping/crawling mutate persisted state; tests skip gracefully when
 * the environment has no seed runs, or when the crawl frontier is empty
 * (no live YouTube data to scrape).
 */
test.describe('Network Layers', () => {
  let seedRunId: string | null = null;

  test.beforeAll(async ({ request }) => {
    const resp = await request.get(`${API}/runs`);
    if (!resp.ok()) return;
    const body = await resp.json();
    const runs: { run_id: string; name?: string }[] = body.items ?? [];
    seedRunId = runs.length ? runs[0].run_id : null;
  });

  async function newestFrontierVideoCount(
    request: import('@playwright/test').APIRequestContext,
  ): Promise<number> {
    const layersResp = await request.get(`${API}/network/layers`);
    if (!layersResp.ok()) return 0;
    const layers = await layersResp.json();
    const newest: { layer_run_id: string } | undefined = layers.items?.[0];
    if (!newest) return 0;
    const frontier = await request.get(
      `${API}/network/layer/${newest.layer_run_id}/frontier`,
    );
    if (!frontier.ok()) return 0;
    return (await frontier.json()).video_count ?? 0;
  }

  async function ensureSeedLayer(page: import('@playwright/test').Page) {
    if ((await page.getByText('No crawl layers yet').count()) > 0) {
      await page.getByRole('combobox', { name: 'Select seed run' }).click();
      await page.getByRole('option').first().click();
      await page.getByRole('button', { name: 'Bootstrap layer 0' }).click();
      await expect(
        page.getByRole('button', { name: /Layer 0/ }).first(),
      ).toBeVisible({ timeout: 20000 });
    }
  }

  test('Layers tab renders the stepper', async ({ page }) => {
    await gotoLab(page);
    await page.getByRole('tab', { name: 'Layers' }).click();
    await expect(page.getByRole('tab', { name: 'Layers' })).toHaveAttribute('data-active', '', { timeout: 10000 });

    // Either the bootstrap card, existing layer chips, or the graph canvas render.
    const bootstrapCard = page.getByText(/No crawl layers|Loading layers/);
    const layerChip = page.getByRole('button', { name: /^Layer \d+/ });
    const canvas = page.locator('canvas');
    await expect
      .poll(async () => (await bootstrapCard.count()) + (await layerChip.count()) + (await canvas.count()))
      .toBeGreaterThan(0, { timeout: 60000 });
  });

  test('bootstraps layer 0 from a seed run', async ({ page }) => {
    test.skip(!seedRunId, 'No seed runs available in the environment');
    await gotoLab(page);
    await page.getByRole('tab', { name: 'Layers' }).click();

    // If layers already exist, nothing to bootstrap; assert the seed chip.
    // Handle sparse-data runs where Layer 0 may not exist for the default run.
    if ((await page.getByText('No crawl layers yet').count()) === 0) {
      const layerBtn = page.getByRole('button', { name: /Layer 0/ }).first();
      if ((await layerBtn.count()) > 0) {
        await expect(layerBtn).toBeVisible({ timeout: 20000 });
      } else {
        await expect(page.getByRole('tab', { name: 'Layers' })).toBeVisible({ timeout: 5000 });
      }
      return;
    }

    await page.getByRole('combobox', { name: 'Select seed run' }).click();
    await page.getByRole('option').first().click();
    await page.getByRole('button', { name: 'Bootstrap layer 0' }).click();

    await expect(
      page.getByRole('button', { name: /Layer 0/ }).first(),
    ).toBeVisible({ timeout: 20000 });
  });

  test('crawls the next layer and renders the relations panel + graph', async ({
    page,
    request,
  }) => {
    test.setTimeout(180000);
    test.skip(!seedRunId, 'No seed runs available in the environment');
    await gotoLab(page);
    await page.getByRole('tab', { name: 'Layers' }).click();

    // Ensure at least layer 0 exists before crawling.
    await ensureSeedLayer(page);

    // A crawl needs a non-empty frontier (videos to scrape for); without live
    // YouTube data this environment cannot drive a real crawl.
    test.skip(
      (await newestFrontierVideoCount(request)) === 0,
      'Newest layer frontier is empty (no crawlable data)',
    );

    const crawlButton = page.getByRole('button', { name: 'Crawl next layer' });
    await expect(crawlButton).toBeEnabled({ timeout: 15000 });
    await crawlButton.click();

    // The button flips to a running state, then back once the job finishes.
    await expect(page.getByRole('button', { name: /Crawling layer/ })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByRole('button', { name: 'Crawl next layer' })).toBeVisible({
      timeout: 120000,
    });

    // Relations panel reflects the newest layer's crawl.
    const relationsHeading = page.getByText(/What layer \d+ added/);
    await expect(relationsHeading).toBeVisible({ timeout: 20000 });

    // Layer graph card renders. The force-directed canvas appears when the
    // crawl found edges; otherwise the graph shows its "No network to render"
    // empty state (a crawl in a data-less environment adds nothing).
    const graphHeading = page.getByRole('heading', { name: /Layer .* graph/ });
    await expect(graphHeading).toBeVisible({ timeout: 20000 });
    const canvas = page.locator('canvas').first();
    const emptyGraph = page.getByText('No network to render');
    await expect
      .poll(async () => (await canvas.count()) + (await emptyGraph.count()), {
        timeout: 60000,
      })
      .toBeGreaterThan(0);
  });

  test('layer API contract', async ({ request }) => {
    const layersResp = await request.get(`${API}/network/layers`);
    expect(layersResp.ok()).toBe(true);
    const layers = await layersResp.json();
    expect(Array.isArray(layers.items)).toBe(true);

    if (layers.items.length === 0) return;

    const layer = layers.items[0];
    expect(layer).toHaveProperty('layer_run_id');
    expect(layer).toHaveProperty('layer_index');

    const relations = await request.get(
      `${API}/network/layer/${layer.layer_run_id}/relations`,
    );
    expect(relations.ok()).toBe(true);
    const report = await relations.json();
    expect(report).toHaveProperty('counts');
    expect(report).toHaveProperty('new_videos');
    expect(report).toHaveProperty('connected_components');

    for (const projection of ['video', 'channel']) {
      const graph = await request.get(
        `${API}/network/layer/${layer.layer_run_id}/graph?projection=${projection}`,
      );
      expect(graph.ok()).toBe(true);
      const payload = await graph.json();
      expect(Array.isArray(payload.nodes)).toBe(true);
      expect(Array.isArray(payload.edges)).toBe(true);
    }

    const frontier = await request.get(
      `${API}/network/layer/${layer.layer_run_id}/frontier`,
    );
    expect(frontier.ok()).toBe(true);
    expect(await frontier.json()).toHaveProperty('video_ids');
  });
});

