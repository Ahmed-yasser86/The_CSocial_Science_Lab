"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { ChartCard } from "@/components/features/charts";
import { EmptyState } from "@/components/features/state";
import {
  useCommentReplies,
  useAnalyticsErrorToast,
} from "@/services/analytics";
import { formatPercent } from "@/lib/format";

export function CommentReplies({ videoId }: { videoId: string }) {
  const query = useCommentReplies(videoId);
  useAnalyticsErrorToast(query.isError, query.error, "Reply analytics could not be loaded");

  if (query.isLoading) {
    return (
      <Card className="space-y-3 p-4">
        <Skeleton className="h-4 w-48" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card className="space-y-2 p-4 text-sm">
        <p className="font-medium">Reply structure could not be loaded</p>
        <p className="text-muted-foreground">{(query.error as Error).message}</p>
      </Card>
    );
  }

  const data = query.data;
  if (!data || data.total_comments === 0) {
    return (
      <EmptyState
        title="No reply structure"
        description="Comment threading is derived from the collected comment rows."
      />
    );
  }

  return (
    <ChartCard
      title="Reply structure"
      description="Reply rate and thread size over the video's comments."
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Stat label="Reply rate" value={data.reply_rate} format={(v) => formatPercent(v)} />
        <Stat label="Thread count" value={data.thread_count} format={(v) => formatCount(v)} />
        <Stat label="Max thread depth" value={data.deepest_thread_depth} format={(v) => formatCount(v)} />
        <Stat label="Mean thread size" value={data.thread_size_mean} format={(v) => v.toFixed(2)} />
        <Stat label="Median thread size" value={data.thread_size_median} format={(v) => v.toFixed(2)} />
        <Stat label="Orphan replies" value={data.orphan_reply_count} format={(v) => formatCount(v)} />
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        {formatCount(data.reply_count)} of {formatCount(data.total_comments)} comments
        are replies ({formatPercent(data.reply_rate)}).
      </p>
    </ChartCard>
  );
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function Stat({
  label,
  value,
  format,
}: {
  label: string;
  value: number | null | undefined;
  format: (v: number) => string;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">
        {value === null || value === undefined ? "—" : format(value)}
      </p>
    </Card>
  );
}