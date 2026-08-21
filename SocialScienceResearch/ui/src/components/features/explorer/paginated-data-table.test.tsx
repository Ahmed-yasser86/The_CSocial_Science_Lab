import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import Link from "next/link";
import { PaginatedDataTable } from "@/components/features/explorer/paginated-data-table";
import type { ExplorerColumn } from "@/lib/explorer-types";

function makeColumns(entity: string): ExplorerColumn[] {
  const base = {
    entity: entity as ExplorerColumn["entity"],
    data_type: "string",
    source: "observed",
    description: "",
    unit: null,
    availability: "available",
    limits: null,
  };
  return [
    { ...base, name: `${entity}_id` },
    { ...base, name: "title" },
  ];
}

function noop() {}

function renderTable({
  entity = "video",
  rows,
  renderIdCell,
  renderExpandedActions,
}: {
  entity?: string;
  rows: Record<string, unknown>[];
  renderIdCell?: (value: string, row: Record<string, unknown>) => React.ReactNode;
  renderExpandedActions?: (row: Record<string, unknown>) => React.ReactNode;
}) {
  return renderWithProviders(
    <PaginatedDataTable
      entity={entity as ExplorerColumn["entity"]}
      columns={makeColumns(entity)}
      rows={rows}
      total={rows.length}
      hasMore={false}
      nextCursor={null}
      isFetching={false}
      onNext={noop}
      onPrev={noop}
      hasPrevious={false}
      renderIdCell={renderIdCell}
      renderExpandedActions={renderExpandedActions}
    />,
  );
}

describe("PaginatedDataTable", () => {
  it("renders the id cell as a link when renderIdCell is provided", () => {
    renderTable({
      rows: [{ video_id: "v1", title: "Video One" }],
      renderIdCell: (value, row) => (
        <Link href={`/videos/${row.video_id}`}>{value}</Link>
      ),
    });
    const link = screen.getByRole("link", { name: "v1" });
    expect(link).toHaveAttribute("href", "/videos/v1");
  });

  it("falls back to plain text id cell when renderIdCell returns null", () => {
    renderTable({
      rows: [{ video_id: "v1", title: "Video One" }],
      renderIdCell: () => null,
    });
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("renders expanded actions for a comment row", async () => {
    const user = userEvent.setup();
    renderTable({
      entity: "comment",
      rows: [{ comment_id: "c1", video_id: "v1", title: "A comment" }],
      renderExpandedActions: (row) => (
        <Link href={`/videos/${row.video_id}?tab=comments&thread=${row.comment_id}`}>
          View reply tree
        </Link>
      ),
    });
    await user.click(screen.getByRole("button", { name: "Show details" }));
    const link = screen.getByRole("link", { name: "View reply tree" });
    expect(link).toHaveAttribute("href", "/videos/v1?tab=comments&thread=c1");
  });
});