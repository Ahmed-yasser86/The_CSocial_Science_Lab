"use client";

import { useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/state";
import type {
  CohortComparison,
  EntityComparison,
  PeriodComparison,
  RunComparison,
} from "@/lib/comparison-types";
import { formatNumber } from "@/lib/format";

export function ComparisonTable({
  mode,
  result,
}: {
  mode: string;
  result: unknown;
}) {
  switch (mode) {
    case "videos":
    case "channels":
      return <EntityTable result={result as EntityComparison} />;
    case "periods":
      return <PeriodTable result={result as PeriodComparison} />;
    case "cohorts":
      return <CohortTable result={result as CohortComparison} />;
    case "runs":
      return <RunTable result={result as RunComparison} />;
    default:
      return null;
  }
}

function EntityTable({ result }: { result: EntityComparison }) {
  const rows = useMemo(
    () =>
      result.metrics.flatMap((metric) =>
        result.rows.filter((row) => row.metric === metric),
      ),
    [result],
  );

  if (result.rows.length === 0) {
    return <EmptyState title="No comparison rows" description="The comparison returned no rows." />;
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table aria-label={`${result.entity_type} comparison`}>
        <TableHeader>
          <TableRow>
            <TableHead>Entity</TableHead>
            <TableHead>Metric</TableHead>
            <TableHead className="text-right">Observed</TableHead>
            <TableHead className="text-right">Normalized</TableHead>
            <TableHead className="text-right">Percentile</TableHead>
            <TableHead className="text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={`${row.entity_id}-${row.metric}-${index}`}>
              <TableCell>
                <span className="font-mono text-xs">{row.entity_id}</span>
                {row.title ? (
                  <span className="ml-2 text-muted-foreground">{row.title}</span>
                ) : null}
              </TableCell>
              <TableCell>
                <code className="text-xs">{row.metric}</code>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.value === null || row.value === undefined
                  ? "—"
                  : formatNumber(row.value)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.normalized === null || row.normalized === undefined
                  ? "—"
                  : formatNumber(row.normalized)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.percentile_rank === null || row.percentile_rank === undefined
                  ? "—"
                  : `${row.percentile_rank.toFixed(1)}`}
              </TableCell>
              <TableCell className="text-center">
                <div className="flex flex-wrap justify-center gap-1">
                  {row.is_outlier ? (
                    <Badge variant="destructive">outlier</Badge>
                  ) : null}
                  {row.availability === "missing" ? (
                    <Badge variant="secondary">missing</Badge>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function PeriodTable({ result }: { result: PeriodComparison }) {
  const a = result.period_a;
  const b = result.period_b;
  const metrics = a.metrics.map((m) => m.metric);

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table aria-label="Period comparison">
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead className="text-right">{a.name} mean</TableHead>
            <TableHead className="text-right">{b.name} mean</TableHead>
            <TableHead className="text-right">Growth</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {metrics.map((metric) => {
            const meanA = a.metrics.find((m) => m.metric === metric)?.mean;
            const meanB = b.metrics.find((m) => m.metric === metric)?.mean;
            const change = result.changes.find((c) => c.metric === metric);
            return (
              <TableRow key={metric}>
                <TableCell>
                  <code className="text-xs">{metric}</code>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {meanA === null || meanA === undefined ? "—" : formatNumber(meanA)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {meanB === null || meanB === undefined ? "—" : formatNumber(meanB)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {change?.growth_percent === null ||
                  change?.growth_percent === undefined ? (
                    "—"
                  ) : (
                    <span className={change.growth_percent >= 0 ? "text-emerald-600" : "text-red-600"}>
                      {change.growth_percent >= 0 ? "+" : ""}
                      {change.growth_percent.toFixed(2)}%
                    </span>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function CohortTable({ result }: { result: CohortComparison }) {
  const metrics = result.cohorts[0]?.metrics.map((m) => m.metric) ?? [];
  const names = result.cohorts.map((c) => c.name);

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table aria-label="Cohort comparison">
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            {names.map((name) => (
              <TableHead key={name} className="text-right">
                {name}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>count</TableCell>
            {result.cohorts.map((cohort) => (
              <TableCell key={cohort.name} className="text-right tabular-nums">
                {formatNumber(cohort.count)}
              </TableCell>
            ))}
          </TableRow>
          {metrics.map((metric) => (
            <TableRow key={metric}>
              <TableCell>
                <code className="text-xs">{metric} mean</code>
              </TableCell>
              {result.cohorts.map((cohort) => {
                const stat = cohort.metrics.find((m) => m.metric === metric);
                return (
                  <TableCell key={cohort.name} className="text-right tabular-nums">
                    {stat?.mean === null || stat?.mean === undefined
                      ? "—"
                      : formatNumber(stat.mean)}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function RunTable({ result }: { result: RunComparison }) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table aria-label="Run comparison">
        <TableHeader>
          <TableRow>
            <TableHead>Run</TableHead>
            <TableHead className="text-right">Videos</TableHead>
            <TableHead className="text-right">Channels</TableHead>
            <TableHead className="text-right">Comments</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.snapshots.map((snapshot) => (
            <TableRow key={snapshot.run_id}>
              <TableCell className="font-mono text-xs">{snapshot.run_id}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(snapshot.entity_counts?.videos ?? 0)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(snapshot.entity_counts?.channels ?? 0)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(snapshot.entity_counts?.comments ?? 0)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
