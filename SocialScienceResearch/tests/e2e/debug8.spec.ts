import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: full state check', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(5000);
  
  // Collect console logs and errors
  const logs: string[] = [];
  const errors: string[] = [];
  
  page.on('console', (msg) => {
    logs.push(`${msg.type()}: ${msg.text()}`);
  });
  
  page.on('pageerror', (err) => {
    errors.push(err.message);
  });
  
  // Wait for canvas or timeout
  try {
    await page.waitForSelector('canvas', { timeout: 15000 });
    console.log('Canvas appeared!');
  } catch (e) {
    console.log('Canvas did not appear within 15s');
  }
  
  // Check element counts
  const canvasCount = await page.locator('canvas').count();
  const graphCount = await page.locator('div[class*="w-full"]').count();
  const selectTriggerCount = await page.locator('button[data-slot="select-trigger"]').count();
  
  console.log('=== COUNTS ===');
  console.log(`canvas: ${canvasCount}`);
  console.log(`div w-full: ${graphCount}`);
  console.log(`select-trigger button: ${selectTriggerCount}`);
  
  console.log('=== CONSOLE LOGS ===');
  logs.forEach(l => console.log(l));
  
  console.log('=== PAGE ERRORS ===');
  errors.forEach(e => console.log(e));
  
  // Get page title
  const title = await page.title();
  console.log(`Page title: ${title}`);
  
  // Get URL
  const url = page.url();
  console.log(`URL: ${url}`);
  
  // Take screenshot
  await page.screenshot({ path: 'debug8-screenshot.png', fullPage: true });
});