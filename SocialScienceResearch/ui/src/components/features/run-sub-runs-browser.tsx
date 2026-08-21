"use client";

import Link from "next/link";
import { useRunSubRuns } from "@/services/queries";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { DataTable, type Column } from "@/components/features/data-table";
import { Badge } from "@/components/ui/badge";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { CollectionStatus } from "@/lib/types";

interface Row {
  run_id: string;
  run_type: string;
  status: CollectionStatus;
  target_video_id: string | null;
  target_channel_id: string | null;
  entities_discovered: number;
  entities_succeeded: number;
  entities_existing: number;
  entities_failed: number;
  started_at: string;
  name: string | null;
}

const columns: Column<Row>[] = [
  {
    key: "run",
    header: "Run",
    cell: (row) => (
      <Link
        href={`/runs/${row.run_id}`}
        className="font-mono text-sm text-primary underline-offset-2 hover:underline"
      >
        {row.name ?? row.run_id}
      </Link>
    ),
  },
  {
    key: "type",
    header: "Type",
    cell: (row) => <Badge variant="secondary">{row.run_type}</Badge>,
  },
  {
    key: "target",
    header: "Target",
    cell: (row) =>
      row.target_video_id ? (
        <Link
          href={`/videos/${row.target_video_id}`}
          className="font-mono text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {row.target_video_id}
        </Link>
      ) : row.target_channel_id ? (
        <Link
          href={`/channels/${row.target_channel_id}`}
          className="font-mono text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {row.target_channel_id}
        </Link>
      ) : (
        "—"
      ),
  },
  {
    key: "status",
    header: "Status",
    cell: (row) => <RunStatusBadge status={row.status} />,
  },
  {
    key: "discovered",
    header: "Discovered",
    cell: (row) => <span className="tabular-nums">{formatNumber(row.entities_discovered)}</span>,
  },
  {
    key: "new",
    header: "New",
    cell: (row) => <span className="tabular-nums">{formatNumber(row.entities_succeeded)}</span>,
  },
  {
    key: "existing",
    header: "Existing",
    cell: (row) => <span className="tabular-nums">{formatNumber(row.entities_existing)}</span>,
  },
  {
    key: "failed",
    header: "Failed",
    cell: (row) => <span className="tabular-nums">{formatNumber(row.entities_failed)}</span>,
  },
  {
    key: "started",
    header: "Started",
    cell: (row) => (
      <span className="font-mono text-xs text-muted-foreground">
        {formatDateTime(row.started_at)}
      </span>
    ),
  },
];

export function RunSubRunsBrowser({ runId }: { runId: string }) {
  const subRunsQuery = useRunSubRuns(runId);

  if (subRunsQuery.isLoading) return <LoadingState label="Loading sub-runs…" />;
  if (subRunsQuery.isError)
    return <ErrorState message={(subRunsQuery.error as Error).message} />;

  const subRuns = subRunsQuery.data?.items ?? [];

  if (subRuns.length === 0) {
    return (
      <EmptyState
        title="No sub-runs registered"
        description="This run has no child runs. Bulk recommendation scrapes register one sub-run per source video under this run."
      />
    );
  }

  return (
    <DataTable
      columns={columns}
      rows={subRuns as unknown as Row[]}
      getRowKey={(row) => row.run_id}
    />
  );
}
