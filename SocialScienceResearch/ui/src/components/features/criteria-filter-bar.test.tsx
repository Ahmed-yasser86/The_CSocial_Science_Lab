import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";

vi.mock("@/services/queries", () => ({
  useResearchVariables: vi.fn(),
}));

import { CriteriaFilterBar } from "@/components/features/criteria-filter-bar";
import { useResearchVariables } from "@/services/queries";

const mockUseResearchVariables = vi.mocked(useResearchVariables);

function cast<T>(value: unknown): T {
  return value as T;
}

function mockVariables() {
  mockUseResearchVariables.mockReturnValue(
    cast({
      data: [
        { entity: "video", name: "view_count", data_type: "int", source: "observed", description: "", unit: null, availability: "available", limits: null },
        { entity: "video", name: "title", data_type: "string", source: "observed", description: "", unit: null, availability: "available", limits: null },
        { entity: "video", name: "upload_date", data_type: "datetime", source: "observed", description: "", unit: null, availability: "available", limits: null },
        { entity: "video", name: "is_short", data_type: "bool", source: "observed", description: "", unit: null, availability: "available", limits: null },
      ],
      isLoading: false,
      isError: false,
      error: null,
    }),
  );
}

describe("CriteriaFilterBar", () => {
  beforeEach(() => {
    mockUseResearchVariables.mockReset();
  });

  it("renders without crashing when variables are available", () => {
    mockVariables();
    renderWithProviders(<CriteriaFilterBar entity="video" onChange={() => {}} />);
    expect(screen.getByText("Criteria filters")).toBeInTheDocument();
  });

  it("shows preset buttons for video entity", () => {
    mockVariables();
    renderWithProviders(<CriteriaFilterBar entity="video" onChange={() => {}} />);
    expect(screen.getByText("Top 10% by views")).toBeInTheDocument();
    expect(screen.getByText("Long-form (>10min)")).toBeInTheDocument();
    expect(screen.getByText("Shorts only")).toBeInTheDocument();
  });

  it("shows preset buttons for comment entity", () => {
    mockUseResearchVariables.mockReturnValue(cast({ data: [] }));
    renderWithProviders(<CriteriaFilterBar entity="comment" onChange={() => {}} />);
    expect(screen.getByText("Many likes (>100)")).toBeInTheDocument();
    expect(screen.getByText("Recent")).toBeInTheDocument();
  });

  it("applies a preset and calls onChange with the condition", async () => {
    const onChange = vi.fn();
    mockVariables();
    const user = userEvent.setup();
    renderWithProviders(<CriteriaFilterBar entity="video" onChange={onChange} />);
    await user.click(screen.getByText("Shorts only"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        operator: "AND",
        conditions: expect.arrayContaining([
          expect.objectContaining({ variable: "is_short", operator: "eq", value: true }),
        ]),
      }),
    );
  });

  it("calls onChange when adding a custom condition", async () => {
    const onChange = vi.fn();
    mockVariables();
    const user = userEvent.setup();
    renderWithProviders(<CriteriaFilterBar entity="video" onChange={onChange} />);
    // Open the variable select and pick one
    const variableTrigger = screen.getAllByRole("combobox")[0];
    await user.click(variableTrigger);
    await user.click(screen.getByText(/view_count/));
    // Click Add
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(onChange).toHaveBeenCalled();
    const lastArg = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastArg.conditions.length).toBeGreaterThanOrEqual(1);
  });
});
