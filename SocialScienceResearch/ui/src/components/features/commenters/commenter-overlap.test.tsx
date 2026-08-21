import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithProviders } from "@/test-utils";
import { OverlapHeatmap } from "@/components/features/commenters/overlap-heatmap";
import { OverlapPairsTable } from "@/components/features/commenters/overlap-pairs-table";
import {
  BridgeCommentersPanel,
  TopSharedCommentersPanel,
} from "@/components/features/commenters/shared-commenters-panel";
import { CommenterOverlapView } from "@/components/features/commenters/commenter-overlap-view";
import { CommenterProfileView } from "@/components/features/commenters/commenter-profile-view";
import type {
  CommenterOverlapResult,
  CommenterProfile,
  CommenterProjection,
  PairOverlap,
} from "@/lib/commenter-overlap-types";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(),
}));

vi.mock("@/services/commenters", () => ({
  useCommenterOverlap: vi.fn(),
  useCommenterProfile: vi.fn(),
}));

vi.mock("@/services/queries", () => ({
  useChannels: vi.fn(),
}));

import { useSearchParams } from "next/navigation";
import * as commenters from "@/services/commenters";
import * as queries from "@/services/queries";

const mockSearchParams = vi.mocked(useSearchParams);
const mockUseCommenterOverlap = vi.mocked(commenters.useCommenterOverlap);
const mockUseCommenterProfile = vi.mocked(commenters.useCommenterProfile);
const mockUseChannels = vi.mocked(queries.useChannels);

function makeQuery(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  };
}

function makeProjection(overrides: Partial<CommenterProjection> = {}): CommenterProjection {
  return {
    entity_type: "video",
    entities: [
      {
        entity_id: "v1",
        entity_type: "video",
        title: "First video",
        commenter_count: 3,
        comment_count: 5,
      },
      {
        entity_id: "v2",
        entity_type: "video",
        title: "Second video",
        commenter_count: 2,
        comment_count: 4,
      },
    ],
    pairs: [
      {
        entity_a: "v1",
        entity_b: "v2",
        set_size_a: 3,
        set_size_b: 2,
        intersection_size: 1,
        union_size: 4,
        unique_a: 2,
        unique_b: 1,
        jaccard: 0.25,
        overlap_coefficient: 0.5,
        reach_overlap_pct: 25,
        shared_commenters: [
          {
            author_key: "a1",
            author_name: "Alice",
            identity_kind: "id",
            count_a: 2,
            count_b: 1,
            total_comments: 3,
            first_seen_at: "2024-01-01T00:00:00Z",
            last_seen_at: "2024-01-02T00:00:00Z",
          },
        ],
        total_shared: 1,
      },
    ],
    heatmap: { v1: { v2: 0.25 }, v2: { v1: 0.25 } },
    overlap_edges: [
      { entity_a: "v1", entity_b: "v2", shared_commenter_count: 1, jaccard: 0.25 },
    ],
    bridge_commenters: [
      {
        author_key: "b1",
        author_name: "Bridget",
        identity_kind: "id",
        entity_count: 2,
        comment_count: 4,
        video_count: 2,
        channel_count: 1,
        entities: [{ entity_id: "v1", comment_count: 2 }],
      },
    ],
    top_shared_commenters: [
      {
        author_key: "t1",
        author_name: "Tara",
        identity_kind: "name",
        entity_count: 2,
        comment_count: 3,
        video_count: 2,
        channel_count: 1,
      },
    ],
    summary: {
      entity_type: "video",
      entity_count: 2,
      commenter_count: 4,
      comment_count: 9,
      unidentified_comments: 1,
      pair_count: 1,
      average_jaccard: 0.25,
      max_jaccard_pair: {
        entity_a: "v1",
        entity_b: "v2",
        jaccard: 0.25,
        intersection_size: 1,
      },
      max_shared_pair: {
        entity_a: "v1",
        entity_b: "v2",
        intersection_size: 1,
      },
      bridge_commenter_count: 1,
    },
    ...overrides,
  };
}

function makeOverlapResult(): CommenterOverlapResult {
  return {
    scope: { video_ids: ["v1", "v2"], channel_ids: [] },
    metric: "jaccard",
    videos: makeProjection(),
    channels: null,
    global_summary: {
      unique_commenters: 4,
      comment_count: 9,
      bridge_commenter_count: 1,
    },
  };
}

function makeProfile(): CommenterProfile {
  return {
    author_key: "a1",
    author_name: "Alice",
    identity_kind: "id",
    total_comments: 5,
    video_count: 2,
    channel_count: 1,
    is_author: false,
    first_seen_at: "2024-01-01T00:00:00Z",
    last_seen_at: "2024-01-02T00:00:00Z",
    videos: [
      {
        video_id: "v1",
        channel_id: "ch1",
        channel_name: "Channel One",
        comment_count: 3,
        root_count: 2,
        reply_count: 1,
        reply_to_count: 0,
      },
    ],
    channels: [
      {
        channel_id: "ch1",
        channel_name: "Channel One",
        comment_count: 3,
        video_count: 1,
        root_count: 2,
        reply_count: 1,
      },
    ],
    comments: [
      {
        comment_id: "c1",
        video_id: "v1",
        comment_text: "Hello world",
        published_at: "2024-01-01T10:00:00Z",
        is_reply: false,
        like_count: 5,
        is_author: false,
      },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSearchParams.mockReturnValue({
    get: vi.fn().mockReturnValue(null),
    getAll: vi.fn().mockReturnValue([]),
  } as never);
  mockUseChannels.mockReturnValue(
    makeQuery({ data: [] }) as never,
  );
});

describe("OverlapHeatmap", () => {
  it("renders cells with aria labels and omits the diagonal", () => {
    renderWithProviders(
      <OverlapHeatmap projection={makeProjection()} />,
    );
    const grid = screen.getByTestId("overlap-heatmap");
    expect(within(grid).getByLabelText("overlap 0.250 between v1 and v2")).toBeInTheDocument();
    expect(within(grid).getByLabelText("overlap 0.250 between v2 and v1")).toBeInTheDocument();
    expect(within(grid).queryByLabelText(/overlap .* between v1 and v1/)).not.toBeInTheDocument();
  });

  it("renders a placeholder for empty cells", () => {
    renderWithProviders(
      <OverlapHeatmap projection={makeProjection({ heatmap: {} })} />,
    );
    const grid = screen.getByTestId("overlap-heatmap");
    expect(within(grid).getAllByRole("button")).toHaveLength(2);
  });
});

describe("OverlapPairsTable", () => {
  const pairs: PairOverlap[] = [makeProjection().pairs[0]];

  it("renders pair rows with metric values", () => {
    renderWithProviders(<OverlapPairsTable pairs={pairs} />);
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("0.250")).toBeInTheDocument();
  });

  it("expands shared commenters for a selected pair", async () => {
    const { user } = renderWithProviders(<OverlapPairsTable pairs={pairs} />);
    await user.click(screen.getByText("v1"));
    expect(screen.getByText(/Shared commenters: v1 ↔ v2/)).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });
});

describe("Shared commenter panels", () => {
  it("renders bridge and top-shared commenters with profile links", () => {
    const projection = makeProjection();
    renderWithProviders(
      <BridgeCommentersPanel commenters={projection.bridge_commenters} />,
    );
    expect(screen.getByText("Bridge commenters")).toBeInTheDocument();
    expect(screen.getByText("Bridget")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Bridget" }).getAttribute("href"),
    ).toBe("/network/commenters/b1");

    renderWithProviders(
      <TopSharedCommentersPanel commenters={projection.top_shared_commenters} />,
    );
    expect(screen.getByText("Tara")).toBeInTheDocument();
  });
});

describe("CommenterOverlapView", () => {
  it("shows an empty state before a scope is applied", () => {
    mockUseCommenterOverlap.mockReturnValue(makeQuery() as never);
    renderWithProviders(<CommenterOverlapView />);
    expect(screen.getByText("No scope selected")).toBeInTheDocument();
  });

  it("applies a scope and renders results", async () => {
    mockUseCommenterOverlap.mockReturnValue(
      makeQuery({ data: makeOverlapResult() }) as never,
    );
    const { user } = renderWithProviders(<CommenterOverlapView />);
    await user.type(
      screen.getByLabelText("Video IDs"),
      "v1, v2",
    );
    await user.click(screen.getByRole("button", { name: /Analyze/ }));
    expect(mockUseCommenterOverlap).toHaveBeenCalled();
    expect(screen.getByTestId("commenter-overlap-results")).toBeInTheDocument();
    expect(screen.getByText("Unique commenters")).toBeInTheDocument();
    expect(screen.getByTestId("overlap-heatmap")).toBeInTheDocument();
    expect(screen.getByText("Shared count")).toBeInTheDocument();
  });
});

describe("CommenterProfileView", () => {
  it("renders the profile header and videos table", () => {
    mockUseCommenterProfile.mockReturnValue(
      makeQuery({ data: makeProfile() }) as never,
    );
    renderWithProviders(<CommenterProfileView authorKey="a1" />);
    expect(screen.getByTestId("commenter-profile")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("Channel One")).toBeInTheDocument();
  });

  it("renders comments tab", async () => {
    mockUseCommenterProfile.mockReturnValue(
      makeQuery({ data: makeProfile() }) as never,
    );
    const { user } = renderWithProviders(<CommenterProfileView authorKey="a1" />);
    await user.click(screen.getByRole("tab", { name: /Comments/ }));
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    mockUseCommenterProfile.mockReturnValue(makeQuery() as never);
    renderWithProviders(<CommenterProfileView authorKey="a1" />);
    expect(screen.getByText("No profile found")).toBeInTheDocument();
  });
});
