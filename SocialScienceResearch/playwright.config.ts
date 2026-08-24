import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API_URL = process.env.API_URL ?? 'http://localhost:8000/api/v1/social-science';

export default defineConfig({
  testDir: './tests/e2e',
  // Generous per-test budget: on a loaded dev machine (builds, crawls,
  // background apps) individual page loads can stretch past a minute.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    headless: true,
    trace: 'on-first-retry',
  },
  env: {
    BASE_URL,
    API_URL,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
