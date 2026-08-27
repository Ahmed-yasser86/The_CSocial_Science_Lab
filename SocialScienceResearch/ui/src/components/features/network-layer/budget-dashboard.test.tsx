import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test-utils";
import { BudgetDashboard } from "@/components/features/network-layer/budget-dashboard";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    for (const [suffix, body] of Object.entries(routes)) {
      if (url.includes(suffix)) return jsonResponse(body);
    }
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const STATE = {
  min_interval: 0.5,
  max_ytdl_contexts: 4,
  admits: 12,
  rate_limited: 1,
  total_waited_seconds: 3.5,
  aimd_floor: 0.125,
  aimd_ceiling: 4.0,
  in_cooldown: false,
  cooldown_remaining_seconds: 0,
};

const EVENTS = {
  events: [
    {
      ts: 1700000000,
      kind: "acquire",
      operation: "extract_video",
      run_id: "r1",
      cost: 2.0,
      waited_seconds: 0.5,
      budget_after: 10,
      reason: null,
      detail: null,
    },
    {
      ts: 1700000005,
      kind: "rate_limit",
      operation: "extract_video",
      run_id: "r1",
      reason: "429/RateLimitError",
      detail: { session: "sess1" },
    },
  ],
  min_interval: 0.5,
  max_ytdl_contexts: 4,
};

describe("BudgetDashboard", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "/api/v1/social-science");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders live rate/admits and the latest events", async () => {
    stubFetch({
      "/budget/state": STATE,
      "/budget/events": EVENTS,
    });
    renderWithProviders(<BudgetDashboard />);

    expect(await screen.findByTestId("budget-dashboard")).toBeTruthy();
    // 1 / 0.5 = 2.00 req/s
    expect(await screen.findByTestId("budget-rate")).toHaveTextContent(
      "2.00 req/s",
    );
    expect(screen.getByTestId("budget-admits")).toHaveTextContent("12");
    expect(screen.getByTestId("budget-429s")).toHaveTextContent("1");
    // newest event first -> rate_limit appears
    expect(screen.getByText(/rate_limit/)).toBeTruthy();
    expect(screen.getByText(/429\/RateLimitError/)).toBeTruthy();
  });

  it("shows a cooldown badge when the controller is backing off", async () => {
    stubFetch({
      "/budget/state": { ...STATE, in_cooldown: true, cooldown_remaining_seconds: 120 },
      "/budget/events": EVENTS,
    });
    renderWithProviders(<BudgetDashboard />);
    expect(await screen.findByTestId("budget-cooldown")).toBeTruthy();
    expect(screen.getByTestId("budget-cooldown")).toHaveTextContent("cooldown");
  });

  it("surfaces an unavailable state without crashing", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response("boom", { status: 500 });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<BudgetDashboard />);
    expect(
      await screen.findByText(/Budget telemetry is unavailable/i),
    ).toBeTruthy();
  });
});
