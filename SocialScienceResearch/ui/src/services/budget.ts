"use client";

import { useQuery } from "@tanstack/react-query";
import { request } from "@/services/api";

/** Live counters + AIMD bounds from ``GET /budget/state``. */
export interface BudgetState {
  min_interval: number;
  max_ytdl_contexts: number;
  admits: number;
  rate_limited: number;
  total_waited_seconds: number;
  aimd_floor: number;
  aimd_ceiling: number;
  in_cooldown: boolean;
  cooldown_remaining_seconds: number;
}

/** A single admission / rate-limit record from ``GET /budget/events``. */
export interface BudgetEvent {
  ts: number;
  kind: string;
  operation?: string | null;
  run_id?: string | null;
  cost?: number;
  waited_seconds?: number;
  budget_after?: number;
  reason?: string | null;
  detail?: Record<string, unknown> | null;
}

export interface BudgetEventsResponse {
  events: BudgetEvent[];
  min_interval: number;
  max_ytdl_contexts: number;
}

const DEFAULT_REFRESH_MS = 2000;

export function useBudgetState(refreshMs: number = DEFAULT_REFRESH_MS) {
  return useQuery({
    queryKey: ["budget", "state"],
    queryFn: () => request<BudgetState>("/budget/state"),
    refetchInterval: refreshMs,
  });
}

export function useBudgetEvents(
  limit: number = 50,
  refreshMs: number = DEFAULT_REFRESH_MS,
) {
  return useQuery({
    queryKey: ["budget", "events", limit],
    queryFn: () =>
      request<BudgetEventsResponse>(`/budget/events?limit=${limit}`),
    refetchInterval: refreshMs,
  });
}

/** Effective request rate implied by the current spacing (req/s), or "—" if 0. */
export function formatRatePerSecond(minInterval: number): string {
  if (!minInterval || minInterval <= 0) return "—";
  return `${(1 / minInterval).toFixed(2)} req/s`;
}

/** Human spacing label, e.g. "0.50s" or "—" for an unbounded (0) interval. */
export function formatInterval(seconds: number): string {
  if (!seconds || seconds <= 0) return "—";
  return `${seconds.toFixed(seconds < 1 ? 2 : 1)}s`;
}
