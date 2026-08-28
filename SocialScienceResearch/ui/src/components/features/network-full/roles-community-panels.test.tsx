import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  CommenterRolesPanel,
  CommenterCommunityInsightsPanel,
} from "./roles-community-panels";

vi.mock("@/services/networkFull", () => ({
  useCommenterNetworkRoles: vi.fn(),
  useCommenterNetworkCommunityInsights: vi.fn(),
  useNetworkRoles: vi.fn(),
  useNetworkCommunityInsights: vi.fn(),
}));

// Import after the mock is registered.
import {
  useCommenterNetworkRoles,
  useCommenterNetworkCommunityInsights,
} from "@/services/networkFull";

const okQuery = (data: unknown) => ({
  data,
  isLoading: false,
  isError: false,
  error: null,
  refetch: vi.fn(),
});

const rolesData = {
  nodes: {
    "@core1": { role: "core", community_id: 3 },
    "@core2": { role: "core", community_id: 1 },
    "@broker1": { role: "broker", community_id: 0 },
    "@bridge1": { role: "bridge", community_id: 1 },
    "@periph1": { role: "periphery", community_id: 2 },
  },
  role_model: "louvain",
  algorithm: "louvain",
  computed_at: "2026-08-24T00:00:00Z",
};

// Commenter community insight that also carries dominant_channels + eigenvector
// (this is what the live commenter endpoint returns, so Top core renders).
const commDataWithCore = {
  communities: [
    {
      community_id: 5,
      size: 297,
      dominant_channels: [],
      top_eigenvector: [
        { id: "@coreA", label: "@coreA", value: 0.145 },
        { id: "@coreB", label: "@coreB", value: 0.04 },
      ],
      top_betweenness: [
        { id: "@bridgeA", label: "@bridgeA", value: 0.05 },
        { id: "@bridgeB", label: "@bridgeB", value: 0.02 },
      ],
    },
  ],
  algorithm: "louvain",
  computed_at: "2026-08-24T00:00:00Z",
};

// Typed CommenterCommunityInsight (no dominant_channels) — only Top bridges.
const commDataBridgesOnly = {
  communities: [
    {
      community_id: 5,
      size: 297,
      dominant_kinds: { commenter: 296, video: 1 },
      top_bridges: [
        { id: "@bridgeA", label: "@bridgeA", betweenness: 0.05 },
        { id: "@bridgeB", label: "@bridgeB", betweenness: 0.02 },
      ],
    },
  ],
  algorithm: "louvain",
  computed_at: "2026-08-24T00:00:00Z",
};

describe("commenter handle clickability (new feature)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders role handles as buttons that fire onSelectCommenter (Structural roles)", () => {
    vi.mocked(useCommenterNetworkRoles).mockReturnValue(okQuery(rolesData) as never);
    const onSelect = vi.fn();

    render(
      <CommenterRolesPanel
        runId="run_x"
        projection="commenter"
        weight="co_comment:jaccard"
        onSelectCommenter={onSelect}
      />,
    );

    // Structural roles heading + per-role counts render.
    expect(screen.getByText("Structural roles")).toBeInTheDocument();
    expect(screen.getByText("core: 2")).toBeInTheDocument();
    expect(screen.getByText("broker: 1")).toBeInTheDocument();

    const coreHandle = screen.getByRole("button", { name: "@core1" });
    expect(coreHandle).toBeInTheDocument();
    fireEvent.click(coreHandle);
    expect(onSelect).toHaveBeenCalledWith("@core1");

    const brokerHandle = screen.getByRole("button", { name: "@broker1" });
    fireEvent.click(brokerHandle);
    expect(onSelect).toHaveBeenCalledWith("@broker1");
  });

  it("fires onSelectCommenter for Top core + Top bridges handles (commenter insight with core)", () => {
    vi.mocked(useCommenterNetworkCommunityInsights).mockReturnValue(
      okQuery(commDataWithCore) as never,
    );
    const onSelect = vi.fn();

    render(
      <CommenterCommunityInsightsPanel
        runId="run_x"
        projection="commenter"
        weight="co_comment:jaccard"
        onSelectCommenter={onSelect}
      />,
    );

    expect(screen.getByText("Community 5")).toBeInTheDocument();
    expect(screen.getByText("Top core (eigenvector)")).toBeInTheDocument();
    expect(screen.getByText("Top bridges (betweenness)")).toBeInTheDocument();

    const coreHandle = screen.getByRole("button", { name: "@coreA" });
    fireEvent.click(coreHandle);
    expect(onSelect).toHaveBeenCalledWith("@coreA");

    const bridgeHandle = screen.getByRole("button", { name: "@bridgeA" });
    fireEvent.click(bridgeHandle);
    expect(onSelect).toHaveBeenCalledWith("@bridgeA");
  });

  it("fires onSelectCommenter for Top bridges when only bridges are present", () => {
    vi.mocked(useCommenterNetworkCommunityInsights).mockReturnValue(
      okQuery(commDataBridgesOnly) as never,
    );
    const onSelect = vi.fn();

    render(
      <CommenterCommunityInsightsPanel
        runId="run_x"
        projection="commenter"
        weight="co_comment:jaccard"
        onSelectCommenter={onSelect}
      />,
    );

    expect(screen.getByText(/Node kinds/)).toBeInTheDocument();
    // No eigenvector data -> Top core list is empty.
    expect(screen.queryByRole("button", { name: "@coreA" })).toBeNull();

    const bridgeHandle = screen.getByRole("button", { name: "@bridgeA" });
    fireEvent.click(bridgeHandle);
    expect(onSelect).toHaveBeenCalledWith("@bridgeA");
  });
});
