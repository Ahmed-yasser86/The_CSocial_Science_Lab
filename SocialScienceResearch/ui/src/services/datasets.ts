import { request, toQuery } from "@/services/api";
import { getRuns } from "@/services/api";
import type {
  Channel,
  CombineDatasetsInput,
  CreateDatasetInput,
  CreateProjectInput,
  Dataset,
  DatasetDeleteResult,
  DatasetEntityType,
  DatasetExportFormat,
  DatasetQuality,
  Paginated,
  Project,
  ProjectDeleteResult,
  ProjectItem,
  ProjectItemDeleteResult,
  CreateProjectItemInput,
  UpdateProjectItemInput,
  UpdateProjectInput,
} from "@/lib/dataset-types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "/api/v1/social-science";

export function listProjects(
  cursor?: string,
): Promise<Paginated<Project>> {
  return request(`/projects${toQuery({ cursor })}`);
}

export function getProject(projectId: string): Promise<Project> {
  return request(`/projects/${projectId}`);
}

export function createProject(
  body: CreateProjectInput,
): Promise<Project> {
  return request("/projects", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProject(
  projectId: string,
  patch: UpdateProjectInput,
): Promise<Project> {
  return request(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteProject(
  projectId: string,
): Promise<ProjectDeleteResult> {
  return request(`/projects/${projectId}`, { method: "DELETE" });
}

export function addDatasetToProject(
  projectId: string,
  datasetId: string,
): Promise<Project> {
  return request(`/projects/${projectId}/datasets/${datasetId}`, {
    method: "POST",
  });
}

export function removeDatasetFromProject(
  projectId: string,
  datasetId: string,
): Promise<Project> {
  return request(`/projects/${projectId}/datasets/${datasetId}`, {
    method: "DELETE",
  });
}

export function listProjectItems(
  projectId: string,
): Promise<Paginated<ProjectItem>> {
  return request(`/projects/${projectId}/items`);
}

export function getProjectItem(
  projectId: string,
  itemId: string,
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}`);
}

export function createProjectItem(
  projectId: string,
  body: CreateProjectItemInput,
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProjectItem(
  projectId: string,
  itemId: string,
  patch: UpdateProjectItemInput,
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteProjectItem(
  projectId: string,
  itemId: string,
): Promise<ProjectItemDeleteResult> {
  return request(`/projects/${projectId}/items/${itemId}`, {
    method: "DELETE",
  });
}

export function addSamplesToItem(
  projectId: string,
  itemId: string,
  sampleIds: string[],
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}/samples`, {
    method: "POST",
    body: JSON.stringify({ sample_ids: sampleIds }),
  });
}

export function removeSamplesFromItem(
  projectId: string,
  itemId: string,
  sampleIds: string[],
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}/samples`, {
    method: "DELETE",
    body: JSON.stringify({ sample_ids: sampleIds }),
  });
}

export function addDatasetsToItem(
  projectId: string,
  itemId: string,
  datasetIds: string[],
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}/datasets`, {
    method: "POST",
    body: JSON.stringify({ dataset_ids: datasetIds }),
  });
}

export function removeDatasetsFromItem(
  projectId: string,
  itemId: string,
  datasetIds: string[],
): Promise<ProjectItem> {
  return request(`/projects/${projectId}/items/${itemId}/datasets`, {
    method: "DELETE",
    body: JSON.stringify({ dataset_ids: datasetIds }),
  });
}

export function listDatasets(
  cursor?: string,
): Promise<Paginated<Dataset>> {
  return request(`/datasets${toQuery({ cursor })}`);
}

export function getDataset(datasetId: string): Promise<Dataset> {
  return request(`/datasets/${datasetId}`);
}

export function createDataset(body: CreateDatasetInput): Promise<Dataset> {
  return request("/datasets", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateDataset(
  datasetId: string,
  patch: Partial<CreateDatasetInput>,
): Promise<Dataset> {
  return request(`/datasets/${datasetId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteDataset(
  datasetId: string,
): Promise<DatasetDeleteResult> {
  return request(`/datasets/${datasetId}`, { method: "DELETE" });
}

export function combineDatasets(
  body: CombineDatasetsInput,
): Promise<Dataset> {
  return request("/datasets/combine", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getDatasetMembers(
  datasetId: string,
  cursor?: string,
): Promise<Paginated<Record<string, unknown>>> {
  return request(`/datasets/${datasetId}/members${toQuery({ cursor })}`);
}

export function getDatasetQuality(
  datasetId: string,
): Promise<DatasetQuality> {
  return request(`/datasets/${datasetId}/quality`);
}

export function getDatasetExportUrl(
  datasetId: string,
  format: DatasetExportFormat,
): string {
  return `${API_BASE}/datasets/${datasetId}/export${toQuery({ format: String(format) })}`;
}

export function getChannels(cursor?: string): Promise<Paginated<Channel>> {
  return request(`/channels${toQuery({ cursor })}`);
}

export { getRuns };

export type { DatasetEntityType };