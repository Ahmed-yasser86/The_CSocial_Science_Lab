"use client";

import Link from "next/link";
import { Database, MessageSquare, ScrollText, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoverage } from "@/services/queries";
import { formatNumber, formatDateTime } from "@/lib/format";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function CoveragePanel() {
  const query = useCoverage();

  if (query.isPending) {
    return (
      <Card className="p-4">
        <Skeleton className="h-4 w-40" />
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card className="flex items-start gap-3 border-destructive/40 p-4 text-sm">
        <RefreshCw className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
        <div>
          <p className="font-medium">Coverage could not be loaded</p>
          <p className="text-muted-foreground">
            {(query.error as Error).message}
          </p>
        </div>
      </Card>
    );
  }

  const c = query.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Dataset coverage</h2>
        <p className="text-xs text-muted-foreground">
          As of {formatDateTime(c.generated_at)}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={Database}
          label="Channels"
          value={c.total_channels}
          detail={`${formatNumber(c.total_runs)} collection run(s)`}
        />
        <StatCard
          icon={MessageSquare}
          label="Videos"
          value={c.total_videos}
          detail={`${formatNumber(c.total_comments)} comments captured`}
        />
        <StatCard
          icon={ScrollText}
          label="Transcripts"
          value={c.transcripts_available}
          detail={`${c.transcripts_missing} missing · ${c.transcripts_unsupported} unsupported`}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="space-y-2 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Comment coverage</span>
            <span className="tabular-nums text-muted-foreground">
              {formatNumber(c.videos_with_comments)} / {formatNumber(c.total_videos)} videos
            </span>
          </div>
          <Progress value={Math.round(c.comment_coverage * 100)} aria-label="Comment coverage" />
          <p className="text-xs text-muted-foreground">
            {percent(c.comment_coverage)} of collected videos have comment rows
          </p>
        </Card>

        <Card className="space-y-2 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Transcript coverage</span>
            <span className="tabular-nums text-muted-foreground">
              {formatNumber(c.transcripts_available)} / {formatNumber(c.total_videos)} videos
            </span>
          </div>
          <Progress value={Math.round(c.transcript_coverage * 100)} aria-label="Transcript coverage" />
          <p className="text-xs text-muted-foreground">
            {percent(c.transcript_coverage)} of collected videos have an available transcript
          </p>
        </Card>
      </div>

      {c.last_run_id ? (
        <p className="text-xs text-muted-foreground">
          Last collection:{" "}
          <Button
            render={<Link href={`/runs/${c.last_run_id}`} />}
            nativeButton={false}
            variant="link"
            size="sm"
            className="h-auto p-0"
          >
            <span className="font-mono">{c.last_run_id}</span>
          </Button>
        </p>
      ) : null}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <Card className="space-y-1 p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="size-3.5" aria-hidden />
        {label}
      </div>
      <p className="text-2xl font-semibold tabular-nums">{formatNumber(value)}</p>
      <p className="text-xs text-muted-foreground">{detail}</p>
    </Card>
  );
}
