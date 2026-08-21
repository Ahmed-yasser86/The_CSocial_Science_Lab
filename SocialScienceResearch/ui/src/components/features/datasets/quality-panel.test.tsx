import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, makeQuality } from "@/test-utils";
import { QualityPanel } from "@/components/features/datasets/quality-panel";

vi.mock("@/services/datasets", () => ({
  getDatasetQuality: vi.fn(),
}));

import { getDatasetQuality } from "@/services/datasets";

const mockGetQuality = vi.mocked(getDatasetQuality);

describe("QualityPanel", () => {
  beforeEach(() => {
    mockGetQuality.mockReset();
  });

  it("shows loading state", () => {
    mockGetQuality.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<QualityPanel datasetId="ds1" />);
    expect(screen.getByText("Loading quality…")).toBeInTheDocument();
  });

  it("renders quality metrics and column table", async () => {
    const quality = makeQuality();
    mockGetQuality.mockResolvedValue(quality);
    renderWithProviders(<QualityPanel datasetId="ds1" />);
    await waitFor(() => {
      expect(screen.getByText("Overall coverage")).toBeInTheDocument();
    });
    expect(screen.getByText("video_id")).toBeInTheDocument();
    expect(screen.getByText("title")).toBeInTheDocument();
  });

  it("shows empty state when no columns", async () => {
    const quality = makeQuality();
    quality.columns = [];
    mockGetQuality.mockResolvedValue(quality);
    renderWithProviders(<QualityPanel datasetId="ds1" />);
    await waitFor(() => {
      expect(screen.getByText("No columns reported")).toBeInTheDocument();
    });
  });
});
