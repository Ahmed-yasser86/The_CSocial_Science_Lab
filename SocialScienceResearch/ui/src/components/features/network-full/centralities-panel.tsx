"use client";

import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNumber } from "@/lib/format";
import type { NetworkCentralities } from "@/lib/network-full-types";
import { useNetworkCentralities } from "@/services/networkFull";

export function CentralitiesPanel({
  runId,
  topN = 25,
}: {
  runId?: string | null;
  topN?: number;
}) {
  const { data, isLoading, isError, error, refetch } = useNetworkCentralities({
    run_id: runId ?? undefined,
    projection: "video",
  });

  if (isLoading) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-muted-foreground">Loading centralities…</p>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load centralities"}
        </p>
      </Card>
    );
  }

  if (!data || Object.keys(data.nodes).length === 0) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-muted-foreground">
          No nodes available for centrality analysis.
        </p>
      </Card>
    );
  }

  return <CentralitiesTable data={data} topN={topN} />;
}

function CentralitiesTable({
  data,
  topN,
}: {
  data: NetworkCentralities;
  topN: number;
}) {
  const rows = useMemo(() => {
    const entries = Object.entries(data.nodes).map(([node, c]) => ({
      node,
      ...c,
    }));
    return entries
      .sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0))
      .slice(0, topN);
  }, [data, topN]);

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Node centralities</h3>
        <Badge variant="outline" className="tabular-nums">
          {Object.keys(data.nodes).length} nodes · {data.algorithm}
        </Badge>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table aria-label="Node centralities">
          <TableHeader>
            <TableRow>
              <TableHead>Node</TableHead>
              <TableHead className="text-right">Degree</TableHead>
              <TableHead className="text-right">Closeness</TableHead>
              <TableHead className="text-right">Eigenvector</TableHead>
              <TableHead className="text-right">Betweenness</TableHead>
              <TableHead className="text-right">Community</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.node}>
                <TableCell className="font-mono text-xs">{row.node}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.degree)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.closeness)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.eigenvector)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.betweenness)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.community_id === null || row.community_id === undefined
                    ? "—"
                    : formatNumber(row.community_id)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}
