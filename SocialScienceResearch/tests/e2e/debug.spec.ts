import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug page load', async ({ page }) => {
  const consoleLogs: string[] = [];
  const errors: string[] = [];
  
  page.on('console', msg => {
    consoleLogs.push(`${msg.type()}: ${msg.text()}`);
  });
  
  page.on('pageerror', error => {
    errors.push(error.message);
  });
  
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  
  // Wait a bit for React to hydrate
  await page.waitForTimeout(5000);
  
  console.log('=== CONSOLE LOGS ===');
  consoleLogs.forEach(log => console.log(log));
  
  console.log('=== ERRORS ===');
  errors.forEach(err => console.log(err));
  
  // Check if the FullNetworkView component is rendered
  const pageContent = await page.content();
  console.log('=== PAGE CONTENT (first 5000 chars) ===');
  console.log(pageContent.substring(0, 5000));
  
  // Check for specific elements
  const hasGraphContainer = await page.locator('div[class*="w-full overflow-hidden rounded-md border"]').count();
  const hasSelectTrigger = await page.locator('div[class*="SelectTrigger"]').count();
  const hasCanvas = await page.locator('canvas').count();
  
  console.log(`Graph container count: ${hasGraphContainer}`);
  console.log(`SelectTrigger count: ${hasSelectTrigger}`);
  console.log(`Canvas count: ${hasCanvas}`);
  
  // Take a screenshot for debugging
  await page.screenshot({ path: 'debug-screenshot.png', fullPage: true });
});