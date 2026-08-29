"use client";

import { Activity, AlertTriangle, Loader2 } from "lucide-react";
import type { LogCounts } from "../lib/logSchema";

export function ActivityPill({
  counts,
  onClick,
}: {
  counts: LogCounts;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      aria-label="Toggle backend activity log"
    >
      {counts.running ? (
        <Loader2 className="size-3.5 animate-spin text-chart-accent" />
      ) : (
        <Activity className="size-3.5" />
      )}
      <span>{counts.running ? "Running" : "Idle"}</span>
      <span className="text-muted-foreground/70">·</span>
      <span>{counts.stageStart} steps</span>
      {counts.tokens > 0 && (
        <>
          <span className="text-muted-foreground/70">·</span>
          <span>{counts.tokens.toLocaleString()} tok</span>
        </>
      )}
      {counts.error > 0 && (
        <>
          <span className="text-muted-foreground/70">·</span>
          <span className="inline-flex items-center gap-1 text-destructive">
            <AlertTriangle className="size-3.5" />
            {counts.error}
          </span>
        </>
      )}
    </button>
  );
}
