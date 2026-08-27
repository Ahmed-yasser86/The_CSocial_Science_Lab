"use client";

import { useEffect, useRef } from "react";
import { Activity } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useBudgetEvents,
  useBudgetState,
  formatInterval,
  formatRatePerSecond,
} from "@/services/budget";

const MAX_SAMPLES = 40;
const MAX_EVENT_ROWS = 12;

function formatEventTime(ts: number): string {
  try {
    return new Date(ts * 1000).toLocaleTimeString();
  } catch {
    return String(ts);
  }
}

function Sparkline({
  samples,
  floor,
  ceiling,
}: {
  samples: number[];
  floor: number;
  ceiling: number;
}) {
  if (samples.length < 2) {
    return (
      <div className="h-10 w-full rounded bg-muted/40 text-[10px] text-muted-foreground flex items-center justify-center">
        collecting…
      </div>
    );
  }
  const lo = Math.min(floor, ...samples);
  const hi = Math.max(ceiling, ...samples);
  const span = hi - lo || 1;
  const w = 100;
  const h = 40;
  const step = w / (samples.length - 1);
  const points = samples
    .map((v, i) => {
      // Lower interval (faster) -> higher on the chart.
      const y = h - ((v - lo) / span) * h;
      return `${i * step},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="h-10 w-full"
      data-testid="budget-sparkline"
      aria-hidden
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-xs font-medium tabular-nums" data-testid={`budget-${label.toLowerCase()}`}>
        {value}
      </div>
    </div>
  );
}

export function BudgetDashboard() {
  const stateQuery = useBudgetState();
  const eventsQuery = useBudgetEvents(50);

  const state = stateQuery.data;
  const events = eventsQuery.data?.events ?? [];

  // Sample the effective interval over time so the AIMD trend is visible.
  const samplesRef = useRef<number[]>([]);
  useEffect(() => {
    if (state && typeof state.min_interval === "number") {
      const next = [...samplesRef.current, state.min_interval];
      if (next.length > MAX_SAMPLES) next.shift();
      samplesRef.current = next;
    }
  }, [state?.min_interval, state]);

  return (
    <Card className="p-3 space-y-2" data-testid="budget-dashboard">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-medium">
          <Activity className="size-3.5 text-emerald-500" aria-hidden />
          Live Budget
        </div>
        {stateQuery.isError ? (
          <Badge variant="outline" className="text-[10px]">
            unavailable
          </Badge>
        ) : (
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
            polling
          </span>
        )}
      </div>

      {stateQuery.isError ? (
        <p className="text-[10px] text-muted-foreground">
          Budget telemetry is unavailable from the backend.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-1.5">
            <Stat label="Rate" value={formatRatePerSecond(state?.min_interval ?? 0)} />
            <Stat label="Delay" value={formatInterval(state?.min_interval ?? 0)} />
            <Stat label="Admits" value={String(state?.admits ?? 0)} />
            <Stat label="429s" value={String(state?.rate_limited ?? 0)} />
          </div>

          <div className="rounded-md border bg-muted/20 p-1.5">
            <div className="mb-0.5 flex items-center justify-between text-[9px] text-muted-foreground">
              <span>AIMD interval (per-cost spacing)</span>
              {state?.in_cooldown ? (
                <Badge variant="destructive" className="text-[9px]" data-testid="budget-cooldown">
                  cooldown {formatInterval(state.cooldown_remaining_seconds)}
                </Badge>
              ) : (
                <span className="text-[9px] text-emerald-600">healthy</span>
              )}
            </div>
            <Sparkline
              samples={samplesRef.current}
              floor={state?.aimd_floor ?? 0}
              ceiling={state?.aimd_ceiling ?? 0}
            />
          </div>

          <div className="space-y-1">
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">
              Recent events
            </div>
            <div className="max-h-40 space-y-0.5 overflow-y-auto pr-1">
              {events.length === 0 ? (
                <p className="text-[10px] text-muted-foreground">No events yet.</p>
              ) : (
                [...events]
                  .slice(-MAX_EVENT_ROWS)
                  .reverse()
                  .map((e, i) => (
                    <div
                      key={`${e.ts}-${i}`}
                      className="flex items-center gap-1.5 text-[10px] tabular-nums"
                      data-testid="budget-event"
                    >
                      <span className="text-muted-foreground">
                        {formatEventTime(e.ts)}
                      </span>
                      <Badge
                        variant={
                          e.kind === "rate_limit"
                            ? "destructive"
                            : e.kind === "state_change"
                              ? "secondary"
                              : "outline"
                        }
                        className="px-1 py-0 text-[9px]"
                      >
                        {e.kind}
                      </Badge>
                      <span className="truncate text-muted-foreground">
                        {e.operation ?? "—"}
                        {e.reason ? ` · ${e.reason}` : ""}
                      </span>
                    </div>
                  ))
              )}
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
