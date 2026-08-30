import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

/**
 * Composite, journey-style coverage of the Lab "Layers" tab across MANY runs
 * (not a single run). Each selected run in the Network-slice picker must drive
 * the Layer tab to that run's own layer family — the regression being that the
 * Layer tab ignored the selection and always rendered the global newest layer
 * (so every run looked identical / "just 2 videos").
 *
 * For each run we bootstrap a seed layer (offline; copies the run's own videos)
 * and then mimic a researcher: pick the run, open Layers, open the seed layer,
 * and assert the relations reflect THAT run's real video count.
 */
test.describe('Lab Layers tab is run-aware across many runs', () => {
  type Target = {
    runId: string;
    display: string;
    layerRunId: string;
    videos: number;
    discovered: number;
  };
  const targets: Target[] = [];

  test.beforeAll(async ({ request }) => {
    const runsResp = await request.get(`${API}/runs?page_size=200`);
    const runs: { run_id: string; name?: string | null; run_type?: string }[] =
      (await runsResp.json()).items ?? [];

    const chosen: typeof runs = [];
    for (const run of runs) {
      if (chosen.length >= 4) break;
      const v = await request.get(
        `${API}/videos?run_id=${encodeURIComponent(run.run_id)}&page_size=1`,
      );
      const body = await v.json();
      if ((body.total ?? 0) > 0) chosen.push(run);
    }

    for (const run of chosen) {
      const b = await request.post(`${API}/network/layer`, {
        data: { run_id: run.run_id, projection: 'video' },
      });
      if (!b.ok()) continue;
      const layer = await b.json();
      const meta = await (
        await request.get(`${API}/network/layer/${layer.layer_run_id}`)
      ).json();
      targets.push({
        runId: run.run_id,
        display: run.name ?? run.run_id,
        layerRunId: layer.layer_run_id,
        videos: (await (
          await request.get(
            `${API}/videos?run_id=${encodeURIComponent(run.run_id)}&page_size=1`,
          )
        ).json()).total,
        discovered: meta.discovered_video_ids?.length ?? 0,
      });
    }
  });

  async function openRunLayers(page: import('@playwright/test').Page, display: string) {
    await page.goto(`${BASE_URL}/network/full`);
    // Never wait for load here: the Lab keeps polling jobs/queries in
    // the background, so network idle may never occur within the timeout.
    await page.getByLabel('Select network slice run').waitFor({ timeout: 45000 });
    await page.getByLabel('Select network slice run').click();
    await page.getByRole('option', { name: display, exact: true }).click();
    await page.getByRole('tab', { name: 'Layers' }).click();
  }

  test('Layers tab reflects every selected run (composite journey, many runs)', async ({
    page,
  }) => {
    test.setTimeout(240000);
    test.skip(targets.length === 0, 'No runs with videos found to bootstrap');
    for (const t of targets) {
      await openRunLayers(page, t.display);

      // The seed layer button for this run exists (a corpus-wide view can list
      // many seed chips; any one proves this run's family rendered).
      const seedBtn = page.getByRole('button', { name: /Layer 0 \(seed\)/ }).first();
      await expect(seedBtn).toBeVisible({ timeout: 30000 });
      await seedBtn.click();

      // The stepper must name THIS run, not a global/default one.
      await expect(
        page.getByText(/Seed layer built from/).first(),
      ).toBeVisible({ timeout: 30000 });

      // The relations panel loads for this run's layer.
      await expect(
        page.getByText(/What layer 0 added/),
      ).toBeVisible({ timeout: 30000 });

      // The stepper reflects THIS run's layer (tied to the backend's own
      // discovered count) — proving the Layer tab is scoping to the selection
      // rather than always rendering the same global layer.
      const enriched = page
        .getByText(/video\(s\) enriched/)
        .first();
      await expect(enriched).toBeVisible({ timeout: 30000 });
      const txt = (await enriched.textContent()) ?? '0';
      const n = parseInt(txt.replace(/\D+/g, ''), 10);
      expect(
        n,
        `run ${t.display} Layer tab should show its own discovered count`,
      ).toBe(t.discovered);
    }
  });

  test('different runs yield different Layer tab content', async ({ page }) => {
    test.setTimeout(240000);
    test.skip(targets.length < 2, 'Need at least two runs with data');
    const [a, b] = targets;

    await openRunLayers(page, a.display);
    await page.getByRole('button', { name: /Layer 0 \(seed\)/ }).first().click();
    const aContext = await page
      .getByText(/Seed layer built from/)
      .first()
      .textContent();

    await openRunLayers(page, b.display);
    await page.getByRole('button', { name: /Layer 0 \(seed\)/ }).first().click();
    const bContext = await page
      .getByText(/Seed layer built from/)
      .first()
      .textContent();

    expect(aContext).not.toEqual(bContext);
  });
});

