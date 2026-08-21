"use client";

import { useState } from "react";
import Link from "next/link";
import { Pencil } from "lucide-react";
import type { CollectionRun, RunType } from "@/lib/types";
import { useRuns, useUpdateRunName } from "@/services/queries";
import { DataTable, type Column } from "@/components/features/data-table";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { formatDateTime, formatNumber } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

const TYPE_OPTIONS: { value: RunType | "all"; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "channel", label: "Channel" },
  { value: "video", label: "Video" },
  { value: "recommendation", label: "Recommendations" },
];

function RunNameCell({
  run,
  onRename,
}: {
  run: CollectionRun;
  onRename: (runId: string, name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(run.name ?? "");

  const commit = () => {
    const trimmed = value.trim();
    if (trimmed && trimmed !== (run.name ?? "")) onRename(run.run_id, trimmed);
    else setValue(run.name ?? "");
    setEditing(false);
  };

  if (!editing) {
    return (
      <span className="group flex items-center gap-1.5">
        <span className="max-w-[16rem] truncate text-sm">
          {run.name || <span className="text-muted-foreground">Untitled</span>}
        </span>
        <button
          type="button"
          aria-label={`Rename run ${run.run_id}`}
          onClick={() => {
            setValue(run.name ?? "");
            setEditing(true);
          }}
          className="rounded p-0.5 text-muted-foreground opacity-0 outline-none transition-opacity hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100"
        >
          <Pencil className="size-3.5" aria-hidden />
        </button>
      </span>
    );
  }

  return (
    <Input
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        else if (e.key === "Escape") {
          setValue(run.name ?? "");
          setEditing(false);
        }
      }}
      onBlur={commit}
      autoFocus
      aria-label={`Name for run ${run.run_id}`}
      className="h-7 w-48 text-sm"
    />
  );
}

export function RunLedger() {
  const [runType, setRunType] = useState<RunType | "all">("all");
  const runsQuery = useRuns(runType === "all" ? undefined : runType);
  const renameMutation = useUpdateRunName();

  const columns: Column<CollectionRun>[] = [
    {
      key: "run_id",
      header: "Run",
      sortable: true,
      sortValue: (r) => r.run_id,
      cell: (r) => (
        <Link
          href={`/runs/${r.run_id}`}
          className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        >
          {r.run_id}
        </Link>
      ),
    },
    {
      key: "name",
      header: "Name",
      sortable: true,
      sortValue: (r) => r.name ?? "",
      cell: (r) => (
        <RunNameCell run={r} onRename={(runId, name) => renameMutation.mutate({ runId, name })} />
      ),
    },
    {
      key: "run_type",
      header: "Type",
      sortable: true,
      sortValue: (r) => r.run_type,
      cell: (r) => <Badge variant="secondary">{r.run_type}</Badge>,
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      cell: (r) => <RunStatusBadge status={r.status} />,
    },
    {
      key: "target_url",
      header: "Target",
      sortable: true,
      sortValue: (r) => r.target_url,
      cell: (r) => (
        <span className="block max-w-xs truncate font-mono text-xs">
          {r.target_url}
        </span>
      ),
    },
    {
      key: "entities_discovered",
      header: "Discovered",
      sortable: true,
      sortValue: (r) => r.entities_discovered,
      cell: (r) => formatNumber(r.entities_discovered),
      className: "text-right tabular-nums",
    },
    {
      key: "entities_failed",
      header: "Failed",
      sortable: true,
      sortValue: (r) => r.entities_failed,
      cell: (r) => formatNumber(r.entities_failed),
      className: "text-right tabular-nums",
    },
    {
      key: "started_at",
      header: "Started",
      sortable: true,
      sortValue: (r) => r.started_at,
      cell: (r) => formatDateTime(r.started_at),
    },
  ];

  if (runsQuery.isLoading) return <LoadingState label="Loading runs…" />;
  if (runsQuery.isError)
    return (
      <ErrorState message={(runsQuery.error as Error).message} retry={() => runsQuery.refetch()} />
    );
  if (!runsQuery.data || runsQuery.data.length === 0)
    return (
      <EmptyState
        title="No collection runs yet"
        description="Runs are recorded every time you collect a channel, video, or recommendation set. Start a collection to build your provenance ledger."
      />
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {TYPE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setRunType(option.value)}
            aria-pressed={runType === option.value}
            className="rounded-md border border-border px-3 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-primary aria-pressed:text-primary-foreground"
          >
            {option.label}
          </button>
        ))}
      </div>
      <DataTable
        columns={columns}
        rows={runsQuery.data}
        getRowKey={(r) => r.run_id}
        initialSortKey="started_at"
        initialSortDirection="desc"
        ariaLabel="Collection runs"
      />
    </div>
  );
}
