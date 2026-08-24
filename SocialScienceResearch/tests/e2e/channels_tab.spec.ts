import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

/**
 * Channels tab (Lab) E2E. Requires the UI + API to be running against the
 * current backend code. Covers:
 *  - The "Channels" tab is present and renders a search box.
 *  - Channels list with metadata renders (or a friendly empty state).
 *  - The name/handle search filters the list.
 *  - Expanding a channel reveals its videos, each linking to analytics.
 */
test.describe('Channels tab', () => {
  let seededChannelId: string | null = null;
  let seededChannelTitle: string | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    // Warm up the Next.js dev server route compilation so the first test does
    // not time out waiting on on-demand compilation.
    try {
      await request.get(`${baseURL ?? BASE_URL}/network/full`);
    } catch {
      /* ignore */
    }
    const resp = await request.get(`${API}/channels?page_size=1`);
    if (resp.ok()) {
      const body = await resp.json();
      const channels: { channel_id: string; title: string | null }[] =
        body.items ?? [];
      if (channels.length) {
        seededChannelId = channels[0].channel_id;
        seededChannelTitle = channels[0].title;
      }
    }
  });

  test('Channels tab renders search and a channel list or empty state', async ({
    page,
  }) => {
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState('networkidle');
    await page.getByRole('tab', { name: 'Channels' }).click();

    await expect(
      page.getByRole('textbox', { name: 'Search channels' }),
    ).toBeVisible();

    // Either channels render or a friendly empty state is shown.
    const rows = page.getByTestId('channel-row');
    const empty = page.getByText('No channels found');
    await expect
      .poll(async () => (await rows.count()) > 0 || (await empty.count()) > 0, {
        timeout: 30000,
      })
      .toBeTruthy();
  });

  test('Channel search filters by name', async ({ page }) => {
    test.skip(!seededChannelTitle, 'No seeded channel title available');
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState('networkidle');
    await page.getByRole('tab', { name: 'Channels' }).click();

    const search = page.getByRole('textbox', { name: 'Search channels' });
    await search.fill(seededChannelTitle!.slice(0, 3));
    await expect
      .poll(async () => page.getByText(seededChannelTitle!, { exact: false }).count(), {
        timeout: 30000,
      })
      .toBeGreaterThan(0);
  });

  test('Expanding a channel lists its videos with analytics links', async ({
    page,
  }) => {
    test.skip(!seededChannelId, 'No seeded channel available');
    await page.goto(`${BASE_URL}/network/full`);
    await page.waitForLoadState('networkidle');
    await page.getByRole('tab', { name: 'Channels' }).click();

    const row = page
      .locator('button', { hasText: seededChannelTitle ?? seededChannelId! })
      .first();
    await row.click();

    await expect
      .poll(
        async () => page.getByRole('link', { name: 'Analytics' }).count(),
        { timeout: 30000 },
      )
      .toBeGreaterThan(0);
  });
});
