"use client";

import { useEffect, useMemo, useState } from "react";
import type { LogEvent, LogCounts } from "../lib/logSchema";

// Full pipeline order as emitted by the backend (Graph/intelligence_graph.py).
export const STAGE_KEYS = [
  "identity_research",
  "profile_summarization",
  "subject_intelligence",
  "audience_intelligence",
  "ecosystem_intelligence",
] as const;

export const STAGE_LABELS: Record<string, string> = {
  identity_research: "Identity Research",
  profile_summarization: "Profile Summarization",
  subject_intelligence: "Subject Intelligence",
  audience_intelligence: "Audience Intelligence",
  ecosystem_intelligence: "Ecosystem Intelligence",
};

export type StageStatus = "pending" | "active" | "done" | "error";

export function useAgentLogs() {
  const [events, setEvents] = useState<LogEvent[]>([]);

  useEffect(() => {
    // Talk to the backend DIRECTLY (not through the Next.js proxy). Next.js
    // rewrites buffer Server-Sent Events and POST bodies, which made the live
    // log stream and /api/agent/run appear to hang/500. The backend enables
    // CORS for the dev origins, so a direct EventSource works.
    const base = process.env.NEXT_PUBLIC_AGENT_BACKEND_URL ?? "";
    const es = new EventSource(`${base}/api/agent/logs`);
    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as LogEvent;
        if (parsed.type === "connected") return;
        setEvents((prev) => {
          const next = [...prev, parsed];
          return next.length > 600 ? next.slice(next.length - 600) : next;
        });
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => es.close();
  }, []);

  return useMemo(() => {
    let stageStart = 0;
    let done = 0;
    let error = 0;
    let tokens = 0;
    const stageStatus: Record<string, StageStatus> = {};
    let running = false;
    let lastError: string | undefined;
    let cancelled = false;
    let plan: string[] | undefined;
    let currentStage: string | undefined;

    for (const e of events) {
      if (e.type === "run_start") {
        running = true;
        cancelled = false;
        const p = (e as { plan?: string[] }).plan;
        if (Array.isArray(p)) plan = p;
      } else if (e.type === "stage_start") {
        if (e.stage) {
          stageStatus[e.stage] = "active";
          currentStage = e.stage;
        }
      } else if (e.type === "stage_done") {
        if (e.stage) stageStatus[e.stage] = "done";
      } else if (e.type === "error") {
        lastError = e.message;
        if (e.stage && stageStatus[e.stage]) stageStatus[e.stage] = "error";
      } else if (e.type === "cancelled") {
        running = false;
        cancelled = true;
        lastError = e.message ?? "Run cancelled";
      } else if (e.type === "done") {
        running = false;
      } else if (e.type === "llm" && e.action === "end" && e.tokens) {
        tokens += e.tokens.total;
      }
    }

    // Counts for the compact header summary.
    for (const e of events) {
      if (e.type === "stage_start") stageStart++;
      else if (e.type === "done") done++;
      else if (e.type === "error") error++;
    }

    const stages = STAGE_KEYS.map((k) => ({
      key: k,
      label: STAGE_LABELS[k],
      status: stageStatus[k] ?? "pending",
    }));

    const counts: LogCounts = { stageStart, done, error, tokens, running };
    return { events, counts, currentStage, stages, plan, running, lastError, cancelled };
  }, [events]);
}
