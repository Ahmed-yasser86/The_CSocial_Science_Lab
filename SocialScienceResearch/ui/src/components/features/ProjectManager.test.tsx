import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, makeProject } from "@/test-utils";

vi.mock("@/services/queries", () => ({
  useProjectList: vi.fn(),
  useCreateProject: vi.fn(),
  useUpdateProject: vi.fn(),
  useDeleteProject: vi.fn(),
  useAddDatasetToProject: vi.fn(),
  useRemoveDatasetFromProject: vi.fn(),
  useDatasetList: vi.fn(),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { ProjectManager } from "@/components/features/ProjectManager";
import {
  useProjectList,
  useDeleteProject,
  useCreateProject,
  useUpdateProject,
  useAddDatasetToProject,
  useRemoveDatasetFromProject,
  useDatasetList,
} from "@/services/queries";

const mockUseProjectList = vi.mocked(useProjectList);
const mockUseDeleteProject = vi.mocked(useDeleteProject);
const mockUseCreateProject = vi.mocked(useCreateProject);
const mockUseUpdateProject = vi.mocked(useUpdateProject);
const mockUseAddDatasetToProject = vi.mocked(useAddDatasetToProject);
const mockUseRemoveDatasetFromProject = vi.mocked(useRemoveDatasetFromProject);
const mockUseDatasetList = vi.mocked(useDatasetList);

function cast<T>(value: unknown): T {
  return value as T;
}

function makeQueryResult(overrides: Record<string, unknown> = {}) {
  return cast<ReturnType<typeof useProjectList>>({
    data: { pages: [{ items: [], next_cursor: null, has_more: false }] },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  });
}

describe("ProjectManager", () => {
  beforeEach(() => {
    mockUseProjectList.mockReturnValue(makeQueryResult({}));
    mockUseDeleteProject.mockReturnValue(cast({ mutate: vi.fn(), isPending: false }));
    mockUseCreateProject.mockReturnValue(cast({ mutate: vi.fn(), isPending: false }));
    mockUseUpdateProject.mockReturnValue(cast({ mutate: vi.fn(), isPending: false }));
    mockUseAddDatasetToProject.mockReturnValue(cast({ mutate: vi.fn(), isPending: false }));
    mockUseRemoveDatasetFromProject.mockReturnValue(cast({ mutate: vi.fn(), isPending: false }));
    mockUseDatasetList.mockReturnValue(cast({ data: [], isLoading: false, isError: false, error: null }));
  });

  it("shows loading state", () => {
    mockUseProjectList.mockReturnValue(makeQueryResult({ isLoading: true, data: undefined }));
    renderWithProviders(<ProjectManager />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows empty state when no projects", () => {
    renderWithProviders(<ProjectManager />);
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
  });

  it("renders projects and shows count", () => {
    mockUseProjectList.mockReturnValue(
      makeQueryResult({
        data: {
          pages: [{
            items: [
              makeProject({ project_id: "p1", name: "Study 2026" }),
              makeProject({ project_id: "p2", name: "Pilot" }),
            ],
            next_cursor: null,
            has_more: false,
          }],
        },
      }),
    );
    renderWithProviders(<ProjectManager />);
    expect(screen.getByText("2 projects")).toBeInTheDocument();
    expect(screen.getByText("Study 2026")).toBeInTheDocument();
    expect(screen.getByText("Pilot")).toBeInTheDocument();
  });

  it("opens new project dialog", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProjectManager />);
    await user.click(screen.getByRole("button", { name: "New project" }));
    expect(screen.getByText("New research project")).toBeInTheDocument();
  });

  it("displays project description and targets", () => {
    mockUseProjectList.mockReturnValue(
      makeQueryResult({
        data: {
          pages: [{
            items: [
              makeProject({
                project_id: "p1",
                name: "Study",
                description: "Main research study",
                targets: [{ kind: "channel" as const, url: "https://youtube.com/@channel" }],
              }),
            ],
            next_cursor: null,
            has_more: false,
          }],
        },
      }),
    );
    renderWithProviders(<ProjectManager />);
    expect(screen.getByText("Main research study")).toBeInTheDocument();
    expect(screen.getByText("channel")).toBeInTheDocument();
  });
});
