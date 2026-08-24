import { describe, expect, it } from "vitest";
import {
  parseStoredSession,
  reconcileSessions,
  serializeStoredSession,
  type StoredActiveSession,
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
