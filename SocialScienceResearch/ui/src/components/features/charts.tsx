"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Cell,
  LabelList,
} from "recharts";
import type { CommentPercentiles } from "@/lib/types";
import { formatCompact } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { CHART_VARS } from "@/lib/colors";

const INK = CHART_VARS.ink;
const INK_MUTED = CHART_VARS.inkMuted;

function chartTooltipStyle() {
  return {
    contentStyle: {
      background: "var(--popover)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-md)",
      fontSize: "12px",
    },
    labelStyle: { color: "var(--muted-foreground)" },
  };
}

export function TimelineChart({
  data,
  highlightMissing = true,
  ariaLabel,
}: {
  data: { bucket: string; count: number }[];
  highlightMissing?: boolean;
  ariaLabel?: string;
}) {
  const rows = data.map((d) => ({
    ...d,
    label: d.bucket === "missing_published_at" ? "missing timestamp" : d.bucket,
    isMissing: d.bucket === "missing_published_at",
  }));

  return (
    <div className="h-64 w-full" role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: INK_MUTED }}
            interval="preserveStartEnd"
            angle={rows.length > 24 ? -45 : 0}
            textAnchor={rows.length > 24 ? "end" : "middle"}
            height={rows.length > 24 ? 60 : 30}
          />
          <YAxis
            tick={{ fontSize: 10, fill: INK_MUTED }}
            allowDecimals={false}
            width={36}
          />
          <Tooltip {...chartTooltipStyle()} cursor={{ fill: "var(--muted)" }} />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {rows.map((r, i) => (
              <Cell
                key={i}
                fill={highlightMissing && r.isMissing ? INK_MUTED : INK}
                fillOpacity={highlightMissing && r.isMissing ? 0.35 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const HIST_BAND_COUNT = 20;

export function HistogramChart({
  percentiles,
  ariaLabel,
}: {
  percentiles: CommentPercentiles;
  ariaLabel?: string;
}) {
  const bins = useMemo(() => {
    const values = percentiles.observed_like_counts;
    if (values.length === 0) return [];
    const max = Math.max(...values);
    if (max === 0) {
      return [{ from: 0, to: 0, label: "0", count: values.length }];
    }
    const width = Math.max(1, Math.ceil(max / HIST_BAND_COUNT));
    const bucket = new Map<number, number>();
    for (const v of values) {
      const b = Math.floor(v / width);
      bucket.set(b, (bucket.get(b) ?? 0) + 1);
    }
    return [...bucket.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([b, count]) => ({
        from: b * width,
        to: (b + 1) * width - 1,
        label: `${formatCompact(b * width)}–${formatCompact((b + 1) * width - 1)}`,
        count,
      }));
  }, [percentiles]);

  const bandLines = Object.entries(percentiles.bands)
    .filter(([, v]) => v !== null)
    .map(([band, value]) => ({ band, value: Number(value) }));

  return (
    <div className="h-64 w-full" role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bins} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: INK_MUTED }}
            interval={Math.max(0, Math.floor(bins.length / 8))}
            height={40}
          />
          <YAxis tick={{ fontSize: 10, fill: INK_MUTED }} allowDecimals={false} width={36} />
          <Tooltip {...chartTooltipStyle()} cursor={{ fill: "var(--muted)" }} />
          {bandLines.map(({ band, value }) => (
            <ReferenceLine
              key={band}
              x={value}
              stroke={INK_MUTED}
              strokeDasharray="4 4"
            />
          ))}
          <Bar dataKey="count" fill={INK} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RankingChart({
  data,
  valueLabel,
  ariaLabel,
}: {
  data: { id: string; label: string; value: number }[];
  valueLabel: string;
  ariaLabel?: string;
}) {
  const rows = useMemo(
    () =>
      [...data]
        .sort((a, b) => b.value - a.value)
        .slice(0, 10)
        .map((d, i) => ({ ...d, rank: i + 1 })),
    [data],
  );

  return (
    <div className="h-64 w-full" role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 8, right: 48, bottom: 8, left: 8 }}
        >
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 10, fill: INK_MUTED }} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={210}
            tick={{ fontSize: 11, fill: INK }}
            interval={0}
          />
          <Tooltip
            {...chartTooltipStyle()}
            formatter={(value) => [`${formatCompact(Number(value))} ${valueLabel}`, ""]}
            cursor={{ fill: "var(--muted)" }}
          />
          <Bar dataKey="value" fill={INK} radius={[0, 2, 2, 0]}>
            <LabelList
              dataKey="value"
              position="right"
              formatter={(value) => formatCompact(Number(value))}
              className="fill-muted-foreground"
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChartCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="p-4">
      <div className="mb-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {description ? (
          <p className="text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {children}
    </Card>
  );
}
