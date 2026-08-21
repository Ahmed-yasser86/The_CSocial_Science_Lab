"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
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
import { ChartCard } from "@/components/features/charts";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { useNetworkTemporal } from "@/services/networkFull";
import { useRuns } from "@/services/queries";
import { formatNumber } from "@/lib/format";
import { CHART_VARS } from "@/lib/colors";
import type { TemporalResult } from "@/lib/network-full-types";

const INK = CHART_VARS.ink;
const INK_MUTED = CHART_VARS.inkMuted;

export function TemporalOverlay({
  runIds,
}: {
  runIds: string[];
}) {
  const query = useNetworkTemporal(runIds);
  const runsQuery = useRuns();
  const runNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const run of runsQuery.data ?? []) {
      if (run.name && !names.has(run.run_id)) names.set(run.run_id, run.name);
    }
    return names;
  }, [runsQuery.data]);

  if (query.isLoading) return <LoadingState label="Loading temporal slices…" />;
  if (query.isError)
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : "Failed to load temporal network slices"
        }
        retry={() => query.refetch()}
      />
    );

  const result = query.data as TemporalResult | undefined;
  if (!result) return <LoadingState label="Loading temporal slices…" />;
  if (result.slices.length === 0) {
    return (
      <EmptyState
        title="No temporal slices"
        description="Pick one or more runs to compare network slices over time."
      />
    );
  }

  return (
    <div className="space-y-4">
      <ChartCard
        title="Network size over runs"
        description="Nodes and edges per collection run slice."
      >
        <div className="h-64 w-full" role="img" aria-label="Network size over runs">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={result.slices.map((slice) => ({
                label: runNames.get(slice.run_id) ?? slice.run_id,
                nodes: slice.node_count,
                edges: slice.edge_count,
              }))}
              margin={{ top: 16, right: 16, bottom: 8, left: 8 }}
            >
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 9, fill: INK_MUTED }} />
              <YAxis tick={{ fontSize: 10, fill: INK_MUTED }} allowDecimals={false} width={44} />
              <Tooltip
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "12px",
                }}
                cursor={{ stroke: "var(--border)" }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Line type="monotone" dataKey="nodes" name="Nodes" stroke={INK} strokeWidth={2} dot />
              <Line type="monotone" dataKey="edges" name="Edges" stroke={CHART_VARS.accent} strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <GrowthTable result={result} runNames={runNames} />
    </div>
  );
}

function GrowthTable({
  result,
  runNames,
}: {
  result: TemporalResult;
  runNames: Map<string, string>;
}) {
  const rows = useMemo(() => {
    return result.slices.map((slice, index) => {
      const growth = result.growth[index - 1];
      return { slice, growth };
    });
  }, [result]);

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">Per-run slices</h3>
      <div className="overflow-x-auto rounded-md border">
        <Table aria-label="Per-run network slices">
          <TableHeader>
            <TableRow>
              <TableHead>Run</TableHead>
              <TableHead className="text-right">Nodes</TableHead>
              <TableHead className="text-right">Edges</TableHead>
              <TableHead className="text-right">Density</TableHead>
              <TableHead className="text-right">Reciprocity</TableHead>
              <TableHead className="text-right">Δ nodes</TableHead>
              <TableHead className="text-right">Δ edges</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ slice, growth }) => (
              <TableRow key={slice.run_id}>
                <TableCell className="font-mono text-xs">
                  {runNames.get(slice.run_id) ?? slice.run_id}
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(slice.node_count)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(slice.edge_count)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(slice.density)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(slice.reciprocity)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {growth ? <GrowthValue value={growth.node_growth} /> : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {growth ? <GrowthValue value={growth.edge_growth} /> : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function GrowthValue({ value }: { value: number }) {
  if (value > 0) {
    return <span className="text-emerald-600">+{formatNumber(value)}</span>;
  }
  if (value < 0) {
    return <span className="text-red-600">{formatNumber(value)}</span>;
  }
  return <Badge variant="secondary">0</Badge>;
}
