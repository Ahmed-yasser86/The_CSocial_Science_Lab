"use client";

import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { useNetworkEdges } from "@/services/networkFull";
import { useRuns } from "@/services/queries";
import { formatNumber } from "@/lib/format";

export function EdgeTable({ runId }: { runId?: string }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const query = useNetworkEdges(runId, cursor ?? undefined);
  const runsQuery = useRuns();
  const runNames = new Map(
    (runsQuery.data ?? [])
      .filter((run) => run.name)
      .map((run) => [run.run_id, run.name as string]),
  );

  if (query.isLoading) return <LoadingState label="Loading edges…" />;
  if (query.isError)
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : "Failed to load network edges"
        }
        retry={() => query.refetch()}
      />
    );

  const page = query.data;
  const edges = page?.items ?? [];
  const total = page?.total ?? null;

  function goNext() {
    if (!page?.has_more || !page.next_cursor) return;
    setHistory((prev) => [...prev, cursor ?? "start"]);
    setCursor(page.next_cursor);
  }

  function goPrev() {
    const prevCursor = history[history.length - 1];
    setHistory((prev) => prev.slice(0, -1));
    setCursor(prevCursor ?? null);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {total !== null && total !== undefined
            ? `${formatNumber(total)} edges`
            : `${edges.length} edges on this page`}
        </span>
        {runId ? <span className="font-mono">run: {runId}</span> : null}
      </div>

      {edges.length === 0 ? (
        <EmptyState
          title="No edges observed"
          description="The recommendation network has no persisted edges for this slice."
        />
      ) : (
        <div className="w-full overflow-x-auto rounded-md border">
          <Table aria-label="Network edges">
            <TableHeader>
              <TableRow>
                <TableHead>Source video</TableHead>
                <TableHead>Recommended video</TableHead>
                <TableHead className="text-right">Position</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {edges.map((edge, index) => (
                <TableRow key={`${edge.source_video_id}-${edge.recommended_video_id}-${index}`}>
                  <TableCell className="font-mono text-xs">{edge.source_video_id}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {edge.recommended_video_id}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {edge.position === null || edge.position === undefined
                      ? "—"
                      : `#${edge.position + 1}`}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-muted-foreground">
                    {edge.title ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {edge.channel_id ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {edge.run_id ? runNames.get(edge.run_id) ?? edge.run_id : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 border-t pt-3">
        <p className="text-xs text-muted-foreground">
          {page?.has_more ? "More edges available" : "End of edges"}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={goPrev}
            disabled={query.isFetching || history.length === 0}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={goNext}
            disabled={query.isFetching || !page?.has_more || !page.next_cursor}
          >
            {query.isFetching ? "Loading…" : "Next"}
          </Button>
        </div>
      </div>
    </div>
  );
}
