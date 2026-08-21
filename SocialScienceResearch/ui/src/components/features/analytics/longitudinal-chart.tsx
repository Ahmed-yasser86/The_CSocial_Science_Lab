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
import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "@/components/ui/table";
import { AlertTriangle } from "lucide-react";
import { ChartCard } from "@/components/features/charts";
import { EmptyState } from "@/components/features/state";
import { useChannelHistory, useVideoHistory, useAnalyticsErrorToast } from "@/services/analytics";
import { formatCompact, formatDate, formatDateTime } from "@/lib/format";
import { CHART_VARS } from "@/lib/colors";

const INK = CHART_VARS.ink;
const INK_MUTED = CHART_VARS.inkMuted;

export const HISTORY_GAP_DAYS = 30;

interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

interface GrowthDef {
  key: string;
  label: string;
}

interface MetricRow {
  observation_id: string;
  observed_at: string;
  label: string;
  [key: string]: string | number | null;
}

interface HistoryFrameProps {
  entityName: "video" | "channel";
  rows: MetricRow[];
  series: SeriesDef[];
  growth: GrowthDef[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  hasMore: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
  total: number | null | undefined;
  gaps: Map<string, number>;
  gapItems: GapItem[];
}

interface GapItem {
  toId: string;
  fromLabel: string;
  toLabel: string;
  days: number;
}

const chartTooltipStyle = {
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-md)",
    fontSize: "12px",
  },
  labelStyle: { color: "var(--muted-foreground)" },
};

export function VideoLongitudinalChart({ videoId }: { videoId: string }) {
  const query = useVideoHistory(videoId);
  useAnalyticsErrorToast(query.isError, query.error, "Video history could not be loaded");

  const rows = useMemo(
    () => toVideoRows(query.data?.pages.flatMap((p) => p.items) ?? []),
    [query.data],
  );

  return (
    <HistoryFrame
      entityName="video"
      rows={rows}
      series={[
        { key: "view_count", label: "Views", color: INK },
        { key: "like_count", label: "Likes", color: CHART_VARS.accent },
        { key: "comment_count", label: "Comments", color: CHART_VARS.accent2 },
      ]}
      growth={[
        { key: "view_growth_pct", label: "Views" },
        { key: "like_growth_pct", label: "Likes" },
        { key: "comment_growth_pct", label: "Comments" },
      ]}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      hasMore={query.hasNextPage}
      isFetchingNextPage={query.isFetchingNextPage}
      onLoadMore={() => void query.fetchNextPage()}
      total={query.data?.pages[0]?.total ?? null}
      gaps={new Map<string, number>()}
      gapItems={[]}
    />
  );
}

export function ChannelLongitudinalChart({ channelId }: { channelId: string }) {
  const query = useChannelHistory(channelId);
  useAnalyticsErrorToast(query.isError, query.error, "Channel history could not be loaded");

  const rows = useMemo(
    () => toChannelRows(query.data?.pages.flatMap((p) => p.items) ?? []),
    [query.data],
  );

  const { gaps, gapItems } = useMemo(() => computeGaps(rows), [rows]);

  return (
    <HistoryFrame
      entityName="channel"
      rows={rows}
      series={[
        { key: "subscriber_count", label: "Subscribers", color: INK },
        { key: "video_count", label: "Videos", color: CHART_VARS.accent },
        { key: "view_count", label: "Views", color: CHART_VARS.accent2 },
      ]}
      growth={[
        { key: "subscriber_growth_pct", label: "Subscribers" },
        { key: "video_growth_pct", label: "Videos" },
        { key: "view_growth_pct", label: "Views" },
      ]}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      hasMore={query.hasNextPage}
      isFetchingNextPage={query.isFetchingNextPage}
      onLoadMore={() => void query.fetchNextPage()}
      total={query.data?.pages[0]?.total ?? null}
      gaps={gaps}
      gapItems={gapItems}
    />
  );
}

function HistoryFrame({
  entityName,
  rows,
  series,
  growth,
  isLoading,
  isError,
  error,
  hasMore,
  isFetchingNextPage,
  onLoadMore,
  total,
  gaps,
  gapItems,
}: HistoryFrameProps) {
  if (isLoading) {
    return (
      <Card className="space-y-3 p-4">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-24 w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="space-y-2 p-4 text-sm">
        <p className="font-medium">History could not be loaded</p>
        <p className="text-muted-foreground">{(error as Error).message}</p>
      </Card>
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No longitudinal observations"
        description={`Re-collect this ${entityName} over time to build a history.`}
      />
    );
  }

  const chartData = rows.map((r) => ({ ...r }));

  return (
    <div className="space-y-4">
      <ChartCard
        title={
          entityName === "video"
            ? "Engagement over time"
            : "Channel size over time"
        }
        description={
          hasMore
            ? "Scroll the growth table and load further observations to extend the series."
            : "All collected observations are shown (newest last)."
        }
      >
        <div className="h-72 w-full" role="img" aria-label="Longitudinal line chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: INK_MUTED }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: INK_MUTED }}
                width={44}
                allowDecimals={false}
              />
              <Tooltip
                {...chartTooltipStyle}
                labelFormatter={(label) => String(label)}
                formatter={(value, name) => [
                  formatCompact(Number(value)),
                  String(name),
                ]}
                cursor={{ stroke: "var(--border)" }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              {series.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-medium">Per-step growth</h3>
            <p className="text-xs text-muted-foreground">
              Growth is computed by the collector versus the previous observation
              — never estimated.
            </p>
          </div>
          {total !== null && total !== undefined ? (
            <Badge variant="secondary">{formatCompact(total)} observations</Badge>
          ) : null}
        </div>

        {gapItems.length > 0 ? (
          <div className="mb-3 flex flex-col gap-1.5 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-medium text-destructive">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden />
              {gapItems.length} observation gap{gapItems.length > 1 ? "s" : ""} exceeding {HISTORY_GAP_DAYS} days
            </p>
            <ul className="space-y-0.5 font-mono text-xs text-muted-foreground">
              {gapItems.map((g) => (
                <li key={g.toId}>
                  {g.fromLabel} → {g.toLabel} ({g.days}d)
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Observed</TableHead>
              {series.map((s) => (
                <TableHead key={s.key} className="text-right">
                  {s.label}
                </TableHead>
              ))}
              {growth.map((g) => (
                <TableHead key={g.key} className="text-right">
                  {g.label} Δ
                </TableHead>
              ))}
              {entityName === "channel" ? <TableHead>Gaps</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const gapDays = gaps.get(row.observation_id);
              return (
                <TableRow key={row.observation_id}>
                  <TableCell>
                    <span
                      className="cursor-help border-b border-dotted border-muted-foreground/50"
                      title={formatDateTime(row.observed_at)}
                    >
                      {row.label}
                    </span>
                  </TableCell>
                  {series.map((s) => (
                    <TableCell key={s.key} className="text-right tabular-nums">
                      <CellValue value={row[s.key]} />
                    </TableCell>
                  ))}
                  {growth.map((g) => (
                    <TableCell key={g.key} className="text-right tabular-nums">
                      <GrowthCell value={num(row[g.key])} />
                    </TableCell>
                  ))}
                  {entityName === "channel" ? (
                    <TableCell>
                      {gapDays ? (
                        <Badge variant="destructive" title={`Observation gap of ${gapDays} days`}>
                          &gt;{HISTORY_GAP_DAYS}d
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  ) : null}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        {hasMore ? (
          <div className="mt-3 flex justify-center">
            <Button
              variant="outline"
              size="sm"
              onClick={onLoadMore}
              disabled={isFetchingNextPage}
            >
              {isFetchingNextPage ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  Loading…
                </>
              ) : (
                "Load more observations"
              )}
            </Button>
          </div>
        ) : null}
      </Card>

      <p className="text-xs text-muted-foreground">
        History shows recorded observations only — data is observed, never
        estimated. Missing values are rendered as gaps, not zeros.
      </p>
    </div>
  );
}

function CellValue({ value }: { value: string | number | null }) {
  if (value === null || value === undefined) return <span className="text-muted-foreground">—</span>;
  return <>{formatCompact(Number(value))}</>;
}

function GrowthCell({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  if (!Number.isFinite(value)) return <span className="text-muted-foreground">—</span>;
  const positive = value > 0;
  return (
    <span className={positive ? "text-emerald-600" : "text-red-600"}>
      {positive ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function num(value: string | number | null | undefined): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function byObservedAt(a: { observed_at: string }, b: { observed_at: string }) {
  return new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime();
}

function toVideoRows(points: VideoPoint[]): MetricRow[] {
  return [...points]
    .sort(byObservedAt)
    .map((p) => ({
      observation_id: p.observation_id,
      observed_at: p.observed_at,
      label: formatDate(p.observed_at),
      view_count: p.view_count ?? null,
      like_count: p.like_count ?? null,
      comment_count: p.comment_count ?? null,
      view_growth_pct: p.view_growth_pct ?? null,
      like_growth_pct: p.like_growth_pct ?? null,
      comment_growth_pct: p.comment_growth_pct ?? null,
    }));
}

function toChannelRows(points: ChannelPoint[]): MetricRow[] {
  return [...points]
    .sort(byObservedAt)
    .map((p) => ({
      observation_id: p.observation_id,
      observed_at: p.observed_at,
      label: formatDate(p.observed_at),
      subscriber_count: p.subscriber_count ?? null,
      video_count: p.video_count ?? null,
      view_count: p.view_count ?? null,
      subscriber_growth_pct: p.subscriber_growth_pct ?? null,
      video_growth_pct: p.video_growth_pct ?? null,
      view_growth_pct: p.view_growth_pct ?? null,
    }));
}

function computeGaps(rows: MetricRow[]): { gaps: Map<string, number>; gapItems: GapItem[] } {
  const gaps = new Map<string, number>();
  const gapItems: GapItem[] = [];
  for (let i = 1; i < rows.length; i++) {
    const prev = new Date(rows[i - 1].observed_at).getTime();
    const cur = new Date(rows[i].observed_at).getTime();
    if (Number.isFinite(prev) && Number.isFinite(cur) && cur > prev) {
      const days = (cur - prev) / 86_400_000;
      if (days > HISTORY_GAP_DAYS) {
        const rounded = Math.round(days);
        gaps.set(rows[i].observation_id, rounded);
        gapItems.push({
          toId: rows[i].observation_id,
          fromLabel: rows[i - 1].label,
          toLabel: rows[i].label,
          days: rounded,
        });
      }
    }
  }
  return { gaps, gapItems };
}

type VideoPoint = {
  observation_id: string;
  observed_at: string;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  view_growth_pct?: number | null;
  like_growth_pct?: number | null;
  comment_growth_pct?: number | null;
};

type ChannelPoint = {
  observation_id: string;
  observed_at: string;
  subscriber_count?: number | null;
  video_count?: number | null;
  view_count?: number | null;
  subscriber_growth_pct?: number | null;
  video_growth_pct?: number | null;
  view_growth_pct?: number | null;
};