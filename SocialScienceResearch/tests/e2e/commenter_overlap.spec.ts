import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

/**
 * Commenter-overlap E2E. Requires the UI and API to be running against the
 * current backend code.
 *
 * Covers:
 *  - API contract for GET /network/commenters/overlap and
 *    GET /network/commenters/{author_key}/profile
 *  - The /network/commenters page: manual scope entry + Analyze, and deep-link
 *    via ?video_ids=...
 *  - A commenter profile page rendered from a real shared commenter
 *
 * Every test that depends on real overlap data reads the overlap summary from
 * the live API at runtime and skips cleanly when the prerequisite is absent
 * (fewer than two videos, no comments, or no commenter active across two or
 * more videos). Tests never skip unconditionally.
 */
test.describe('Commenter Overlap', () => {
  let videoIds: string[] = [];
  let commenterKey: string | null = null;
  let hasOverlapData = false;

  test.beforeAll(async ({ request }) => {
    const channelsResp = await request.get(`${API}/channels`);
    if (!channelsResp.ok()) return;
    const channels: { channel_id: string }[] = (await channelsResp.json()).items ?? [];
    if (!channels.length) return;

    for (const channel of channels.slice(0, 3)) {
      const videosResp = await request.get(
        `${API}/channels/${channel.channel_id}/videos`,
      );
      if (!videosResp.ok()) continue;
      const videos: { video_id: string }[] = (await videosResp.json()).items ?? [];
      videoIds = videoIds.concat(videos.map((v) => v.video_id));
      if (videoIds.length >= 3) break;
    }
    videoIds = videoIds.slice(0, 3);

    if (videoIds.length >= 2) {
      const overlapResp = await request.get(
        `${API}/network/commenters/overlap?video_ids=${videoIds.join(',')}`,
      );
      if (overlapResp.ok()) {
        const result = await overlapResp.json();
        const global = result.global_summary ?? {};
        const projection = result.videos ?? {};
        const bridges = projection.bridge_commenters ?? [];
        // Real overlap exists only when the corpus has comments AND at least
        // one commenter active across >= 2 of the selected videos.
        hasOverlapData = (global.comment_count ?? 0) > 0 && bridges.length > 0;
        if (bridges.length) {
          commenterKey = bridges[0].author_key;
        }
      }
    }
  });

  test('API: computes overlap across videos', async ({ request }) => {
    test.skip(videoIds.length < 2, 'Fewer than two videos in the corpus');
    const resp = await request.get(
      `${API}/network/commenters/overlap?video_ids=${videoIds.join(',')}`,
    );
    expect(resp.status()).toBe(200);
    const result = await resp.json();
    test.skip(
      result.global_summary.comment_count === 0,
      'No comments in the corpus for the selected videos',
    );
    expect(result.metric).toBe('jaccard');
    expect(result.global_summary.comment_count).toBeGreaterThan(0);
    expect(result.videos).not.toBeNull();
    expect(result.videos.summary.pair_count).toBeGreaterThan(0);
    expect(result.videos.heatmap).toBeDefined();
  });

  test('API: invalid metric returns 400 invalid_argument', async ({ request }) => {
    const resp = await request.get(
      `${API}/network/commenters/overlap?video_ids=${videoIds.join(',')}&metric=not_a_metric`,
    );
    expect(resp.status()).toBe(400);
    const body = await resp.json();
    expect(body.code).toBe('invalid_argument');
  });

  test('page: manual scope entry renders results', async ({ page }) => {
    test.skip(
      !hasOverlapData,
      'No overlapping commenters in the corpus for the selected videos',
    );
    await page.goto(`${BASE_URL}/network/commenters`);
    await page.waitForLoadState('load');

    await page.getByLabel('Video IDs').fill(videoIds.slice(0, 2).join(', '));
    await page.getByRole('button', { name: 'Analyze' }).click();

    await expect(page.getByTestId('commenter-overlap-results')).toBeVisible({
      timeout: 20000,
    });
    await expect(page.getByText('Unique commenters')).toBeVisible();
    await expect(page.getByTestId('overlap-heatmap')).toBeVisible();
    await expect(page.getByText('Shared count')).toBeVisible();
  });

  test('page: deep-link via query params renders results directly', async ({
    page,
  }) => {
    test.skip(
      !hasOverlapData,
      'No overlapping commenters in the corpus for the selected videos',
    );
    await page.goto(
      `${BASE_URL}/network/commenters?video_ids=${videoIds.slice(0, 2).join(',')}`,
    );
    await page.waitForLoadState('load');

    await expect(page.getByTestId('commenter-overlap-results')).toBeVisible({
      timeout: 20000,
    });
  });

  test('page: commenter profile renders from a shared commenter', async ({
    page,
  }) => {
    test.skip(!commenterKey, 'No bridge commenter in the overlap result');
    await page.goto(`${BASE_URL}/network/commenters/${encodeURIComponent(commenterKey!)}`);
    await page.waitForLoadState('load');

    await expect(page.getByTestId('commenter-profile')).toBeVisible({
      timeout: 20000,
    });
    await expect(page.getByRole('tab', { name: /Videos/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Channels/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Comments/ })).toBeVisible();
  });
});
