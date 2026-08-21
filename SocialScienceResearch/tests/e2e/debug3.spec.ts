import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: select run and check graph rendering', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  
  // Check initial state
  console.log('=== INITIAL STATE ===');
  const graphContainer = await page.locator('div[class*="w-full overflow-hidden rounded-md border"]').count();
  const selectTrigger = await page.locator('div[class*="SelectTrigger"]').count();
  const runPickerText = await page.locator('text=Network slice').count();
  console.log(`graphContainer: ${graphContainer}`);
  console.log(`selectTrigger: ${selectTrigger}`);
  console.log(`runPickerText: ${runPickerText}`);
  
  // Click the run filter to show runs
  console.log('=== CLICKING RUN FILTER ===');
  await page.click('div[class*="SelectTrigger"]:has-text("Network slice")');
  await page.waitForTimeout(2000);
  
  // Check for run options
  const runOptions = await page.locator('[role="option"]').count();
  console.log(`run options count: ${runOptions}`);
  
  // Try to click the first run option
  if (runOptions > 0) {
    console.log('=== CLICKING FIRST RUN ===');
    await page.click('[role="option"]:first-child');
    await page.waitForTimeout(3000);
    
    // Check state after selecting run
    const graphContainer = await page.locator('div[class*="w-full overflow-hidden rounded-md border"]').count();
    const canvas = await page.locator('canvas').count();
    const legendFocus = await page.locator('text=Focus video').count();
    console.log(`graphContainer after run select: ${graphContainer}`);
    console.log(`canvas after run select: ${canvas}`);
    console.log(`legendFocus after run select: ${legendFocus}`);
  }
  
  // Take screenshot
  await page.screenshot({ path: 'debug3-screenshot.png', fullPage: true });
});