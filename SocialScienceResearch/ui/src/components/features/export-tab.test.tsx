import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { ExportTab } from "@/components/features/export-tab";

vi.mock("@/services/queries", () => ({
  useExportData: vi.fn(),
}));

import { useExportData } from "@/services/queries";

const mockUseExportData = vi.mocked(useExportData);

function cast<T>(value: unknown): T {
  return value as T;
}

describe("ExportTab", () => {
  beforeEach(() => {
    mockUseExportData.mockReturnValue(
      cast({ mutateAsync: vi.fn(), isPending: false }),
    );
  });

  it("renders the export form", () => {
    renderWithProviders(<ExportTab />);
    expect(screen.getByText("Export Data")).toBeInTheDocument();
    expect(screen.getByText("Entity Type")).toBeInTheDocument();
    expect(screen.getByText("Entity IDs")).toBeInTheDocument();
    expect(screen.getByText("Columns")).toBeInTheDocument();
    expect(screen.getByText("Filename")).toBeInTheDocument();
  });

  it("shows video columns by default", () => {
    renderWithProviders(<ExportTab />);
    expect(screen.getByText("Video ID")).toBeInTheDocument();
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Duration (s)")).toBeInTheDocument();
  });

  it("disables the export button when no entity ids selected", () => {
    renderWithProviders(<ExportTab />);
    expect(screen.getByRole("button", { name: /Export to Excel/i })).toBeDisabled();
  });

  it("has select all / deselect all column buttons", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExportTab />);
    await user.click(screen.getByRole("button", { name: "Deselect all" }));
    // After deselect all, columns should be unchecked (export button disabled)
    await user.click(screen.getByRole("button", { name: "Select all" }));
    // re-checked
  });
});
