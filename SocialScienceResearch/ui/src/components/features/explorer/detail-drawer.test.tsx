import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test-utils";
import { DetailDrawer } from "@/components/features/explorer/detail-drawer";
import type { ExplorerColumn } from "@/lib/explorer-types";

vi.mock("@/services/explorer", () => ({
  useRawRecord: vi.fn(),
  useProvenance: vi.fn(),
}));

import { useRawRecord, useProvenance } from "@/services/explorer";

const mockUseRawRecord = vi.mocked(useRawRecord);
const mockUseProvenance = vi.mocked(useProvenance);

const columns: ExplorerColumn[] = [
  {
    entity: "comment",
    name: "comment_id",
    data_type: "string",
    source: "observed",
    description: "",
    unit: null,
    availability: "available",
    limits: null,
  },
  {
    entity: "comment",
    name: "video_id",
    data_type: "string",
    source: "observed",
    description: "",
    unit: null,
    availability: "available",
    limits: null,
  },
];

function renderDrawer(row: Record<string, unknown>, entity = "comment") {
  return renderWithProviders(
    <DetailDrawer
      open={true}
      onOpenChange={() => {}}
      entity={entity}
      entityId={String(row.comment_id ?? row.video_id ?? "")}
      row={row}
      columns={columns}
    />,
  );
}

describe("DetailDrawer", () => {
  beforeEach(() => {
    mockUseRawRecord.mockReset();
    mockUseProvenance.mockReset();
    mockUseRawRecord.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRawRecord>);
    mockUseProvenance.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useProvenance>);
  });

  it("shows a View reply tree link for comment rows with a video_id", () => {
    renderDrawer({ comment_id: "c1", video_id: "v1" });
    const link = screen.getByRole("button", { name: "View reply tree" });
    expect(link).toHaveAttribute("href", "/videos/v1?tab=comments&thread=c1");
  });

  it("hides the View reply tree link when the comment has no video_id", () => {
    renderDrawer({ comment_id: "c1" });
    expect(screen.queryByRole("button", { name: "View reply tree" })).not.toBeInTheDocument();
  });

  it("does not show the View reply tree link for non-comment entities", () => {
    renderDrawer({ video_id: "v1" }, "video");
    expect(screen.queryByRole("button", { name: "View reply tree" })).not.toBeInTheDocument();
  });
});