import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: check HTML structure', async ({ page }) => {
  await page.goto(`${BASE_URL}/network/full`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  
  // Get the full page HTML
  const html = await page.content();
  
  // Find the SelectTrigger element and its surrounding structure
  const selectTriggerIndex = html.indexOf('SelectTrigger');
  if (selectTriggerIndex !== -1) {
    // Get a portion of the HTML around the SelectTrigger
    const start = Math.max(0, selectTriggerIndex - 200);
    const end = Math.min(html.length, selectTriggerIndex + 500);
    const context = html.substring(start, end);
    console.log('=== SELECT TRIGGER CONTEXT ===');
    console.log(context);
  } else {
    console.log('SelectTrigger not found in HTML');
  }
  
  // Also check for the run picker text
  const runPickerIndex = html.indexOf('Network slice');
  if (runPickerIndex !== -1) {
    const start = Math.max(0, runPickerIndex - 200);
    const end = Math.min(html.length, runPickerIndex + 500);
    const context = html.substring(start, end);
    console.log('=== RUN PICKER CONTEXT ===');
    console.log(context);
  }
  
  // Take screenshot
  await page.screenshot({ path: 'debug4-screenshot.png', fullPage: true });
});