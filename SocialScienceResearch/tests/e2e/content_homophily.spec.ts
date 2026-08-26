import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1/social-science";

/**
 * Content Homophily E2E smoke (Content Homophily spec §22-§24, MOCKED backend).
 *
 * Verifies the opt-in journey on the echo page's "Content" tab: start an
 * on-demand analysis -> stage checklist + embedding observability render ->
 * the CONTENT EVIDENCE results block appears with disclaimers.
 */

const ANALYSIS_ID = "chh_e2e_test_0001";
const JOB_ID = "job_e2e_chh";

function analysisPayload(status: string) {
  const done = status === "observed" || status === "insufficient_data";
  return {
    analysis_id: ANALYSIS_ID,
    job_id: JOB_ID,
    status,
    params: {
      run_id: null,
      video_ids: [],
      sampling_fraction: 0.1,
      max_pair_cap: 10000,
      random_seed: 42,
      num_permutations: 1000,
      max_videos_per_community: 40,
      include_edge_similarity: false,
    },
    progress: {
      current_stage: done ? null : "embedding_preparation",
      stages: done
        ? {
            dataset_preparation: "done",
            transcript_collection: "done",
            embedding_preparation: "done",
            pair_sampling: "done",
            similarity_calculation: "done",
            observed_difference: "done",
            null_model: "done",
            statistical_summary: "done",
            results: "done",
          }
        : {
            dataset_preparation: "done",
            transcript_collection: "done",
            embedding_preparation: "running",
          },
      log: [
        { ts: new Date().toISOString(), message: "dataset prepared: 12 videos" },
        { ts: new Date().toISOString(), message: "transcript loaded: a0" },
        { ts: new Date().toISOString(), message: "embedding ready: a1" },
      ],
      videos_total: 12,
      videos_processed: status === "running" ? 7 : 12,
      embeddings_reused: 5,
      embeddings_generated: status === "running" ? 2 : 7,
      embedding_failures: 0,
      embedding_model: "mock-embed-model",
      elapsed_seconds: 18.4,
      eta_seconds: status === "running" ? 14.6 : 0,
    },
    results: done
      ? {
          status,
          label: "CONTENT EVIDENCE",
          within_mean_similarity: 0.74,
          between_mean_similarity: 0.43,
          observed_difference: 0.31,
          null_mean: 0.01,
          null_std: 0.04,
          z_score: 7.5,
          permutation_p_value: 0.001,
          pairs_available_within: 31600,
          pairs_sampled_within: 10000,
          pairs_available_between: 4200000,
          pairs_sampled_between: 10000,
          sampling_fraction: 0.1,
          max_pair_cap: 10000,
          random_seed: 42,
          num_permutations: 1000,
          videos_with_transcript: 87,
          videos_without_transcript: 13,
          transcript_coverage: 0.87,
          embedding_model: "mock-embed-model",
          embedding_model_version: "1",
          embeddings_reused: 58,
          embeddings_generated: 15,
          embedding_failures: 0,
          analysis_run_id: ANALYSIS_ID,
          community_algorithm: "louvain_communities(seed=42)",
          chunking_configuration: { chunk_size: 1000, chunk_overlap: 200 },
          disclaimers: [
            "Content homophily is evidence about observed content structure only.",
          ],
        }
      : undefined,
    created_at: new Date().toISOString(),
  };
}

async function mockBackend(page: Page, wsId: string, wsName: string) {
  let state = { status: "observed", polls: 0 };

  await page.route("**/session/context", async (route) =>
    route.fulfill({
      json: {
        active_workspace_id: wsId,
        active_project_id: null,
        active_dataset_id: null,
        updated_at: new Date().toISOString(),
      },
    }),
  );
  await page.route(`**/workspaces/${wsId}`, async (route) =>
    route.fulfill({
      json: {
        workspace_id: wsId,
        name: wsName,
        research_topic: null,
        is_legacy: false,
        active: true,
        created_at: new Date().toISOString(),
        last_opened_at: new Date().toISOString(),
        stats: { runs: 0, videos: 0, channels: 0, comments: 0, datasets: 0, samples: 0, projects: 0 },
      },
    }),
  );
  await page.route("**/jobs", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: { items: [], next_cursor: null, has_more: false, total: 0 },
    });
  });

  await page.route("**/network/content-homophily?*", async (route) => {
    if (route.request().method() === "POST") return route.fallback();
    return route.fulfill({
      json: {
        items: [analysisPayload(state.status)],
        next_cursor: null,
        has_more: false,
        total: 1,
      },
    });
  });
  await page.route("**/network/content-homophily", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    state.status = "running";
    // Simulate the background job finishing shortly after start.
    setTimeout(() => {
      state.status = "observed";
    }, 1500);
    return route.fulfill({
      json: { analysis_id: ANALYSIS_ID, job_id: JOB_ID, status: "pending" },
    });
  });
  await page.route(new RegExp(`/network/content-homophily/${ANALYSIS_ID}$`), async (route) =>
    route.fulfill({ json: analysisPayload(state.status) }),
  );
}

test.describe("Content Homophily", () => {
  test.setTimeout(120_000);

  let wsId = "";
  let wsName = "Legacy";

  test.beforeAll(async ({ request }) => {
    try {
      const resp = await request.get(`${API}/workspaces`);
      if (resp.ok()) {
        const workspaces = (await resp.json()).items ?? [];
        if (workspaces.length) {
          wsId = workspaces[0].workspace_id;
          wsName = workspaces[0].name;
          return;
        }
      }
    } catch {
      /* fall through to mocked ids */
    }
    wsId = "ws_mock";
    wsName = "Mock Workspace";
  });

  test("opt-in start -> progress checklist -> CONTENT EVIDENCE block", async ({ page }) => {
    await mockBackend(page, wsId, wsName);
    await page.addInitScript(
      ([id]) => {
        window.localStorage.setItem(
          "ssr-active-workspace",
          JSON.stringify({ workspaceId: id, updatedAt: new Date().toISOString() }),
        );
      },
      [wsId] as unknown as string[],
    );

    await page.goto(`${BASE_URL}/network/echo-chambers`);
    await expect(page.getByTestId("echo-chamber-view")).toBeVisible();

    // The Content tab hosts the independent CONTENT evidence layer.
    await page.getByTestId("echo-tab-content").click();
    await expect(page.getByTestId("content-homophily-section")).toBeVisible();
    await expect(page.getByTestId("chh-start-button")).toBeVisible();

    // Opt in: start the on-demand analysis.
    await page.getByTestId("chh-start-button").click();

    // Running: stage checklist + embedding observability are visible.
    await expect(page.getByTestId("chh-stage-checklist")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("chh-embedding-stats")).toContainText("7 / 12");

    // Terminal: the CONTENT EVIDENCE block renders with key §19 fields and
    // never claims an echo-chamber probability.
    await expect(page.getByTestId("chh-results")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("chh-results")).toContainText("+0.310");
    await expect(page.getByTestId("chh-results")).toContainText("Transcript coverage");
    await expect(page.getByTestId("content-homophily-section")).not.toContainText(
      /echo chamber probability/i,
    );
  });
});
