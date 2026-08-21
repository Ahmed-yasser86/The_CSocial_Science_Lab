import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug full page rendering', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(5000);
  
  // Check for various elements (await the counts)
  const graphContainer = await page.locator('div[class*="w-full overflow-hidden rounded-md border"]').count();
  const selectTrigger = await page.locator('div[class*="SelectTrigger"]').count();
  const canvas = await page.locator('canvas').count();
  const legendFocus = await page.locator('text=Focus video').count();
  const legendConnected = await page.locator('text=Connected video').count();
  const legendOther = await page.locator('text=Other').count();
  const runPicker = await page.locator('text=Network slice').count();
  
  console.log('=== ELEMENT COUNTS ===');
  console.log(`graphContainer: ${graphContainer}`);
  console.log(`selectTrigger: ${selectTrigger}`);
  console.log(`canvas: ${canvas}`);
  console.log(`legendFocus: ${legendFocus}`);
  console.log(`legendConnected: ${legendConnected}`);
  console.log(`legendOther: ${legendOther}`);
  console.log(`runPicker: ${runPicker}`);
  
  // Get page title
  const title = await page.title();
  console.log(`Page title: ${title}`);
  
  // Get page URL
  const url = page.url();
  console.log(`Page URL: ${url}`);
  
  // Take screenshot
  await page.screenshot({ path: 'debug2-screenshot.png', fullPage: true });
  
  // Check console errors
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  const consoleLogs: string[] = [];
  page.on('console', (msg) => consoleLogs.push(`${msg.type()}: ${msg.text()}`));
  
  // Wait a bit more
  await page.waitForTimeout(3000);
  
  console.log('=== CONSOLE LOGS ===');
  consoleLogs.forEach(log => console.log(log));
  
  console.log('=== PAGE ERRORS ===');
  errors.forEach(err => console.log(err));
});