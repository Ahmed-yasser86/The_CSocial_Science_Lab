import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  UseInfiniteQueryResult,
  UseMutationResult,
  UseQueryResult,
} from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { renderWithProviders, makeProject } from "@/test-utils";
import type {
  CreateProjectItemInput,
  Dataset,
  Paginated,
  Project,
  ProjectItem,
  ProjectItemDeleteResult,
  UpdateProjectItemInput,
} from "@/lib/dataset-types";
import type { Sample } from "@/lib/sample-types";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
}));

vi.mock("@/services/queries", () => ({
  useProject: vi.fn(),
  useProjectItems: vi.fn(),
  useDeleteProjectItem: vi.fn(),
  useCreateProjectItem: vi.fn(),
  useProjectItem: vi.fn(),
  useUpdateProjectItem: vi.fn(),
  useAddSamplesToItem: vi.fn(),
  useRemoveSamplesFromItem: vi.fn(),
  useAddDatasetsToItem: vi.fn(),
  useRemoveDatasetsFromItem: vi.fn(),
  useDatasetList: vi.fn(),
}));

vi.mock("@/services/samples", () => ({
  useSampleList: vi.fn(),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { ProjectDetail } from "@/components/features/datasets/project-detail";
import { ProjectItemDetail } from "@/components/features/datasets/project-item-detail";
import {
  useProject,
  useProjectItems,
  useDeleteProjectItem,
  useCreateProjectItem,
  useProjectItem,
  useUpdateProjectItem,
  useAddSamplesToItem,
  useRemoveSamplesFromItem,
  useAddDatasetsToItem,
  useRemoveDatasetsFromItem,
  useDatasetList,
} from "@/services/queries";
import { useSampleList } from "@/services/samples";

const mockUseProject = vi.mocked(useProject);
const mockUseProjectItems = vi.mocked(useProjectItems);
const mockUseDeleteProjectItem = vi.mocked(useDeleteProjectItem);
const mockUseCreateProjectItem = vi.mocked(useCreateProjectItem);
const mockUseProjectItem = vi.mocked(useProjectItem);
const mockUseUpdateProjectItem = vi.mocked(useUpdateProjectItem);
const mockUseAddSamplesToItem = vi.mocked(useAddSamplesToItem);
const mockUseRemoveSamplesFromItem = vi.mocked(useRemoveSamplesFromItem);
const mockUseAddDatasetsToItem = vi.mocked(useAddDatasetsToItem);
const mockUseRemoveDatasetsFromItem = vi.mocked(useRemoveDatasetsFromItem);
const mockUseDatasetList = vi.mocked(useDatasetList);
const mockUseSampleList = vi.mocked(useSampleList);

function makeProjectItem(overrides: Partial<ProjectItem> = {}): ProjectItem {
  return {
    item_id: "i1",
    project_id: "p1",
    name: "Sample item",
    description: null,
    item_type: "sample_group",
    sample_ids: [],
    dataset_ids: [],
    tags: [],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

type ItemMutation = UseMutationResult<
  ProjectItem,
  Error,
  { projectId: string; itemId: string; sampleIds: string[] },
  unknown
>;

function makeProjectQuery(
  overrides: Record<string, unknown> = {},
): UseQueryResult<Project, Error> {
  return {
    data: makeProject({ project_id: "p1", name: "Study", description: "A study" }),
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as unknown as UseQueryResult<Project, Error>;
}

function makeItemsQuery(
  items: ProjectItem[],
  overrides: Record<string, unknown> = {},
): UseQueryResult<Paginated<ProjectItem>, Error> {
  return {
    data: { items, next_cursor: null, has_more: false, total: items.length },
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as unknown as UseQueryResult<Paginated<ProjectItem>, Error>;
}

function makeItemQuery(
  item: ProjectItem,
  overrides: Record<string, unknown> = {},
): UseQueryResult<ProjectItem, Error> {
  return {
    data: item,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as unknown as UseQueryResult<ProjectItem, Error>;
}

function makeInfiniteQuery<T>(
  items: T[],
): UseInfiniteQueryResult<InfiniteData<Paginated<T>, unknown>, Error> {
  return {
    data: {
      pages: [{ items, next_cursor: null, has_more: false, total: items.length }],
      pageParams: [],
    },
    isLoading: false,
    isError: false,
    error: null,
  } as unknown as UseInfiniteQueryResult<InfiniteData<Paginated<T>, unknown>, Error>;
}

function makeMutation<TData, TVariables>(
  mutate: (
    variables: TVariables,
    options?: { onSuccess?: (data: TData) => void },
  ) => void,
  overrides: Record<string, unknown> = {},
): UseMutationResult<TData, Error, TVariables, unknown> {
  return {
    mutate,
    isPending: false,
    ...overrides,
  } as unknown as UseMutationResult<TData, Error, TVariables, unknown>;
}

describe("ProjectDetail", () => {
  beforeEach(() => {
    pushMock.mockReset();
    mockUseProject.mockReturnValue(makeProjectQuery());
    mockUseProjectItems.mockReturnValue(makeItemsQuery([]));
    mockUseDeleteProjectItem.mockReturnValue(
      makeMutation<ProjectItemDeleteResult, { projectId: string; itemId: string }>(
        vi.fn(),
      ),
    );
    mockUseCreateProjectItem.mockReturnValue(
      makeMutation<ProjectItem, { projectId: string; body: CreateProjectItemInput }>(
        vi.fn(),
      ),
    );
  });

  it("renders project details and its items list", () => {
    mockUseProjectItems.mockReturnValue(
      makeItemsQuery([
        makeProjectItem({ item_id: "i1", name: "Group A", item_type: "sample_group" }),
        makeProjectItem({ item_id: "i2", name: "Group B", item_type: "mixed" }),
      ]),
    );
    renderWithProviders(<ProjectDetail projectId="p1" />);
    expect(screen.getByText("Study")).toBeInTheDocument();
    expect(screen.getByText("A study")).toBeInTheDocument();
    expect(screen.getByText("2 project items")).toBeInTheDocument();
    expect(screen.getByText("Group A")).toBeInTheDocument();
    expect(screen.getByText("Group B")).toBeInTheDocument();
  });

  it("opens the new item dialog", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProjectDetail projectId="p1" />);
    await user.click(screen.getByRole("button", { name: "New item" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("New project item")).toBeInTheDocument();
  });

  it("navigates to the item detail page when an item is clicked", async () => {
    const user = userEvent.setup();
    mockUseProjectItems.mockReturnValue(
      makeItemsQuery([makeProjectItem({ item_id: "i1", name: "Group A" })]),
    );
    renderWithProviders(<ProjectDetail projectId="p1" />);
    await user.click(screen.getByText("Group A"));
    expect(pushMock).toHaveBeenCalledWith("/projects/p1/items/i1");
  });

  it("navigates to the created item detail page after creating an item", async () => {
    const user = userEvent.setup();
    const created = makeProjectItem({ item_id: "i9", name: "New group" });
    mockUseCreateProjectItem.mockReturnValue(
      makeMutation<ProjectItem, { projectId: string; body: CreateProjectItemInput }>(
        (_variables, options) => options?.onSuccess?.(created),
      ),
    );
    renderWithProviders(<ProjectDetail projectId="p1" />);
    await user.click(screen.getByRole("button", { name: "New item" }));
    await user.type(screen.getByPlaceholderText("e.g. Channel sample group"), "New group");
    await user.click(screen.getByRole("button", { name: "Create item" }));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/projects/p1/items/i9");
    });
  });
});

describe("ProjectItemDetail", () => {
  beforeEach(() => {
    pushMock.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockUseProjectItem.mockReturnValue(
      makeItemQuery(
        makeProjectItem({
          name: "Sample item",
          item_type: "mixed",
          tags: ["yt"],
          sample_ids: ["s1"],
          dataset_ids: ["d1"],
        }),
      ),
    );
    mockUseDeleteProjectItem.mockReturnValue(
      makeMutation<ProjectItemDeleteResult, { projectId: string; itemId: string }>(
        (_variables, options) => options?.onSuccess?.({ item_id: "i1", deleted: true }),
      ),
    );
    mockUseUpdateProjectItem.mockReturnValue(
      makeMutation<
        ProjectItem,
        { projectId: string; itemId: string; patch: UpdateProjectItemInput }
      >(vi.fn()),
    );
    mockUseRemoveSamplesFromItem.mockReturnValue(
      { mutate: vi.fn(), isPending: false } as unknown as ItemMutation,
    );
    mockUseRemoveDatasetsFromItem.mockReturnValue(
      makeMutation<ProjectItem, { projectId: string; itemId: string; datasetIds: string[] }>(
        vi.fn(),
      ),
    );
    mockUseAddSamplesToItem.mockReturnValue(
      makeMutation<ProjectItem, { projectId: string; itemId: string; sampleIds: string[] }>(
        vi.fn(),
      ),
    );
    mockUseAddDatasetsToItem.mockReturnValue(
      makeMutation<ProjectItem, { projectId: string; itemId: string; datasetIds: string[] }>(
        vi.fn(),
      ),
    );
    mockUseSampleList.mockReturnValue(makeInfiniteQuery<Sample>([]));
    mockUseDatasetList.mockReturnValue(makeInfiniteQuery<Dataset>([]));
  });

  it("renders item details, tags and member lists", () => {
    renderWithProviders(<ProjectItemDetail projectId="p1" itemId="i1" />);
    expect(screen.getByText("Sample item")).toBeInTheDocument();
    expect(screen.getByText("mixed")).toBeInTheDocument();
    expect(screen.getByText("yt")).toBeInTheDocument();
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("d1")).toBeInTheDocument();
  });

  it("removes a sample from the item", async () => {
    const user = userEvent.setup();
    const removeSamples = vi.fn();
    mockUseRemoveSamplesFromItem.mockReturnValue(
      { mutate: removeSamples, isPending: false } as unknown as ItemMutation,
    );
    renderWithProviders(<ProjectItemDetail projectId="p1" itemId="i1" />);
    await user.click(screen.getByRole("button", { name: "Remove sample s1" }));
    expect(removeSamples).toHaveBeenCalledWith({
      projectId: "p1",
      itemId: "i1",
      sampleIds: ["s1"],
    });
  });

  it("deletes the item and navigates back to the project", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProjectItemDetail projectId="p1" itemId="i1" />);
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/projects/p1");
    });
  });
});