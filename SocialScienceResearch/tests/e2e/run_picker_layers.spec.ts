import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';

test('run selector stays enabled but drops "All runs" on the Layers tab', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('load');

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

