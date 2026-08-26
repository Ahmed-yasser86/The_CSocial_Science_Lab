import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const API = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1/social-science";

/**
 * Echo-chamber detector E2E (echo plan E3 journey, fully MOCKED backend).
 *
 * No live yt-dlp: POST /echo-chamber/detect, GET /echo-chamber/{id},
 * /continue and /stop are intercepted with page.route and served from an
 * in-test state machine, so the layered timeline / verdict / continue / stop
 * interactions are exercised deterministically against the real UI bundle.
 */

const DETECTION_ID = "ech_e2e_test_0001";
const JOB_ID = "job_e2e_echo";

interface LayerRow {
  layer_index: number;
  nodes_discovered: number;
  edges_observed: number;
}

function signal(
  value: number | null,
  detail: Record<string, unknown> = {},
): { value: number | null; status: string; detail: Record<string, unknown> } {
  return {
    value,
    status: value === null ? "unavailable" : "available",
    detail,
  };
}

function buildLayer(row: LayerRow, nodesTotal: number) {
  const zeroEdge = row.edges_observed === 0;
  return {
    layer_run_id: `lyr_${row.layer_index}`,
    layer_index: row.layer_index,
    nodes_discovered: row.nodes_discovered,
    edges_observed: row.edges_observed,
    nodes_total: nodesTotal,
    signals: {
      // S1 unavailable before layer 2 (nothing can collapse yet).
      s1: signal(row.layer_index >= 2 && !zeroEdge ? 0.5 : null, {
        per_layer: row.layer_index >= 2 ? 0.5 : null,
        cumulative: row.layer_index >= 2 ? 0.5 : null,
      }),
      s2: signal(!zeroEdge ? 0.72 : null, {
        community_share: !zeroEdge ? 0.6 : null,
        modularity: !zeroEdge ? 0.31 : null,
        community_size: 6,
        node_count: nodesTotal,
      }),
      s3: signal(!zeroEdge ? 0.8 : null, {
        top1: !zeroEdge ? 0.8 : null,
        top3: !zeroEdge ? 1.0 : null,
        seed_channel_share: 0.2,
      }),
      s4: signal(!zeroEdge && row.layer_index >= 2 ? 0.25 : null),
      s5: { value: null, status: "unavailable", detail: {} },
    },
    computed_at: new Date().toISOString(),
  };
}

function scoreFor(verdict: string, value: number | null) {
  const statuses = (v: boolean) => (v ? "available" : "unavailable");
  return {
    value,
    band: verdict === "inconclusive" ? null : verdict,
    verdict,
    components: [
      { key: "s1", label: "Frontier collapse ratio", value: value === null ? null : 0.5, weight_effective: 0.35, status: statuses(value !== null) },
      { key: "s2", label: "Seed-community concentration", value: value === null ? null : 0.72, weight_effective: 0.3, status: statuses(value !== null) },
      { key: "s3", label: "Top-channel share", value: value === null ? null : 0.8, weight_effective: 0.2, status: statuses(value !== null) },
      { key: "s4", label: "Cross-layer repetition", value: value === null ? null : 0.25, weight_effective: 0.15, status: statuses(value !== null) },
      { key: "s5", label: "Commenter-overlap reinforcement", value: null, weight_effective: 0, status: "unavailable" },
    ],
    computed_at: new Date().toISOString(),
  };
}

/** Mutable mocked-detection state shared across route handlers. */
function makeState() {
  return {
    status: "running",
    layers: [] as ReturnType<typeof buildLayer>[],
    verdict: "no_chamber_yet",
    scoreValue: 0.32 as number | null,
    error: null as string | null,
  };
}

function detectionPayload(state: ReturnType<typeof makeState>) {
  const nodesTotal =
    state.layers.length > 0
      ? state.layers[state.layers.length - 1].nodes_total
      : 2;
  return {
    detection_id: DETECTION_ID,
    seed_video_id: "seed_a",
    seed_run_id: "run_seed",
    root_layer_run_id: state.layers[0]?.layer_run_id ?? null,
    job_id: JOB_ID,
    status: state.status,
    params: {
      video_url: "https://www.youtube.com/watch?v=seed_a",
      max_layers: 5,
      discovery_mode: "frontier",
      collect_comments: false,
    },
    layers: state.layers,
    score: state.layers.length ? scoreFor(state.verdict, state.scoreValue) : null,
    error: state.error,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

async function mockBackend(page: Page, state: ReturnType<typeof makeState>, wsId: string, wsName: string) {
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
      json: {
        items: [
          {
            job_id: JOB_ID,
            kind: "echo_chamber",
            status: state.status === "running" ? "running" : "succeeded",
            created_at: new Date().toISOString(),
            progress: {},
            cancel_requested: false,
            runs: [],
          },
        ],
        next_cursor: null,
        has_more: false,
        total: 1,
      },
    });
  });
  await page.route(`**/jobs/${JOB_ID}`, async (route) =>
    route.fulfill({
      json: {
        job_id: JOB_ID,
        kind: "echo_chamber",
        status: state.status === "running" ? "running" : "succeeded",
        created_at: new Date().toISOString(),
        progress: {},
        cancel_requested: false,
        runs: [],
      },
    }),
  );
  await page.route(`**/jobs/${JOB_ID}/stream`, async (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: ": keep-alive\n\n",
    }),
  );

  await page.route("**/echo-chamber/detect", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    state.status = "running";
    state.layers = [buildLayer({ layer_index: 0, nodes_discovered: 2, edges_observed: 0 }, 2)];
    return route.fulfill({
      json: { detection_id: DETECTION_ID, job_id: JOB_ID, status: "pending" },
    });
  });

  await page.route(`**/echo-chamber/${DETECTION_ID}/continue`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    state.status = "running";
    return route.fulfill({ json: { job_id: JOB_ID } });
  });

  await page.route(`**/echo-chamber/${DETECTION_ID}/stop`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    state.status = "stopped";
    state.verdict = "inconclusive";
    state.scoreValue = null;
    return route.fulfill({
      json: { detection_id: DETECTION_ID, job_id: JOB_ID, status: "stopped" },
    });
  });

  await page.route(new RegExp(`/echo-chamber/${DETECTION_ID}$`), async (route: Route) =>
    route.fulfill({ json: detectionPayload(state) }),
  );
}

test.describe("Echo chamber detector", () => {
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
      /* fall through */
    }
    // Fully-mocked fallback when no API is reachable: the session/workspace
    // routes are intercepted anyway, so any id works.
    wsId = "ws_mock";
    wsName = "Mock Workspace";
  });

  test("detect -> layered timeline renders -> continue -> verdict updates", async ({ page }) => {
    const state = makeState();
    await mockBackend(page, state, wsId, wsName);
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
    await expect(page.getByTestId("echo-empty")).toBeVisible();

    await page.getByTestId("echo-video-url").fill("https://www.youtube.com/watch?v=seed_a");
    await page.getByTestId("echo-max-layers").fill("5");
    await page.getByTestId("echo-detect-button").click();

    // Detection starts; the mocked crawl reports two completed layers.
    state.layers = [
      buildLayer({ layer_index: 0, nodes_discovered: 2, edges_observed: 0 }, 2),
      buildLayer({ layer_index: 1, nodes_discovered: 3, edges_observed: 3 }, 7),
    ];
    await expect(page.getByTestId("echo-timeline")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("echo-timeline-row")).toHaveCount(2);
    await expect(page.getByTestId("echo-status")).toHaveText("Crawling");

    // Crawl finishes naturally: layers 2..3 land, verdict appears.
    state.status = "completed";
    state.verdict = "weak";
    state.scoreValue = 0.52;
    state.layers.push(buildLayer({ layer_index: 2, nodes_discovered: 2, edges_observed: 2 }, 9));
    state.layers.push(buildLayer({ layer_index: 3, nodes_discovered: 0, edges_observed: 0 }, 9));
    await expect(page.getByTestId("echo-verdict")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("echo-verdict-chip")).toHaveText("Weak structure");
    await expect(page.getByTestId("echo-timeline-row")).toHaveCount(4);

    // Continue appends a layer WITHOUT altering earlier rows.
    const beforeRows = await page.getByTestId("echo-timeline-row").allInnerTexts();
    state.status = "running";
    await page.getByTestId("echo-continue").click();
    state.status = "completed";
    state.layers.push(buildLayer({ layer_index: 4, nodes_discovered: 1, edges_observed: 1 }, 10));
    await expect(page.getByTestId("echo-timeline-row")).toHaveCount(5);
    const afterRows = await page.getByTestId("echo-timeline-row").allInnerTexts();
    expect(afterRows.slice(0, beforeRows.length)).toEqual(beforeRows);
  });

  test("stop terminates a running detection", async ({ page }) => {
    const state = makeState();
    await mockBackend(page, state, wsId, wsName);
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
    await page.getByTestId("echo-video-url").fill("https://www.youtube.com/watch?v=seed_a");
    await page.getByTestId("echo-detect-button").click();

    state.layers = [
      buildLayer({ layer_index: 0, nodes_discovered: 2, edges_observed: 0 }, 2),
      buildLayer({ layer_index: 1, nodes_discovered: 3, edges_observed: 3 }, 7),
    ];
    await expect(page.getByTestId("echo-stop")).toBeVisible({ timeout: 20_000 });

    await page.getByTestId("echo-stop").click();
    state.status = "stopped";
    state.scoreValue = null;
    state.verdict = "inconclusive";
    await expect(page.getByTestId("echo-status")).toHaveText("Stopped", {
      timeout: 20_000,
    });
    await expect(page.getByTestId("echo-verdict-chip")).toHaveText("Inconclusive");
  });
});
