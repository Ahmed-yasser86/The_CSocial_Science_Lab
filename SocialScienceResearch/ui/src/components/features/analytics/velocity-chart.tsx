"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ChartCard } from "@/components/features/charts";
import { EmptyState } from "@/components/features/state";
import {
  useCommentVelocity,
  useAnalyticsErrorToast,
} from "@/services/analytics";
import type { VelocityBucket } from "@/lib/analytics-types";
import { formatCompact, formatDuration, formatPercent } from "@/lib/format";
import { CHART_VARS } from "@/lib/colors";

const INK = CHART_VARS.ink;
const INK_MUTED = CHART_VARS.inkMuted;

const chartTooltipStyle = {
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-md)",
    fontSize: "12px",
  },
  labelStyle: { color: "var(--muted-foreground)" },
};

export function VelocityChart({ videoId }: { videoId: string }) {
  const [bucket, setBucket] = useState<VelocityBucket>("day");
  const query = useCommentVelocity(videoId, bucket);
  useAnalyticsErrorToast(query.isError, query.error, "Comment velocity could not be loaded");

  if (query.isLoading) {
    return (
      <Card className="space-y-3 p-4">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-56 w-full" />
        <div className="grid gap-3 sm:grid-cols-3">
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
        <p className="font-medium">Velocity could not be loaded</p>
        <p className="text-muted-foreground">{(query.error as Error).message}</p>
      </Card>
    );
  }

  const data = query.data;
  if (!data) {
    return <EmptyState title="No velocity data" description="No comments to bucket." />;
  }

  const points = data.timeline ?? data.points ?? [];
  const age = data.comment_age;

  return (
    <ChartCard
      title="Comment velocity"
      description="Comment counts per time bucket relative to video upload."
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1 rounded-lg bg-muted p-[3px]">
          {(["day", "hour"] as const).map((b) => (
            <Button
              key={b}
              variant={bucket === b ? "default" : "ghost"}
              size="xs"
              className={bucket === b ? "shadow-sm" : ""}
              onClick={() => setBucket(b)}
            >
              {b === "day" ? "Daily" : "Hourly"}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {formatCompact(data.total_comments ?? 0)} comments ·{" "}
          {formatCompact(data.timestamped_comments ?? 0)} timestamped
        </p>
      </div>

      {points.length === 0 ? (
        <EmptyState
          title="No bucketed comments"
          description={
            data.upload_missing
              ? "Upload date is missing, so relative buckets cannot be computed."
              : "No comment timestamps are available for bucketing."
          }
        />
      ) : (
        <div className="h-56 w-full" role="img" aria-label="Comment velocity bar chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 9, fill: INK_MUTED }}
                interval="preserveStartEnd"
                angle={points.length > 12 ? -45 : 0}
                textAnchor={points.length > 12 ? "end" : "middle"}
                height={points.length > 12 ? 48 : 24}
              />
              <YAxis tick={{ fontSize: 10, fill: INK_MUTED }} allowDecimals={false} width={36} />
              <Tooltip {...chartTooltipStyle} cursor={{ fill: "var(--muted)" }} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {points.map((p, i) => (
                  <Cell key={i} fill={INK} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Stat label="First 24h share" value={data.first_24h_share} format={(v) => formatPercent(v)} />
        <Stat label="First 7d share" value={data.first_7d_share} format={(v) => formatPercent(v)} />
        <Stat
          label="Mean comment age"
          value={age?.mean_seconds ?? null}
          format={(v) => formatDuration(v)}
          hint="relative to upload"
        />
        <Stat
          label="Median comment age"
          value={age?.median_seconds ?? null}
          format={(v) => formatDuration(v)}
          hint="relative to upload"
        />
        <Stat
          label="Negative-age comments"
          value={age?.negative_age_count ?? 0}
          format={(v) => formatCompact(v)}
          hint="timestamps before upload"
        />
        <Stat
          label="Missing published-at"
          value={data.missing_published_at ?? 0}
          format={(v) => formatCompact(v)}
          hint="excluded from buckets"
        />
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Shares and age are computed by the collector from observed timestamps —
        data is observed, never estimated.
      </p>
    </ChartCard>
  );
}

function Stat({
  label,
  value,
  format,
  hint,
}: {
  label: string;
  value: number | null | undefined;
  format: (v: number) => string;
  hint?: string;
}) {
  return (
    <Card className="flex flex-col justify-between gap-1 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xl font-semibold tabular-nums">
        {value === null || value === undefined ? "—" : format(value)}
      </p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}