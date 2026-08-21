"use client";

import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ChartCard } from "@/components/features/charts";
import { EmptyState } from "@/components/features/state";
import {
  useCommentParticipation,
  useAnalyticsErrorToast,
  statNumber,
  statMeta,
} from "@/services/analytics";
import type { StatisticLike } from "@/services/analytics";
import { formatCompact, formatPercent } from "@/lib/format";

export function CommentParticipation({ videoId }: { videoId: string }) {
  const query = useCommentParticipation(videoId);
  useAnalyticsErrorToast(query.isError, query.error, "Participation analytics could not be loaded");

  const topAuthors = useMemo(() => {
    const counts = query.data?.author_comment_counts ?? [];
    return [...counts].sort((a, b) => b.comment_count - a.comment_count).slice(0, 5);
  }, [query.data]);

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
        <p className="font-medium">Participation could not be loaded</p>
        <p className="text-muted-foreground">{(query.error as Error).message}</p>
      </Card>
    );
  }

  const data = query.data;
  if (!data || data.total_comments === 0) {
    return (
      <EmptyState
        title="No comment participation"
        description="Collect comments for this video to compute author participation."
      />
    );
  }

  const gini = statNumber(data.participation_gini ?? data.gini);
  const giniMeta = statMeta(data.participation_gini ?? data.gini) as StatisticLike;
  const top10 = statNumber(data.top_10pct_concentration);
  const top10Meta = statMeta(data.top_10pct_concentration);

  return (
    <ChartCard
      title="Author participation"
      description="How comment volume is spread across unique vs repeat authors."
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Stat
          label="Total comments"
          value={data.total_comments}
          format={(v) => formatCompact(v)}
        />
        <Stat label="Unique authors" value={data.unique_authors} format={(v) => formatCompact(v)} />
        <Stat label="Repeat authors" value={data.repeat_authors} format={(v) => formatCompact(v)} />
        <Stat
          label="Repeat share"
          value={data.repeat_author_share}
          format={(v) => formatPercent(v)}
        />
        <Stat
          label="Gini"
          value={gini}
          format={(v) => formatPercent(v)}
          meta={giniMeta.method ? `method: ${giniMeta.method}` : undefined}
        />
        <Stat
          label="Top 10% concentration"
          value={top10}
          format={(v) => formatPercent(v)}
          meta={top10Meta.method ? `method: ${top10Meta.method}` : undefined}
        />
      </div>

      {topAuthors.length > 0 ? (
        <>
          <Separator className="my-4" />
          <div className="space-y-2">
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Top authors by comment count
            </h4>
            <ul className="space-y-1.5">
              {topAuthors.map((a) => (
                <li
                  key={a.author_id ?? a.author_name ?? a.comment_count}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <span className="truncate font-mono text-xs">
                    {a.author_name ?? a.author_id ?? "unknown author"}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    {formatCompact(a.comment_count)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </ChartCard>
  );
}

function Stat({
  label,
  value,
  format,
  meta,
}: {
  label: string;
  value: number | null | undefined;
  format: (v: number) => string;
  meta?: string;
}) {
  return (
    <Card className="flex flex-col justify-between gap-1 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-2xl font-semibold tabular-nums">
        {value === null || value === undefined ? "—" : format(value)}
      </p>
      {meta ? <p className="text-xs text-muted-foreground">{meta}</p> : null}
    </Card>
  );
}