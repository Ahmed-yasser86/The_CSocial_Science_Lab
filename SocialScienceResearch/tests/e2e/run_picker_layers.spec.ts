import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';

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

test('run selector stays enabled but drops "All runs" on the Layers tab', async ({ page }) => {
  await gotoLab(page);

  const picker = page.getByLabel('Select network slice run');
  const allRunsOption = page.getByRole('option', { name: 'All runs', exact: true });

  // Default (Metrics) tab: enabled and the "All runs" choice is available.
  await expect(picker).toBeEnabled();
  await picker.click();
  await expect(allRunsOption).toBeVisible();
  await page.keyboard.press('Escape');

  // Layers tab: still enabled (you can pick a specific run) but "All runs"
  // is no longer offered, forcing a concrete slice for the layer family.
  await page.getByRole('tab', { name: 'Layers' }).click();
  await expect(picker).toBeEnabled();
  await picker.click();
  await expect(allRunsOption).toHaveCount(0);
  await page.keyboard.press('Escape');

  // Leaving the tab restores the "All runs" choice.
  await page.getByRole('tab', { name: 'Metrics' }).click();
  await picker.click();
  await expect(allRunsOption).toBeVisible();
});

