import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { screen } from "@testing-library/react";
import { ContentHomophilySection } from "@/components/features/content-homophily/content-homophily-section";
import type { ContentHomophilyRecord } from "@/services/contentHomophily";

/**
 * Network-layer stub: ContentHomophilySection talks through
 * services/api.request -> global fetch, so we stub fetch and route the two
 * content-homophily endpoints.
 */

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function recordFixture(
  overrides: Partial<ContentHomophilyRecord> = {},
): ContentHomophilyRecord {
  const base: ContentHomophilyRecord = {
    analysis_id: "chh_1",
    job_id: "job_1",
    status: "observed",
    params: {},
    progress: {
      current_stage: null,
      stages: {
        dataset_preparation: "done",
        transcript_collection: "done",
        embedding_preparation: "done",
        pair_sampling: "done",
        similarity_calculation: "done",
        observed_difference: "done",
        null_model: "done",
        statistical_summary: "done",
        results: "done",
      },
      log: [{ ts: "2026-01-01T00:00:00Z", message: "transcript loaded" }],
      videos_total: 10,
      videos_processed: 10,
      embeddings_reused: 8,
      embeddings_generated: 2,
      embedding_failures: 0,
      embedding_model: "fake-model",
    },
    created_at: "2026-01-01T00:00:00Z",
  };
  base.results = {
    status: "observed",
    label: "CONTENT EVIDENCE",
    within_mean_similarity: 0.74,
    between_mean_similarity: 0.43,
    observed_difference: 0.31,
    null_mean: 0.01,
    null_std: 0.04,
    z_score: 7.5,
    permutation_p_value: 0.0009,
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
    videos_targeted_for_transcripts: 100,
    max_transcript_videos: 200,
    transcript_coverage: 0.87,
    embedding_model: "gemini-embedding-2-preview",
    embedding_model_version: "1",
    analysis_run_id: "chh_1",
    disclaimers: ["Content homophily is content-level evidence only."],
  };
  return { ...base, ...overrides };
}

function stubFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    for (const [suffix, body] of Object.entries(routes)) {
      if (url.includes(suffix)) return jsonResponse(body);
    }
    return jsonResponse({ items: [], next_cursor: null, has_more: false, total: 0 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ContentHomophilySection", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "/api/v1/social-science");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the empty opt-in state when no analysis exists", async () => {
    stubFetch({
      "/network/content-homophily?": {
        items: [],
        next_cursor: null,
        has_more: false,
        total: 0,
      },
    });
    renderWithProviders(<ContentHomophilySection />);
    expect(await screen.findByTestId("chh-empty", {}, { timeout: 5000 })).toBeTruthy();
  });

  it("renders CONTENT EVIDENCE, stage checklist and embedding stats", async () => {
    const record = recordFixture();
    stubFetch({
      "/network/content-homophily/chh_1": record,
      "/network/content-homophily?": {
        items: [record],
        next_cursor: null,
        has_more: false,
        total: 1,
      },
    });
    renderWithProviders(<ContentHomophilySection />);

    expect(
      await screen.findByText("CONTENT EVIDENCE", {}, { timeout: 5000 }),
    ).toBeTruthy();
    expect(screen.getByTestId("chh-results").textContent).toContain("+0.310");
    expect(screen.getByTestId("chh-stage-checklist").textContent).toContain(
      "7. Null Model",
    );
    expect(screen.getByTestId("chh-embedding-stats").textContent).toContain(
      "8 / 2 / 0",
    );
  });

  it("labels insufficient data honestly instead of fabricating numbers", async () => {
    const observed = recordFixture();
    const insufficient = recordFixture({
      status: "insufficient_data",
      results: {
        ...observed.results!,
        status: "insufficient_data",
        within_mean_similarity: null,
        between_mean_similarity: null,
        observed_difference: null,
        transcript_coverage: 0,
      },
    });
    stubFetch({
      "/network/content-homophily/chh_1": insufficient,
      "/network/content-homophily?": {
        items: [insufficient],
        next_cursor: null,
        has_more: false,
        total: 1,
      },
    });
    renderWithProviders(<ContentHomophilySection />);

    expect(
      await screen.findByTestId("chh-results", {}, { timeout: 5000 }),
    ).toBeTruthy();
    expect(screen.getByTestId("chh-status").textContent).toContain(
      "insufficient data",
    );
  });
});
