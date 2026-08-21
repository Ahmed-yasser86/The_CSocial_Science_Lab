"use client";

import Link from "next/link";
import { DataTable, Column } from "@/components/features/data-table";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatDuration } from "@/lib/format";
import type { RunVideo } from "@/lib/types";
import { useRunVideos } from "@/services/queries";

type VideoFormat = "Short" | "Long" | "Live";

function getVideoFormat(video: RunVideo): VideoFormat {
  if (video.is_short === true) return "Short";
  if (video.live_status === "is_live" || video.live_status === "is_upcoming") return "Live";
  return "Long";
}

function formatTags(tags: string[]): string {
  if (!tags || tags.length === 0) return "—";
  return tags.slice(0, 5).join(", ") + (tags.length > 5 ? "…" : "");
}

interface Discovery {
  kind?: string;
  source_video_id?: string;
  position?: number | null;
  run_id?: string;
}

function getDiscovery(video: RunVideo): Discovery | null {
  const raw = video.raw_json as Record<string, unknown> | undefined;
  const disc = raw?._discovery;
  if (!disc || typeof disc !== "object") return null;
  return disc as Discovery;
}

const COLUMNS: Column<RunVideo>[] = [
  {
    key: "title",
    header: "Title",
    cell: (row) => (
      <Link
        href={`/videos/${row.video_id}`}
        className="text-primary hover:underline max-w-[300px] truncate block"
      >
        {row.title ?? "—"}
      </Link>
    ),
    sortable: true,
    sortValue: (row) => row.title ?? "",
  },
  {
    key: "video_id",
    header: "Video ID",
    cell: (row) => (
      <span className="font-mono text-xs">{row.video_id}</span>
    ),
    sortable: true,
    sortValue: (row) => row.video_id,
  },
  {
    key: "discovery",
    header: "Source",
    cell: (row) => {
      const disc = getDiscovery(row);
      if (!disc || disc.kind !== "recommendation") return <span className="text-xs text-muted-foreground">collected</span>;
      return (
        <Link
          href={`/videos/${disc.source_video_id}`}
          className="inline-flex items-center gap-1 text-xs"
          title={`Recommended by ${disc.source_video_id}`}
        >
          <Badge variant="outline" className="text-xs">recommended</Badge>
          <span className="font-mono text-[10px] text-muted-foreground truncate max-w-[120px]">
            {disc.source_video_id}
          </span>
        </Link>
      );
    },
    sortable: false,
  },
  {
    key: "published",
    header: "Published",
    cell: (row) => (
      <span className="text-xs">{formatDate(row.upload_date)}</span>
    ),
    sortable: true,
    sortValue: (row) => row.upload_date ?? "",
  },
  {
    key: "duration",
    header: "Duration",
    cell: (row) => (
      <span className="text-xs font-mono">{formatDuration(row.duration)}</span>
    ),
    sortable: true,
    sortValue: (row) => row.duration ?? 0,
  },
  {
    key: "format",
    header: "Format",
    cell: (row) => {
      const format = getVideoFormat(row);
      const variant =
        format === "Short"
          ? "secondary"
          : format === "Live"
          ? "destructive"
          : "default";
      return <Badge variant={variant} className="text-xs">{format}</Badge>;
    },
    sortable: true,
    sortValue: (row) => getVideoFormat(row),
  },
  {
    key: "tags",
    header: "Tags",
    cell: (row) => (
      <span className="text-xs text-muted-foreground max-w-[200px] truncate block">
        {formatTags(row.tags)}
      </span>
    ),
  },
];

export function RunVideosBrowser({ runId }: { runId: string }) {
  const query = useRunVideos(runId);

  if (query.isLoading) {
    return <LoadingState label="Loading videos…" />;
  }

  if (query.isError) {
    return (
      <ErrorState
        message="Failed to load videos"
        detail={query.error instanceof Error ? query.error.message : String(query.error)}
        retry={() => query.refetch()}
      />
    );
  }

  const videos = query.data ?? [];

  if (videos.length === 0) {
    return <EmptyState title="No videos found" description="This run has no collected videos." />;
  }

  return (
    <DataTable
      columns={COLUMNS}
      rows={videos}
      getRowKey={(row) => row.video_id}
      emptyTitle="No videos"
      emptyDescription="This run has no collected videos."
      initialSortKey="published"
      initialSortDirection="desc"
      ariaLabel="Videos collected in this run"
    />
  );
}