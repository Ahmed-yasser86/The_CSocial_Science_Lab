import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: find graph container', async ({ page }) => {
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
  
  // Find all elements with "overflow-hidden"
  const overflowMatches = html.match(/overflow-hidden/g) || [];
  console.log(`overflow-hidden count: ${overflowMatches.length}`);
  
  // Find all elements with "w-full"
  const wFullMatches = html.match(/w-full/g) || [];
  console.log(`w-full count: ${wFullMatches.length}`);
  
  // Find div elements and extract their classes
  const divClassPattern = /<div[^>]*class="([^"]*)"[^>]*>/g;
  let match;
  let divCount = 0;
  while ((match = divClassPattern.exec(html)) && divCount < 30) {
    divCount++;
    const classes = match[1];
    if (classes.includes('overflow-hidden') || classes.includes('graph') || classes.includes('network')) {
      console.log(`div with overflow-hidden or graph/network: ${classes}`);
    }
    if (divCount >= 5 && (classes.includes('overflow-hidden') || classes.includes('graph') || classes.includes('network'))) {
      // We found enough, stop looking
    }
  }
  
  // Search for the specific pattern we're looking for
  const pattern = /div class="[^"]*overflow-hidden[^"]*"/g;
  let patternMatch;
  while ((patternMatch = pattern.exec(html)) && divCount < 30) {
    divCount++;
    console.log(`div with overflow-hidden pattern: ${patternMatch[0]}`);
  }
  
  // Take screenshot
  await page.screenshot({ path: 'debug7-screenshot.png', fullPage: true });
});