import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders, makeSystemFolders } from "@/test-utils";

vi.mock("@/services/queries", () => ({
  useSystemFolders: vi.fn(),
}));

import { FoldersTab } from "@/components/features/folders-tab";
import { useSystemFolders } from "@/services/queries";

const mockUseSystemFolders = vi.mocked(useSystemFolders);

function cast<T>(value: unknown): T {
  return value as T;
}

function mockQuery(overrides: Record<string, unknown> = {}) {
  return cast<ReturnType<typeof useSystemFolders>>({
    data: makeSystemFolders(),
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  });
}

describe("FoldersTab", () => {
  beforeEach(() => {
    mockUseSystemFolders.mockReset();
  });

  it("shows placeholder cards while loading", () => {
    mockUseSystemFolders.mockReturnValue(mockQuery({ isLoading: true, data: undefined }));
    const { container } = renderWithProviders(<FoldersTab />);
    const placeholders = container.querySelectorAll('[data-slot="card"]');
    expect(placeholders).toHaveLength(5);
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(5);
  });

  it("shows error state", () => {
    mockUseSystemFolders.mockReturnValue(
      mockQuery({ isError: true, error: new Error("Server down"), data: undefined }),
    );
    renderWithProviders(<FoldersTab />);
    expect(screen.getByText("Failed to load system folders")).toBeInTheDocument();
  });

  it("shows empty state when no folder data", () => {
    mockUseSystemFolders.mockReturnValue(mockQuery({ data: undefined }));
    renderWithProviders(<FoldersTab />);
    expect(screen.getByText("No folder data")).toBeInTheDocument();
  });

  it("renders folder paths", () => {
    mockUseSystemFolders.mockReturnValue(
      mockQuery({
        data: makeSystemFolders({
          workbook_path: "/data/workbook",
          transcripts_dir: "/data/transcripts",
        }),
      }),
    );
    renderWithProviders(<FoldersTab />);
    expect(screen.getByText("/data/workbook")).toBeInTheDocument();
    expect(screen.getByText("/data/transcripts")).toBeInTheDocument();
  });
});
