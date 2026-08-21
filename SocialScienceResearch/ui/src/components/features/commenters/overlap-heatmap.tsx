"use client";

import { useMemo } from "react";
import { resolveChartColors } from "@/lib/colors";
import type { CommenterProjection } from "@/lib/commenter-overlap-types";

function formatMetric(value: number | null): string {
  if (value === null || value === undefined) return "–";
  return value >= 1 ? String(Math.round(value)) : value.toFixed(3);
}

export function OverlapHeatmap({
  projection,
  selectedPair,
  onSelectPair,
}: {
  projection: CommenterProjection;
  selectedPair?: { a: string; b: string } | null;
  onSelectPair?: (a: string, b: string) => void;
}) {
  const entities = projection.entities;

  const { maxValue, accent } = useMemo(() => {
    let max = 0;
    for (const a of entities) {
      for (const b of entities) {
        const v = projection.heatmap[a.entity_id]?.[b.entity_id];
        if (v !== null && v !== undefined && v > max) max = v;
      }
    }
    return { maxValue: max || 1, accent: resolveChartColors().accent };
  }, [entities, projection.heatmap]);

  function alphaFor(value: number | null): number {
    if (value === null || value === undefined) return 0;
    return 0.08 + 0.72 * Math.min(1, value / maxValue);
  }

  return (
    <div
      data-testid="overlap-heatmap"
      className="inline-block rounded-lg border border-border p-2"
    >
      <div
        role="grid"
        aria-label="Overlap heatmap"
        className="grid gap-1"
        style={{
          gridTemplateColumns: `minmax(0, 11rem) repeat(${entities.length}, minmax(2rem, 1fr))`,
        }}
      >
        <div />
        {entities.map((entity) => (
          <div
            key={entity.entity_id}
            className="truncate px-1 text-center text-[10px] uppercase tracking-wide text-muted-foreground"
            title={entity.title ?? entity.entity_id}
          >
            {entity.title?.slice(0, 10) ?? entity.entity_id.slice(0, 8)}
          </div>
        ))}

        {entities.map((a) => (
          <Row
            key={a.entity_id}
            label={a.title ?? a.entity_id}
            a={a.entity_id}
            entityIds={entities.map((e) => e.entity_id)}
            heatmap={projection.heatmap}
            accent={accent}
            alphaFor={alphaFor}
            selectedPair={selectedPair}
            onSelectPair={onSelectPair}
          />
        ))}
      </div>
      <div className="mt-2 flex items-center gap-2 px-1 text-[10px] text-muted-foreground">
        <span>lower</span>
        <span
          className="h-2 w-24 rounded"
          style={{
            background: `linear-gradient(to right, ${accent}1A, ${accent}66, ${accent}E6)`,
          }}
          aria-hidden
        />
        <span>higher</span>
      </div>
    </div>
  );
}

function Row({
  label,
  a,
  entityIds,
  heatmap,
  accent,
  alphaFor,
  selectedPair,
  onSelectPair,
}: {
  label: string;
  a: string;
  entityIds: string[];
  heatmap: CommenterProjection["heatmap"];
  accent: string;
  alphaFor: (value: number | null) => number;
  selectedPair?: { a: string; b: string } | null;
  onSelectPair?: (a: string, b: string) => void;
}) {
  return (
    <>
      <div className="flex items-center truncate pr-2 text-xs" title={label}>
        {label.slice(0, 18)}
      </div>
      {entityIds.map((b) => {
        if (a === b) {
          return (
            <div
              key={`${a}:${b}`}
              className="flex aspect-square items-center justify-center text-muted-foreground/40"
              aria-hidden
            >
              ·
            </div>
          );
        }
        const value = heatmap[a]?.[b] ?? null;
        const isSelected =
          selectedPair !== null &&
          selectedPair !== undefined &&
          ((selectedPair.a === a && selectedPair.b === b) ||
            (selectedPair.a === b && selectedPair.b === a));
        return (
          <button
            key={`${a}:${b}`}
            type="button"
            aria-label={`overlap ${formatMetric(value)} between ${a} and ${b}`}
            title={`${a} ↔ ${b}: ${formatMetric(value)}`}
            aria-pressed={isSelected}
            onClick={() => onSelectPair?.(a, b)}
            className={`flex aspect-square min-w-8 items-center justify-center rounded text-[10px] outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:ring-2 aria-pressed:ring-foreground ${
              value === null || value === undefined ? "bg-muted/30" : "text-foreground"
            }`}
            style={
              value === null || value === undefined
                ? undefined
                : { backgroundColor: `${accent}${Math.round(alphaFor(value) * 255).toString(16).padStart(2, "0")}` }
            }
          >
            {value === null || value === undefined ? "" : formatMetric(value)}
          </button>
        );
      })}
    </>
  );
}
