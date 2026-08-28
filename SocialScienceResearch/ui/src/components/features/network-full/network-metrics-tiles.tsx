"use client";

import { useMemo } from "react";
import Link from "next/link";
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
import { formatNumber, formatPercent } from "@/lib/format";
import type { DegreeDistribution, NetworkMetrics, RankedVideo } from "@/lib/network-full-types";

export function NetworkMetricTiles({ metrics }: { metrics: NetworkMetrics }) {
  return (
    <section aria-labelledby="network-metrics-heading">
      <h2 id="network-metrics-heading" className="sr-only">
        Network metrics
      </h2>
      <div
        className="grid grid-cols-2 gap-4 md:grid-cols-4"
        role="group"
        aria-labelledby="network-metrics-heading"
      >
      <Tile label="Nodes" value={formatNumber(metrics.node_count)} />
      <Tile label="Edges" value={formatNumber(metrics.edge_count)} />
      <Tile label="Density" value={formatNumber(metrics.density)} />
      <Tile label="Reciprocity" value={formatNumber(metrics.reciprocity)} />
      <Tile label="Avg clustering" value={formatNumber(metrics.avg_clustering)} />
      <Tile label="Global clustering" value={formatNumber(metrics.global_clustering)} />
      <Tile
        label="Weak components"
        value={`${formatNumber(metrics.weakly_connected_components)}`}
      />
      <Tile
        label="Largest component"
        value={formatPercent(metrics.largest_component_share)}
      />
      <Tile label="Communities" value={formatNumber(metrics.community_count)} />
      <Tile
        label="Modularity"
        value={metrics.modularity === null || metrics.modularity === undefined ? "—" : formatNumber(metrics.modularity)}
      />
      </div>
    </section>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}

export function DegreeDistributionPanel({
  distribution,
}: {
  distribution: Record<string, DegreeDistribution>;
}) {
  const entries = useMemo(
    () => Object.entries(distribution),
    [distribution],
  );
  if (entries.length === 0) return null;

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">Degree distribution</h3>
      <div className="overflow-x-auto rounded-md border">
        <Table aria-label="Degree distribution by source">
          <TableHeader>
            <TableRow>
              <TableHead>Measure</TableHead>
              {entries.map(([name]) => (
                <TableHead key={name} className="text-right">
                  {name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(["min", "max", "mean", "median", "p25", "p75", "p90", "p95", "p99"] as const).map(
              (key) => (
                <TableRow key={key}>
                  <TableCell className="text-xs text-muted-foreground">{key}</TableCell>
                  {entries.map(([name, dist]) => (
                    <TableCell key={name} className="text-right tabular-nums">
                      {dist[key] === null || dist[key] === undefined
                        ? "—"
                        : formatNumber(dist[key])}
                    </TableCell>
                  ))}
                </TableRow>
              ),
            )}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

export function RankingPanel({
  title,
  videos,
  valueLabel,
  titleFor,
  hrefFor,
}: {
  title: string;
  videos: RankedVideo[];
  valueLabel: string;
  /** Optional enrichment: maps a video id to a human title (falls back to id). */
  titleFor?: (videoId: string) => string | undefined;
  /** Optional link target for each row (e.g. the video's detail page). */
  hrefFor?: (videoId: string) => string | undefined;
}) {
  if (videos.length === 0) return null;
  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">{title}</h3>
      <ol className="space-y-1">
        {videos.map((video, index) => {
          const value =
            video.score !== undefined
              ? video.score
              : video.times_recommended !== undefined
                ? video.times_recommended
                : video.outgoing;
          const label = titleFor?.(video.video_id) ?? video.video_id;
          const href = hrefFor?.(video.video_id);
          const content = (
            <>
              <span className="w-6 shrink-0 text-right text-xs text-muted-foreground">
                {index + 1}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-xs">{label}</span>
                <code className="truncate font-mono text-[10px] text-muted-foreground">
                  {video.video_id}
                </code>
              </span>
            </>
          );
          return (
            <li
              key={video.video_id}
              className="flex items-center justify-between gap-2 text-sm"
            >
              {href ? (
                <Link
                  href={href}
                  className="flex min-w-0 flex-1 items-center gap-2 hover:text-primary"
                >
                  {content}
                </Link>
              ) : (
                <span className="flex min-w-0 flex-1 items-center gap-2">
                  {content}
                </span>
              )}
              <Badge variant="outline" className="tabular-nums">
                {value === undefined ? "—" : formatNumber(value)} {valueLabel}
              </Badge>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
