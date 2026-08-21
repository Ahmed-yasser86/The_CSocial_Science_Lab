"use client";

import { useState } from "react";
import Link from "next/link";
import { useNetworkSummary, useRuns } from "@/services/queries";
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/features/state";
import { RankingChart } from "@/components/features/charts";
import { DataTable, type Column } from "@/components/features/data-table";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatNumber } from "@/lib/format";

function VideoLink({ id, title }: { id: string; title?: string }) {
  return (
    <Link
      href={`/network/videos/${id}`}
      className="line-clamp-1 max-w-xs font-mono text-xs text-primary underline-offset-2 hover:underline"
    >
      {title ?? id}
    </Link>
  );
}

export function NetworkSummaryView() {
  const [runId, setRunId] = useState<string>("all");
  const runsQuery = useRuns("recommendation");
  const summaryQuery = useNetworkSummary(runId === "all" ? undefined : runId, 10);

  const recommendationRuns =
    runsQuery.data
      ?.filter((r) => r.status !== "pending" && r.status !== "running")
      .slice()
      .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? "")) ?? [];

  if (summaryQuery.isLoading) return <LoadingState label="Building recommendation graph…" />;
  if (summaryQuery.isError)
    return <ErrorState message={(summaryQuery.error as Error).message} retry={() => summaryQuery.refetch()} />;

  const summary = summaryQuery.data!;

  if (summary.node_count === 0) {
    return (
      <EmptyState
        title="Empty recommendation network"
        description="The graph is rebuilt on demand from observed recommendation edges. No edges have been recorded yet — run a recommendation collection for a video to observe its “Up Next” rail, ranked by feed position."
      />
    );
  }

  const mostRecommendedTable: Column<(typeof summary.most_recommended)[number]>[] = [
    {
      key: "video_id",
      header: "Video",
      sortable: true,
      sortValue: (r) => r.video_id,
      cell: (r) => <VideoLink id={r.video_id} />,
    },
    {
      key: "times_recommended",
      header: "Times recommended",
      sortable: true,
      sortValue: (r) => r.times_recommended,
      cell: (r) => formatNumber(r.times_recommended),
      className: "text-right tabular-nums",
    },
  ];

  const activeSourcesTable: Column<(typeof summary.most_active_sources)[number]>[] = [
    {
      key: "video_id",
      header: "Source video",
      sortable: true,
      sortValue: (r) => r.video_id,
      cell: (r) => <VideoLink id={r.video_id} />,
    },
    {
      key: "outgoing",
      header: "Outgoing edges",
      sortable: true,
      sortValue: (r) => r.outgoing,
      cell: (r) => formatNumber(r.outgoing),
      className: "text-right tabular-nums",
    },
  ];

  const pagerankTable: Column<(typeof summary.highest_pagerank)[number]>[] = [
    {
      key: "video_id",
      header: "Video",
      sortable: true,
      sortValue: (r) => r.video_id,
      cell: (r) => <VideoLink id={r.video_id} />,
    },
    {
      key: "pagerank",
      header: "PageRank",
      sortable: true,
      sortValue: (r) => r.pagerank,
      cell: (r) => r.pagerank.toFixed(6),
      className: "text-right tabular-nums",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Directed graph rebuilt from observed recommendation edges. Slice by a
          single collection run for temporal analysis.
        </p>
        <Select
          value={runId}
          onValueChange={(v) => setRunId(v ?? "all")}
          items={[
            { value: "all", label: "All runs" },
            ...recommendationRuns.map((r) => ({ value: r.run_id, label: r.name ?? r.run_id })),
          ]}
        >
          <SelectTrigger size="sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="w-[--anchor-width]">
            <SelectItem value="all">All runs</SelectItem>
            {recommendationRuns.map((r) => (
              <SelectItem key={r.run_id} value={r.run_id}>
                {r.name ?? r.run_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Nodes" value={summary.node_count} />
        <Kpi label="Edges" value={summary.edge_count} />
        <Kpi label="Sources" value={summary.source_count} />
        <Kpi label="Targets" value={summary.target_count} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-medium">Most recommended</h2>
          <RankingChart
            data={summary.most_recommended.map((r) => ({
              id: r.video_id,
              label: r.video_id,
              value: r.times_recommended,
            }))}
            valueLabel="recommendations"
            ariaLabel="Videos most frequently recommended by other videos"
          />
          <div className="mt-3">
            <DataTable columns={mostRecommendedTable} rows={summary.most_recommended} getRowKey={(r) => r.video_id} ariaLabel="Most recommended videos" />
          </div>
        </Card>

        <Card className="p-4">
          <h2 className="mb-3 text-sm font-medium">Most active sources</h2>
          <RankingChart
            data={summary.most_active_sources.map((r) => ({
              id: r.video_id,
              label: r.video_id,
              value: r.outgoing,
            }))}
            valueLabel="edges"
            ariaLabel="Videos that recommend the most other videos"
          />
          <div className="mt-3">
            <DataTable columns={activeSourcesTable} rows={summary.most_active_sources} getRowKey={(r) => r.video_id} ariaLabel="Most active sources" />
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-medium">PageRank leaders</h2>
        <DataTable columns={pagerankTable} rows={summary.highest_pagerank} getRowKey={(r) => r.video_id} ariaLabel="Highest PageRank videos" />
      </Card>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-2xl font-semibold tabular-nums">{formatNumber(value)}</p>
    </Card>
  );
}
