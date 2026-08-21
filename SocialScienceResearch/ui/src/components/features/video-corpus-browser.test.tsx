import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, makeVideo } from "@/test-utils";
import { VideoCorpusBrowser } from "@/components/features/video-corpus-browser";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/channels/ch1",
}));

vi.mock("@/services/queries", () => ({
  useChannelVideos: vi.fn(),
  useChannelVideoCount: vi.fn(),
  useSubmitCollect: vi.fn(),
  useCancelJob: vi.fn(),
  useJob: vi.fn(),
}));

vi.mock("@/services/api", () => ({
  getJobResult: vi.fn(),
}));

import {
  useChannelVideos,
  useChannelVideoCount,
  useSubmitCollect,
  useCancelJob,
  useJob,
} from "@/services/queries";

const mockUseChannelVideos = vi.mocked(useChannelVideos);
const mockUseChannelVideoCount = vi.mocked(useChannelVideoCount);
const mockUseSubmitCollect = vi.mocked(useSubmitCollect);
const mockUseCancelJob = vi.mocked(useCancelJob);
const mockUseJob = vi.mocked(useJob);

describe("VideoCorpusBrowser", () => {
  beforeEach(() => {
    mockUseChannelVideos.mockReset();
    mockUseChannelVideoCount.mockReset();
    mockUseSubmitCollect.mockReset();
    mockUseCancelJob.mockReset();
    mockUseJob.mockReset();

    mockUseChannelVideos.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useChannelVideos>);
    mockUseChannelVideoCount.mockReturnValue({
      data: { count: 0 },
      isSuccess: true,
    } as unknown as ReturnType<typeof useChannelVideoCount>);
    mockUseSubmitCollect.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useSubmitCollect>);
    mockUseCancelJob.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useCancelJob>);
    mockUseJob.mockReturnValue({
      data: undefined,
    } as unknown as ReturnType<typeof useJob>);
  });

  it("links the comment count to the video comments tab", () => {
    mockUseChannelVideos.mockReturnValue({
      data: [
        makeVideo({
          video_id: "v1",
          title: "Video One",
          comment_count: 5,
        }),
      ],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useChannelVideos>);

    renderWithProviders(<VideoCorpusBrowser channelId="ch1" searchParams={{}} />);
    expect(screen.getByRole("link", { name: "Video One" })).toHaveAttribute("href", "/videos/v1");
    expect(screen.getByRole("link", { name: "5" })).toHaveAttribute(
      "href",
      "/videos/v1?tab=comments",
    );
  });
});