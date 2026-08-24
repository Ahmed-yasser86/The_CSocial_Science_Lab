import { describe, expect, it } from "vitest";
import {
  parseStoredSession,
  parseStoredWorkspace,
  reconcileSessions,
  reconcileWorkspaces,
  serializeStoredSession,
  serializeStoredWorkspace,
  type StoredActiveSession,
  type StoredActiveWorkspace,
} from "@/lib/session";

const local: StoredActiveSession = {
  activeProjectId: "p-local",
  activeDatasetId: null,
  updatedAt: "2026-01-02T00:00:00Z",
};

function serverSession(
  projectId: string | null,
  updatedAt: string,
  datasetId: string | null = null,
) {
  return {
    active_workspace_id: null,
    active_project_id: projectId,
    active_dataset_id: datasetId,
    updated_at: updatedAt,
  };
}

describe("reconcileSessions", () => {
  it("returns no session when both sides are empty", () => {
    expect(reconcileSessions(null, serverSession(null, "2026-01-01T00:00:00Z"))).toEqual({
      session: null,
      pushLocal: false,
    });
    expect(reconcileSessions(null, null)).toEqual({ session: null, pushLocal: false });
  });

  it("adopts the local session and pushes it when the server is empty", () => {
    expect(reconcileSessions(local, serverSession(null, "2026-01-03T00:00:00Z"))).toEqual({
      session: {
        activeProjectId: "p-local",
        activeDatasetId: null,
      },
      pushLocal: true,
    });
    expect(reconcileSessions(local, null)).toEqual({
      session: { activeProjectId: "p-local", activeDatasetId: null },
      pushLocal: true,
    });
  });

  it("adopts the server session without pushing when local is empty", () => {
    const result = reconcileSessions(
      null,
      serverSession("p-server", "2026-01-01T00:00:00Z", "d1"),
    );
    expect(result).toEqual({
      session: { activeProjectId: "p-server", activeDatasetId: "d1" },
      pushLocal: false,
    });
  });

  it("lets the server win when its timestamp is newer", () => {
    const result = reconcileSessions(
      local,
      serverSession("p-server", "2026-01-05T00:00:00Z"),
    );
    expect(result).toEqual({
      session: { activeProjectId: "p-server", activeDatasetId: null },
      pushLocal: false,
    });
  });

  it("keeps the local session (and pushes it) when it is newer", () => {
    const result = reconcileSessions(
      local,
      serverSession("p-server", "2026-01-01T00:00:00Z"),
    );
    expect(result).toEqual({
      session: { activeProjectId: "p-local", activeDatasetId: null },
      pushLocal: true,
    });
  });

  it("prefers local on equal timestamps", () => {
    const result = reconcileSessions(
      local,
      serverSession("p-server", "2026-01-02T00:00:00Z"),
    );
    expect(result.pushLocal).toBe(true);
    expect(result.session?.activeProjectId).toBe("p-local");
  });

  it("treats an unparseable local timestamp as older than the server", () => {
    const stale: StoredActiveSession = { ...local, updatedAt: "not-a-date" };
    const result = reconcileSessions(
      stale,
      serverSession("p-server", "2026-01-01T00:00:00Z"),
    );
    expect(result).toEqual({
      session: { activeProjectId: "p-server", activeDatasetId: null },
      pushLocal: false,
    });
  });
});

describe("parseStoredSession / serializeStoredSession", () => {
  it("round-trips a stored session", () => {
    const raw = serializeStoredSession(
      { activeProjectId: "p1", activeDatasetId: "d1" },
      "2026-01-01T12:00:00Z",
    );
    expect(parseStoredSession(raw)).toEqual({
      activeProjectId: "p1",
      activeDatasetId: "d1",
      updatedAt: "2026-01-01T12:00:00Z",
    });
  });

  it("rejects malformed or incomplete payloads", () => {
    expect(parseStoredSession(null)).toBeNull();
    expect(parseStoredSession("")).toBeNull();
    expect(parseStoredSession("{broken")).toBeNull();
    expect(parseStoredSession(JSON.stringify({ updatedAt: "x" }))).toBeNull();
    expect(
      parseStoredSession(JSON.stringify({ activeProjectId: "", updatedAt: "x" })),
    ).toBeNull();
  });

  it("coerces a missing dataset id to null", () => {
    expect(
      parseStoredSession(
        JSON.stringify({ activeProjectId: "p1", activeDatasetId: 42 }),
      ),
    ).toMatchObject({ activeProjectId: "p1", activeDatasetId: null });
  });
});

describe("workspace pointer persistence", () => {
  const localWorkspace: StoredActiveWorkspace = {
    workspaceId: "ws_local",
    updatedAt: "2026-01-02T00:00:00Z",
  };

  function serverContext(workspaceId: string | null, updatedAt: string) {
    return { active_workspace_id: workspaceId, updated_at: updatedAt };
  }

  it("round-trips a stored workspace pointer", () => {
    const raw = serializeStoredWorkspace("ws_1", "2026-01-01T12:00:00Z");
    expect(parseStoredWorkspace(raw)).toEqual({
      workspaceId: "ws_1",
      updatedAt: "2026-01-01T12:00:00Z",
    });
  });

  it("rejects malformed or empty pointers", () => {
    expect(parseStoredWorkspace(null)).toBeNull();
    expect(parseStoredWorkspace("{broken")).toBeNull();
    expect(parseStoredWorkspace(JSON.stringify({ workspaceId: "" }))).toBeNull();
  });

  it("reconciles like sessions: newer timestamp wins", () => {
    // Server wins when newer.
    expect(
      reconcileWorkspaces(localWorkspace, serverContext("ws_server", "2026-01-05T00:00:00Z")),
    ).toEqual({ workspaceId: "ws_server", pushLocal: false });
    // Local wins (and pushes) when newer.
    expect(
      reconcileWorkspaces(localWorkspace, serverContext("ws_server", "2026-01-01T00:00:00Z")),
    ).toEqual({ workspaceId: "ws_local", pushLocal: true });
  });

  it("adopts whichever side exists when the other is empty", () => {
    expect(reconcileWorkspaces(null, null)).toEqual({
      workspaceId: null,
      pushLocal: false,
    });
    expect(
      reconcileWorkspaces(null, serverContext("ws_remote", "2026-01-01T00:00:00Z")),
    ).toEqual({ workspaceId: "ws_remote", pushLocal: false });
    expect(reconcileWorkspaces(localWorkspace, undefined)).toEqual({
      workspaceId: "ws_local",
      pushLocal: true,
    });
    expect(reconcileWorkspaces(localWorkspace, serverContext(null, "x"))).toEqual({
      workspaceId: "ws_local",
      pushLocal: true,
    });
  });
});
