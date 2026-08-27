"use client";

import { Badge } from "@/components/ui/badge";

interface ReproducibilityFooterProps {
  algorithm?: string | null;
  seed?: number | null;
  weightSpec?: Record<string, unknown> | null;
  runIds?: string[];
  computedAt?: string | null;
  /** Extra free-form tokens (e.g. "approximation=k" for large graphs). */
  notes?: string[];
}

function weightToken(spec: Record<string, unknown> | null | undefined): string | null {
  if (!spec) return null;
  const edgeType = spec["edge_type"] ?? spec["edgeType"];
  const weightMode = spec["weight_mode"] ?? spec["weightMode"];
  if (edgeType && weightMode) {
    const params = spec["params"];
    let suffix = "";
    if (params && typeof params === "object") {
      const parts = Object.entries(params as Record<string, unknown>)
        .filter(([, v]) => v != null)
        .map(([k, v]) => `${k}=${v}`);
      if (parts.length) suffix = `:${parts.join(",")}`;
    }
    return `${edgeType}:${weightMode}${suffix}`;
  }
  return JSON.stringify(spec);
}

/** N5 — reproducibility footer shown on every analysis surface so a researcher
 * (and a reviewer) can reconstruct exactly how a figure was computed. */
export function ReproducibilityFooter({
  algorithm,
  seed,
  weightSpec,
  runIds,
  computedAt,
  notes,
}: ReproducibilityFooterProps) {
  const token = weightToken(weightSpec);
  const items: string[] = [];
  if (algorithm) items.push(`algorithm=${algorithm}`);
  if (seed != null) items.push(`seed=${seed}`);
  if (token) items.push(`weight=${token}`);
  if (runIds && runIds.length) items.push(`runs=${runIds.length}`);
  if (notes) items.push(...notes);
  if (computedAt) items.push(`computed=${computedAt}`);
  if (items.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3 text-xs text-muted-foreground">
      <span className="font-medium uppercase tracking-wide">Reproducibility</span>
      {items.map((it, i) => (
        <Badge key={i} variant="outline" className="font-mono">
          {it}
        </Badge>
      ))}
    </div>
  );
}
