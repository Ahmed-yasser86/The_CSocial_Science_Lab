import { describe, it, expect, beforeEach } from "vitest";
import {
  loadLabSession,
  saveLabSession,
  clearLabSession,
  defaultLabSession,
  LAB_PRESETS,
  presetById,
} from "@/lib/lab-session";

describe("lab-session", () => {
  beforeEach(() => {
    clearLabSession();
  });

  it("returns an empty partial when nothing is stored", () => {
    expect(loadLabSession()).toEqual({});
  });

  it("merges patches over the previous session", () => {
    saveLabSession({ tab: "graph", identity: "Researcher A" });
    const next = saveLabSession({ runId: "run_1" });
    expect(next.tab).toBe("graph");
    expect(next.identity).toBe("Researcher A");
    expect(next.runId).toBe("run_1");
  });

  it("falls back to defaults for missing keys", () => {
    const session = saveLabSession({ tab: "commenters" });
    expect(session.graphProjection).toBe(defaultLabSession().graphProjection);
    expect(session.annotation).toBe("");
  });

  it("exposes layout presets that cover the main analyses", () => {
    const ids = LAB_PRESETS.map((p) => p.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        "explore",
        "echo",
        "channels",
        "insights",
        "matrices",
        "layers",
      ]),
    );
    expect(presetById("echo")?.patch.tab).toBe("commenters");
  });

  it("clears the persisted session", () => {
    saveLabSession({ identity: "x" });
    clearLabSession();
    expect(loadLabSession()).toEqual({});
  });
});
