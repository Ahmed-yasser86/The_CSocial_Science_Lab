import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: check w-full divs', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  
  // Click the run filter combobox button (data-slot="select-trigger")
  await page.click('button[data-slot="select-trigger"]');
  await page.waitForTimeout(2000);
  
  // Click the first run option
  await page.click('[role="option"]:first-child');
  await page.waitForTimeout(3000);
  
  // Get the full page HTML
  const html = await page.content();
  
  // Find div w-full elements
  const regex = /<div[^>]*class="[^"]*w-full[^"]*"[^>]*>/g;
  let match;
  let i = 0;
  while ((match = regex.exec(html)) && i < 5) {
    i++;
    const start = Math.max(0, match.index - 50);
    const end = Math.min(html.length, match.index + match[0].length + 100);
    const context = html.substring(start, end);
    console.log(`=== w-full div ${i} ===`);
    console.log(context.substring(0, 300));
    console.log('---');
  }
  
  // Take screenshot
  await page.screenshot({ path: 'debug9-screenshot.png', fullPage: true });
});