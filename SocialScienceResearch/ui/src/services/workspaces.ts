import { request } from "@/services/api";

export interface WorkspaceStats {
  runs: number;
  videos: number;
  channels: number;
  comments: number;
  datasets: number;
  samples: number;
  projects: number;
}

export interface Workspace {
  workspace_id: string;
  name: string;
  research_topic: string | null;
  is_legacy: boolean;
  active: boolean;
  created_at: string;
  last_opened_at: string;
  stats: WorkspaceStats;
}

export interface CreateWorkspaceBody {
  name: string;
  research_topic?: string | null;
}

export function listWorkspaces(): Promise<Workspace[]> {
  return request("/workspaces");
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}`);
}

export function createWorkspace(body: CreateWorkspaceBody): Promise<Workspace> {
  return request("/workspaces", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateWorkspace(
  workspaceId: string,
  patch: { name?: string; research_topic?: string | null },
): Promise<Workspace> {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
