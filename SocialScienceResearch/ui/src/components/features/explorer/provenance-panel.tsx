"use client";

import { ShieldCheck } from "lucide-react";
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
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { useProvenance } from "@/services/explorer";
import { formatDateTime } from "@/lib/format";
import type { ProvenanceRecord, RunSummary } from "@/lib/explorer-types";

export function ProvenancePanel({
  entity,
  entityId,
}: {
  entity: string;
  entityId: string;
}) {
  const query = useProvenance(entity, entityId);

  if (query.isLoading) return <LoadingState label="Loading provenance…" />;
  if (query.isError)
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : "Failed to load provenance"
        }
        retry={() => query.refetch()}
      />
    );

  const record = query.data as ProvenanceRecord | undefined;
  if (!record) return <LoadingState label="Loading provenance…" />;

  const firstRunId = record.first_observed_run_id;
  const firstRun = record.runs?.find((run) => run.run_id === firstRunId);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" aria-hidden />
          <h3 className="text-sm font-medium">Collection provenance</h3>
        </div>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
          <ProvenanceField label="Entity" value={record.entity} mono />
          <ProvenanceField label="First observed run" value={firstRunId ?? "—"} mono />
          <ProvenanceField
            label="First seen"
            value={record.first_seen_at ? formatDateTime(record.first_seen_at) : "—"}
          />
          <ProvenanceField
            label="Observations"
            value={record.observation_count?.toLocaleString() ?? "—"}
          />
          <ProvenanceField label="Provider" value={record.provider ?? "—"} />
          {record.channel_id ? (
            <ProvenanceField label="Channel" value={record.channel_id} mono />
          ) : null}
          {record.parent_comment_id ? (
            <ProvenanceField label="Parent comment" value={record.parent_comment_id} mono />
          ) : null}
          {record.root_comment_id ? (
            <ProvenanceField label="Root comment" value={record.root_comment_id} mono />
          ) : null}
        </dl>
      </Card>

      {firstRun ? (
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-medium">First-observed run</h3>
          <RunCard run={firstRun} />
        </Card>
      ) : null}

      <Card className="p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium">Observation history</h3>
          <Badge variant="secondary">{record.observations?.length ?? 0} shown</Badge>
        </div>
        {record.observations && record.observations.length > 0 ? (
          <Table aria-label="Observation history">
            <TableHeader>
              <TableRow>
                <TableHead>Observed at</TableHead>
                <TableHead>Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {record.observations.map((obs, index) => (
                <TableRow key={`${obs.run_id ?? "run"}-${index}`}>
                  <TableCell>
                    {obs.observed_at ? formatDateTime(obs.observed_at) : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {obs.run_id ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState
            title="No observations recorded"
            description="This record has no observation history yet."
          />
        )}
      </Card>

      {record.runs && record.runs.length > 0 ? (
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-medium">Producing runs</h3>
          <div className="space-y-2">
            {record.runs.map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function ProvenanceField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/50 pb-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : "text-sm"}>{value}</dd>
    </div>
  );
}

function RunCard({ run }: { run: RunSummary }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <code className="text-xs">{run.run_id}</code>
        <div className="flex flex-wrap gap-1.5">
          {run.run_type ? (
            <Badge variant="outline">{run.run_type}</Badge>
          ) : null}
          {run.status ? <Badge variant="secondary">{run.status}</Badge> : null}
        </div>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-3">
        <div className="text-xs text-muted-foreground">
          provider: <span className="text-foreground">{run.provider ?? "—"}</span>
        </div>
        <div className="text-xs text-muted-foreground">
          version:{" "}
          <span className="text-foreground">{run.provider_version ?? "—"}</span>
        </div>
        <div className="text-xs text-muted-foreground">
          started:{" "}
          <span className="text-foreground">
            {run.started_at ? formatDateTime(run.started_at) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
