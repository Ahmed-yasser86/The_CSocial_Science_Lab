import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, makeRunVideo } from "@/test-utils";
import { RunVideosBrowser } from "@/components/features/run-videos-browser";

vi.mock("@/services/queries", () => ({
  useRunVideos: vi.fn(),
}));

import { useRunVideos } from "@/services/queries";

const mockUseRunVideos = vi.mocked(useRunVideos);

function cast<T>(value: unknown): T {
  return value as T;
}

function runVideosResult(overrides: Record<string, unknown> = {}) {
  return cast<ReturnType<typeof useRunVideos>>({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  });
}

describe("RunVideosBrowser", () => {
  beforeEach(() => {
    mockUseRunVideos.mockReset();
  });

  it("shows loading state", () => {
    mockUseRunVideos.mockReturnValue(runVideosResult({ isLoading: true }));
    renderWithProviders(<RunVideosBrowser runId="r1" />);
    expect(screen.getByText("Loading videos…")).toBeInTheDocument();
  });

  it("shows error state with retry", async () => {
    const refetch = vi.fn();
    mockUseRunVideos.mockReturnValue(
      runVideosResult({ isError: true, error: new Error("Cannot fetch"), refetch }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RunVideosBrowser runId="r1" />);
    expect(screen.getByText("Failed to load videos")).toBeInTheDocument();
    await user.click(screen.getByText("Retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("shows empty state when no videos", () => {
    mockUseRunVideos.mockReturnValue(runVideosResult({ data: [] }));
    renderWithProviders(<RunVideosBrowser runId="r1" />);
    expect(screen.getByText("No videos found")).toBeInTheDocument();
  });

  it("renders video list with title links", async () => {
    const videos = [
      makeRunVideo({ video_id: "v1", title: "Video One", upload_date: "2024-01-15", duration: 120, tags: ["tagA"] }),
      makeRunVideo({ video_id: "v2", title: "Video Two", upload_date: "2024-02-20", duration: 300, tags: [] }),
    ];
    mockUseRunVideos.mockReturnValue(runVideosResult({ data: videos }));
    renderWithProviders(<RunVideosBrowser runId="r1" />);
    await waitFor(() => {
      expect(screen.getByText("Video One")).toBeInTheDocument();
      expect(screen.getByText("Video Two")).toBeInTheDocument();
    });
  });
});
