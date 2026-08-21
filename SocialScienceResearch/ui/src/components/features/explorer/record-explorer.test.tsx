import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { RecordExplorer } from "@/components/features/explorer/record-explorer";
import type { ExplorePage } from "@/lib/explorer-types";

vi.mock("@/services/explorer", () => ({
  useExploreRecords: vi.fn(),
}));

vi.mock("@/hooks/useVideoPreview", () => ({
  useVideoPreview: vi.fn(),
  useVideoEngagementPreview: vi.fn(),
}));

import { useExploreRecords } from "@/services/explorer";
import { useVideoPreview, useVideoEngagementPreview } from "@/hooks/useVideoPreview";

const mockUseExploreRecords = vi.mocked(useExploreRecords);
const mockUseVideoPreview = vi.mocked(useVideoPreview);
const mockUseVideoEngagementPreview = vi.mocked(useVideoEngagementPreview);

function makeColumns(entity: string, names: string[]): ExplorePage["columns"] {
  const base = {
    entity: entity as ExplorePage["entity"],
    data_type: "string",
    source: "observed",
    description: "",
    unit: null,
    availability: "available",
    limits: null,
  };
  return names.map((name) => ({ ...base, name }));
}

function makePage(entity: string, items: Record<string, unknown>[]): ExplorePage {
  return {
    entity: entity as ExplorePage["entity"],
    columns: items.length > 0 ? makeColumns(entity, Object.keys(items[0])) : [],
    items,
    next_cursor: null,
    has_more: false,
    total: items.length,
    sort_options: [],
  };
}

function mockSuccess(entity: string, items: Record<string, unknown>[]) {
  mockUseExploreRecords.mockReturnValue({
    data: makePage(entity, items),
    isLoading: false,
    isError: false,
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useExploreRecords>);
}

describe("RecordExplorer", () => {
  beforeEach(() => {
    mockUseExploreRecords.mockReset();
    mockUseVideoPreview.mockReset();
    mockUseVideoEngagementPreview.mockReset();
    mockUseVideoPreview.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useVideoPreview>);
    mockUseVideoEngagementPreview.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useVideoEngagementPreview>);
  });

  it("links video rows to their detail page", () => {
    mockSuccess("video", [{ video_id: "v1", title: "Video One" }]);
    renderWithProviders(<RecordExplorer initialEntity="video" />);
    const link = screen.getByRole("link", { name: "v1" });
    expect(link).toHaveAttribute("href", "/videos/v1");
  });

  it("links channel rows to their detail page", () => {
    mockSuccess("channel", [{ channel_id: "ch1", title: "Channel One" }]);
    renderWithProviders(<RecordExplorer initialEntity="channel" />);
    const link = screen.getByRole("link", { name: "ch1" });
    expect(link).toHaveAttribute("href", "/channels/ch1");
  });

  it("does not link comment id cells", () => {
    mockSuccess("comment", [{ comment_id: "c1", video_id: "v1", comment_text: "Hi" }]);
    renderWithProviders(<RecordExplorer initialEntity="comment" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows a View reply tree action for comment rows with a video_id", async () => {
    const user = userEvent.setup();
    mockSuccess("comment", [{ comment_id: "c1", video_id: "v1", comment_text: "Hi" }]);
    renderWithProviders(<RecordExplorer initialEntity="comment" />);
    await user.click(screen.getByRole("button", { name: "Show details" }));
    const action = screen.getByRole("button", { name: "View reply tree" });
    expect(action).toHaveAttribute("href", "/videos/v1?tab=comments&thread=c1");
  });

  it("hides the View reply tree action when a comment has no video_id", async () => {
    const user = userEvent.setup();
    mockSuccess("comment", [{ comment_id: "c1", comment_text: "Hi" }]);
    renderWithProviders(<RecordExplorer initialEntity="comment" />);
    await user.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.queryByRole("button", { name: "View reply tree" })).not.toBeInTheDocument();
    expect(screen.getByText("Open record")).toBeInTheDocument();
  });

  it("keeps the drawer as a secondary action for video rows", async () => {
    const user = userEvent.setup();
    mockSuccess("video", [{ video_id: "v1", title: "Video One" }]);
    renderWithProviders(<RecordExplorer initialEntity="video" />);
    await user.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByRole("button", { name: "View details" })).toHaveAttribute("href", "/videos/v1");
    expect(screen.getByText("Open record")).toBeInTheDocument();
  });
});