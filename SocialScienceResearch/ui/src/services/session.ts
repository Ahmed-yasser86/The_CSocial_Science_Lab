import { request } from "@/services/api";

export interface SessionContext {
  active_project_id: string | null;
  active_dataset_id: string | null;
  updated_at: string;
}

export interface SessionContextPatch {
  active_project_id?: string | null;
  active_dataset_id?: string | null;
}

export function getSessionContext(): Promise<SessionContext> {
  return request("/session/context");
}

/** Absent patch fields are left unchanged on the server; `null` clears. */
export function putSessionContext(
  patch: SessionContextPatch,
): Promise<SessionContext> {
  return request("/session/context", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}
