import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test('debug: check graph container classes', async ({ page }) => {
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
  
  // Find all elements with "rounded-md" (common in Tailwind)
  const matches = html.match(/[a-zA-Z0-9_-]+\s*rounded-md\s*/g) || [];
  console.log('=== ELEMENTS WITH rounded-md ===');
  matches.forEach(m => console.log(m));
  
  // Find div elements with class attribute
  const divClassMatches = html.match(/<div[^>]*class="[^"]*[^"]*"[^>]*>/g) || [];
  console.log('=== DIV ELEMENTS (first 20) ===');
  divClassMatches.slice(0, 20).forEach(m => {
    const classMatch = m.match(/class="([^"]*)"/);
    if (classMatch) {
      console.log(`div with class: ${classMatch[1]}`);
    }
  });
  
  // Take screenshot
  await page.screenshot({ path: 'debug6-screenshot.png', fullPage: true });
});