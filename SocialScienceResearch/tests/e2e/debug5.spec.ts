import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: click run and check HTML', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  
  // Click the run filter combobox button (data-slot="select-trigger")
  await page.click('button[data-slot="select-trigger"]');
  await page.waitForTimeout(2000);
  
  // Check for run options
  const runOptions = await page.locator('[role="option"]').count();
  console.log(`run options count: ${runOptions}`);
  
  // Try to click the first run option
  if (runOptions > 0) {
    await page.click('[role="option"]:first-child');
    await page.waitForTimeout(3000);
  }
  
  // Get the full page HTML
  const html = await page.content();
  
  // Find the graph container
  const graphContainerIndex = html.indexOf('w-full overflow-hidden rounded-md border');
  if (graphContainerIndex !== -1) {
    const start = Math.max(0, graphContainerIndex - 200);
    const end = Math.min(html.length, graphContainerIndex + 500);
    const context = html.substring(start, end);
    console.log('=== GRAPH CONTAINER CONTEXT ===');
    console.log(context);
  } else {
    console.log('Graph container class not found in HTML');
  }
  
  // Check for canvas
  const canvasIndex = html.indexOf('canvas');
  if (canvasIndex !== -1) {
    const start = Math.max(0, canvasIndex - 200);
    const end = Math.min(html.length, canvasIndex + 500);
    const context = html.substring(start, end);
    console.log('=== CANVAS CONTEXT ===');
    console.log(context);
  }
  
  // Take screenshot
  await page.screenshot({ path: 'debug5-screenshot.png', fullPage: true });
});