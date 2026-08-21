import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, makeDataset } from "@/test-utils";
import { DatasetLibrary } from "@/components/features/datasets/dataset-library";
import { useDatasetList } from "@/services/queries";

vi.mock("@/services/datasets", () => ({
  listDatasets: vi.fn(),
  getDatasetMembers: vi.fn(),
  getDatasetExportUrl: vi.fn(() => "/export/ds1/csv"),
  deleteDataset: vi.fn(),
  getDatasetQuality: vi.fn(),
}));

import { listDatasets, deleteDataset } from "@/services/datasets";

const mockListDatasets = vi.mocked(listDatasets);
const mockDeleteDataset = vi.mocked(deleteDataset);

function DatasetListProbe() {
  const query = useDatasetList();
  return <span data-testid="pages-count">{query.data?.pages?.length ?? "none"}</span>;
}

describe("DatasetLibrary", () => {
  beforeEach(() => {
    mockListDatasets.mockReset();
    mockDeleteDataset.mockReset();
  });

  it("shows loading state", () => {
    mockListDatasets.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<DatasetLibrary />);
    expect(screen.getByText("Loading datasets…")).toBeInTheDocument();
  });

  it("shows empty state when no datasets", async () => {
    mockListDatasets.mockResolvedValue({ items: [], next_cursor: null, has_more: false, total: 0 });
    renderWithProviders(<DatasetLibrary />);
    await waitFor(() => {
      expect(screen.getByText("No datasets yet")).toBeInTheDocument();
    });
  });

  it("renders a list of datasets", async () => {
    mockListDatasets.mockResolvedValue({
      items: [
        makeDataset({ dataset_id: "ds1", name: "Alpha", member_count: 42 }),
        makeDataset({ dataset_id: "ds2", name: "Beta", member_count: 100 }),
      ],
      next_cursor: null,
      has_more: false,
      total: 2,
    });
    renderWithProviders(<DatasetLibrary />);
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
      expect(screen.getByText("Beta")).toBeInTheDocument();
    });
    expect(screen.getByText("2 datasets")).toBeInTheDocument();
  });

  it("opens the new dataset dialog", async () => {
    mockListDatasets.mockResolvedValue({ items: [], next_cursor: null, has_more: false, total: 0 });
    const user = userEvent.setup();
    renderWithProviders(<DatasetLibrary />);
    await waitFor(() => expect(screen.getByText("No datasets yet")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "New dataset" }));
    // The dialog header should contain the title
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("keeps the library key distinct from the infinite dataset-list key", async () => {
    // Regression: a plain useQuery writing a bare Paginated under the same
    // ["datasets"] key as useDatasetList's infinite query crashes React Query's
    // hasNextPage with "Cannot read properties of undefined (reading 'length')".
    mockListDatasets.mockResolvedValue({
      items: [makeDataset({ dataset_id: "ds1", name: "Alpha" })],
      next_cursor: null,
      has_more: false,
      total: 1,
    });
    const { queryClient } = renderWithProviders(
      <>
        <DatasetLibrary />
        <DatasetListProbe />
      </>,
    );
    await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("pages-count").textContent).toBe("1"));

    const libraryData = queryClient.getQueryData(["datasets", "library"]) as {
      items?: unknown[];
    } | null;
    expect(libraryData).toEqual(expect.objectContaining({ items: expect.any(Array) }));

    const infiniteData = queryClient.getQueryData(["datasets"]) as
      | { pages?: unknown[] }
      | null;
    expect(Array.isArray(infiniteData?.pages)).toBe(true);
  });
});
