"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { LogEvent } from "../lib/logSchema";

function lineClass(e: LogEvent): string {
  switch (e.type) {
    case "error":
      return "text-destructive";
    case "stage_start":
      return "text-chart-accent";
    case "stage_done":
      return "text-chart-2";
    case "llm":
      return "text-chart-1";
    case "tool_call":
      return "text-foreground";
    case "retriever":
      return "text-chart-accent-2";
    case "done":
      return "text-muted-foreground";
    default:
      return "text-muted-foreground";
  }
}

function summarize(e: LogEvent): string {
  switch (e.type) {
    case "stage_start":
      return `▶ ${e.stage ?? ""}`;
    case "stage_done":
      return `✔ ${e.stage ?? ""}`;
    case "tool_call":
      return `🔧 ${e.tool ?? ""}${
        e.input ? ": " + String(e.input).slice(0, 90) : ""
      }`;
    case "tool_done":
      return `✔ tool ${e.tool ?? ""}`;
    case "retriever":
      return e.action === "start"
        ? `🔍 ${e.tool ?? "retriever"}: ${e.query ?? ""}`
        : `📚 ${e.tool ?? "retriever"} → ${e.count ?? "?"} docs`;
    case "llm":
      return e.action === "start"
        ? `🧠 ${e.model ?? "llm"}`
        : `🧠 ${e.model ?? "llm"} tokens=${e.tokens?.total ?? 0}`;
    case "error":
      return `✖ ${e.stage ?? ""}: ${e.message ?? ""}`;
    case "done":
      return "— pipeline complete —";
    case "run_start":
      return `▶ run ${e.run_id ?? ""}`;
    default:
      return JSON.stringify(e);
  }
}

export function LogsDrawer({
  open,
  onClose,
  events,
}: {
  open: boolean;
  onClose: () => void;
  events: LogEvent[];
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [events, open]);

  if (!open) return null;

  const visible = events.filter((e) => e.type !== "connected");

  return (
    <div className="flex h-72 flex-col border-t border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-sm font-medium">Backend activity</span>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close logs"
        >
          <X className="size-4" />
        </Button>
      </div>
      <div
        ref={ref}
        className="flex-1 overflow-auto px-4 py-2 font-mono text-xs leading-relaxed"
      >
        {visible.length === 0 ? (
          <div className="text-muted-foreground">
            No activity yet. Run the agent (chat or “Run pipeline”) to watch
            backend steps stream here.
          </div>
        ) : (
          visible.map((e, i) => (
            <div key={i} className={lineClass(e)}>
              {summarize(e)}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
