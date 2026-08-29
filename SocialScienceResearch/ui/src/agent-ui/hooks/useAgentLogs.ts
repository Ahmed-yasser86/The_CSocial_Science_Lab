"use client";

import { useEffect, useMemo, useState } from "react";
import type { LogEvent, LogCounts } from "../lib/logSchema";

export function useAgentLogs() {
  const [events, setEvents] = useState<LogEvent[]>([]);

  useEffect(() => {
    const es = new EventSource("/api/agent/logs");
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
    const started = new Set<string>();
    let currentStage: string | undefined;

    for (const e of events) {
      if (e.type === "stage_start") {
        stageStart++;
        if (e.stage) {
          started.add(e.stage);
          currentStage = e.stage;
        }
      } else if (e.type === "stage_done") {
        if (e.stage) started.delete(e.stage);
      } else if (e.type === "done") {
        done++;
      } else if (e.type === "error") {
        error++;
      } else if (e.type === "llm" && e.action === "end" && e.tokens) {
        tokens += e.tokens.total;
      }
    }

    const lastMeaningful = [...events].reverse().find((e) => e.type !== "connected");
    const running =
      !!lastMeaningful &&
      lastMeaningful.type !== "done" &&
      events.some((e) => e.type === "run_start");

    const counts: LogCounts = { stageStart, done, error, tokens, running };
    return { events, counts, currentStage: started.size ? currentStage : undefined };
  }, [events]);
}
