import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";

const crawlMutate = vi.fn();

vi.mock("@/services/networkLayer", () => ({
  useLayers: vi.fn(() => ({ data: [], isLoading: false })),
  useCrawlNextLayer: vi.fn(() => ({
    mutate: crawlMutate,
    isPending: false,
    isRunning: false,
    isError: false,
    error: null,
    jobId: null,
    job: undefined,
  })),
  useBootstrapLayer: vi.fn(),
}));

vi.mock("@/services/networkFull", () => ({
  useNetworkGraph: vi.fn(() => ({ data: undefined, isError: false, error: null })),
}));

vi.mock("@/components/features/network-layer/layer-stepper", () => ({
  LayerStepper: ({ onStartCrawl }: { onStartCrawl: (body: unknown) => void }) => (
    <button type="button" onClick={() => onStartCrawl({
      parent_layer_run_id: "lyr_1",
      projection: "video",
      collect_comments: true,
    })}>
      start-crawl
    </button>
  ),
}));

vi.mock("@/components/features/network-layer/new-relations-panel", () => ({
  NewRelationsPanel: () => <div />,
}));
vi.mock("@/components/features/network-layer/layer-graph", () => ({
  LayerGraph: () => <div />,
}));
vi.mock("@/components/features/network-layer/scraper-config-panel", () => ({
  ScraperConfigPanel: () => <div />,
}));
vi.mock("@/components/features/network-graph", () => ({
  NetworkGraph: () => <div />,
}));

import { LayerPanel } from "@/components/features/network-layer/layer-panel";

describe("LayerPanel discovery mode selection", () => {
  beforeEach(() => {
    crawlMutate.mockReset();
  });

  it("explains both discovery modes with helper text", () => {
    renderWithProviders(<LayerPanel runId="run_1" />);
    // Default mode is rescrape_known; its helper text is visible.
    expect(
      screen.getByText(/Re-observes the resolved frontier/i),
    ).toBeInTheDocument();
    // The frontier alternative is offered by the selector.
    expect(
      screen.getByLabelText("Select discovery mode"),
    ).toBeInTheDocument();
  });

  it("merges the default rescrape_known mode into the crawl request", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LayerPanel runId="run_1" />);
    await user.click(screen.getByText("start-crawl"));
    expect(crawlMutate).toHaveBeenCalledWith(
      expect.objectContaining({ discovery_mode: "rescrape_known" }),
      expect.anything(),
    );
  });

  it("sends frontier mode after switching the selector", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LayerPanel runId="run_1" />);
    await user.click(screen.getByLabelText("Select discovery mode"));
    await user.click(screen.getByRole("option", { name: /New frontier only/i }));
    await user.click(screen.getByText("start-crawl"));
    expect(crawlMutate).toHaveBeenCalledWith(
      expect.objectContaining({ discovery_mode: "frontier" }),
      expect.anything(),
    );
  });
});
