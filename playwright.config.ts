import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "SocialScienceResearch/tests/e2e",
  timeout: 180_000,
  workers: 2,
  retries: 0,
  reporter: [["line"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    // The force-directed canvas fills the tab (full viewport height minus the
    // page chrome). A 720px-tall default viewport leaves most of the canvas
    // below the fold, so mouse.move() never reaches the nodes and hover/click
    // interaction tests fail. Give the graph a fully visible viewport.
    viewport: { width: 1600, height: 1200 },
  },
});

process.env.BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
process.env.API_URL =
  process.env.API_URL ?? "http://127.0.0.1:8000/api/v1/social-science";