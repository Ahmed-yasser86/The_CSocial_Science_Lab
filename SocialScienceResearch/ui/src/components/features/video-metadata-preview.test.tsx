import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, makeVideo, makeEngagement } from "@/test-utils";
import { VideoMetadataPreview } from "@/components/features/video-metadata-preview";

vi.mock("@/hooks/useVideoPreview", () => ({
  useVideoPreview: vi.fn(),
  useVideoEngagementPreview: vi.fn(),
}));

import { useVideoPreview, useVideoEngagementPreview } from "@/hooks/useVideoPreview";

const mockUseVideoPreview = vi.mocked(useVideoPreview);
const mockUseVideoEngagementPreview = vi.mocked(useVideoEngagementPreview);

function mockSuccess(videoOverrides = {}, engagementOverrides = {}) {
  const video = makeVideo(videoOverrides);
  const engagement = makeEngagement(engagementOverrides);
  mockUseVideoPreview.mockReturnValue({
    data: video, isLoading: false, error: null, refetch: vi.fn(),
  } as unknown as ReturnType<typeof useVideoPreview>);
  mockUseVideoEngagementPreview.mockReturnValue({
    data: engagement, isLoading: false, error: null, refetch: vi.fn(),
  } as unknown as ReturnType<typeof useVideoEngagementPreview>);
  return { video, engagement };
}

describe("VideoMetadataPreview", () => {
  beforeEach(() => {
    mockUseVideoPreview.mockReset();
    mockUseVideoEngagementPreview.mockReset();
  });

  it("shows loading state", () => {
    mockUseVideoPreview.mockReturnValue({
      data: undefined, isLoading: true, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof useVideoPreview>);

    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("Loading video metadata…")).toBeInTheDocument();
  });

  it("shows error state with retry", async () => {
    const refetch = vi.fn();
    mockUseVideoPreview.mockReturnValue({
      data: undefined, isLoading: false, error: new Error("API error"), refetch,
    } as unknown as ReturnType<typeof useVideoPreview>);

    const user = userEvent.setup();
    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("API error")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders video metadata when data is available", () => {
    mockSuccess({ duration: 125, channel_id: "ch1", tags: ["tagA"], categories: ["education"] });
    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("Video Metadata")).toBeInTheDocument();
    expect(screen.getByText("tagA")).toBeInTheDocument();
    expect(screen.getByText("education")).toBeInTheDocument();
    expect(screen.getByText("2m 5s")).toBeInTheDocument(); // formatDuration(125)
  });

  it("shows engagement stats", () => {
    mockSuccess({ title: "Stats Test" });
    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("12,345")).toBeInTheDocument();
    expect(screen.getByText("999")).toBeInTheDocument();
  });

  it("shows video not found when no data", () => {
    mockUseVideoPreview.mockReturnValue({
      data: null, isLoading: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof useVideoPreview>);
    mockUseVideoEngagementPreview.mockReturnValue({
      data: undefined, isLoading: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof useVideoEngagementPreview>);

    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("Video not found")).toBeInTheDocument();
  });

  it("displays the is_short badge", () => {
    mockSuccess({ is_short: true, title: "Short Video" });
    renderWithProviders(
      <VideoMetadataPreview open={true} onOpenChange={() => {}} videoId="v1" />,
    );
    expect(screen.getByText("Short")).toBeInTheDocument();
  });
});
