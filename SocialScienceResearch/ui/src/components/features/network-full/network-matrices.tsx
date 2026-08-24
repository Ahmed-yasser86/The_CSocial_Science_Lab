"use client";

import { useState } from "react";
import { Maximize2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/features/state";
import { useNetworkMatrices } from "@/services/networkFull";

interface NetworkMatricesProps {
  channelIds?: string[];
  runIds?: string[];
}

function heatColor(value: number, max: number): string {
  if (max <= 0 || value <= 0) return "transparent";
  const intensity = Math.min(1, value / max);
  const green = Math.round(220 - intensity * 150);
  return `rgb(${Math.round(200 + intensity * 40)}, ${green}, ${Math.round(180 - intensity * 80)})`;
}

function CommunityMatrixTable({
  community_matrix,
}: {
  community_matrix: NonNullable<
    ReturnType<typeof useNetworkMatrices>["data"]
  >["community_matrix"];
}) {
  const labels = community_matrix.labels;
  const label_meta = community_matrix.label_meta ?? {};
  const labelName = (id: string) => label_meta[id] || id;
  const allValues = labels.flatMap((a) =>
    labels.map((b) => community_matrix.matrix[a]?.[b] ?? 0),
  );
  const maxVal = allValues.length ? Math.max(...allValues) : 0;

  if (labels.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No channel data for this scope.</p>
    );
  }

  return (
    <table className="border-collapse text-xs">
      <thead>
        <tr>
          <th className="p-1 text-left" />
          {labels.map((b) => (
            <th key={b} className="p-1 text-right font-medium" title={b}>
              {labelName(b)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {labels.map((a) => (
          <tr key={a}>
            <th className="p-1 text-right font-medium" title={a}>
              {labelName(a)}
            </th>
            {labels.map((b) => {
              const v = community_matrix.matrix[a]?.[b] ?? 0;
              return (
                <td
                  key={b}
                  className="h-8 w-10 border border-border p-1 text-right"
                  style={{ backgroundColor: heatColor(v, maxVal) }}
                >
                  {v}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LayerMatrixTable({
  layer_matrix,
}: {
  layer_matrix: NonNullable<
    ReturnType<typeof useNetworkMatrices>["data"]
  >["layer_matrix"];
}) {
  if (layer_matrix.rows.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No recommendation layers for this scope.
      </p>
    );
  }
  return (
    <table className="border-collapse text-xs">
      <thead>
        <tr>
          <th className="p-1 text-right font-medium">Layer</th>
          <th className="p-1 text-right font-medium">Edges</th>
          <th className="p-1 text-right font-medium">Sources</th>
          <th className="p-1 text-right font-medium">Targets</th>
          <th className="p-1 text-right font-medium">Target channels</th>
        </tr>
      </thead>
      <tbody>
        {layer_matrix.rows.map((row) => (
          <tr key={row.layer_index}>
            <td className="border border-border p-1 text-right">{row.layer_index}</td>
            <td className="border border-border p-1 text-right">{row.edge_count}</td>
            <td className="border border-border p-1 text-right">{row.unique_sources}</td>
            <td className="border border-border p-1 text-right">{row.unique_targets}</td>
            <td className="border border-border p-1 text-right">
              {row.unique_target_channels}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function NetworkMatrices({ channelIds, runIds }: NetworkMatricesProps) {
  const { data, isLoading, isError, error, refetch } = useNetworkMatrices(
    channelIds,
    runIds,
  );
  const [expanded, setExpanded] = useState<null | "community" | "layer">(null);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError)
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load matrices"}
        retry={() => refetch()}
      />
    );
  if (!data) return null;

  const { community_matrix, layer_matrix } = data;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">Community matrix (shared commenters)</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Expand community matrix"
            onClick={() => setExpanded("community")}
          >
            <Maximize2 className="size-4" aria-hidden />
          </Button>
        </CardHeader>
        <CardContent className="overflow-auto">
          <CommunityMatrixTable community_matrix={community_matrix} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">Layer structure matrix</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Expand layer structure matrix"
            onClick={() => setExpanded("layer")}
          >
            <Maximize2 className="size-4" aria-hidden />
          </Button>
        </CardHeader>
        <CardContent className="overflow-auto">
          <LayerMatrixTable layer_matrix={layer_matrix} />
        </CardContent>
      </Card>

      <Dialog
        open={expanded !== null}
        onOpenChange={(open) => {
          if (!open) setExpanded(null);
        }}
      >
        <DialogContent className="fixed inset-0 top-0 left-0 z-50 flex h-screen w-screen max-h-none max-w-none translate-x-0 translate-y-0 flex-col overflow-hidden rounded-none p-0 sm:max-w-none">
          <DialogHeader className="border-b px-4 py-3">
            <DialogTitle>
              {expanded === "community"
                ? "Community matrix (shared commenters)"
                : "Layer structure matrix"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4">
            {expanded === "community" ? (
              <CommunityMatrixTable community_matrix={community_matrix} />
            ) : (
              <LayerMatrixTable layer_matrix={layer_matrix} />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
