"use client";

/**
 * Theme-aware color helpers for canvas-based charts (react-force-graph) and
 * DOM swatches. Recharts consumers use the raw CSS `var(...)` strings from
 * `CHART_VARS` directly so SVG presentation attributes resolve at paint time
 * (no hydration mismatch, auto-adapts to the active theme). Canvas contexts
 * cannot resolve `var()` strings, so they call `resolveChartColors()` at
 * accessor-call time (runs client-side only).
 *
 * The `--chart-*` variables are defined in `globals.css` for both themes.
 */

export const CHART_VARS = {
  ink: "var(--foreground)",
  inkMuted: "var(--muted-foreground)",
  accent: "var(--chart-accent)",
  accent2: "var(--chart-accent-2)",
  dim: "var(--chart-dim)",
  faint: "var(--chart-faint)",
  link: "var(--chart-link)",
} as const;

export const CHART_FALLBACKS = {
  ink: "#18181b",
  inkMuted: "#71717a",
  accent: "#2563eb",
  accent2: "#7c3aed",
  dim: "#52525b",
  faint: "#a1a1aa",
  link: "rgba(113, 113, 122, 0.45)",
} as const;

export type ChartColorKey = keyof typeof CHART_VARS;

export function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

export function resolveChartColors(): Record<ChartColorKey, string> {
  return {
    ink: cssVar("--foreground", CHART_FALLBACKS.ink),
    inkMuted: cssVar("--muted-foreground", CHART_FALLBACKS.inkMuted),
    accent: cssVar("--chart-accent", CHART_FALLBACKS.accent),
    accent2: cssVar("--chart-accent-2", CHART_FALLBACKS.accent2),
    dim: cssVar("--chart-dim", CHART_FALLBACKS.dim),
    faint: cssVar("--chart-faint", CHART_FALLBACKS.faint),
    link: cssVar("--chart-link", CHART_FALLBACKS.link),
  };
}
