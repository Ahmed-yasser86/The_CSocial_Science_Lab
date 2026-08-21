"use client";

import Link from "next/link";
import { Share2, CircleOff } from "lucide-react";
import type { RecommendationEdge } from "@/lib/types";
import { useVideoRecommendations } from "@/services/queries";
import { DataTable, type Column } from "@/components/features/data-table";
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/features/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function RecommendationsExplorer({ videoId }: { videoId: string }) {
  const edgesQuery = useVideoRecommendations(videoId);

  const columns: Column<RecommendationEdge>[] = [
    {
      key: "position",
      header: "Position",
      sortable: true,
      sortValue: (e) => e.position,
      cell: (e) =>
        e.position === null || e.position === undefined ? "—" : `#${e.position + 1}`,
      className: "text-right tabular-nums",
    },
    {
      key: "recommended_video_id",
      header: "Recommended video",
      sortable: true,
      sortValue: (e) => e.recommended_video_id,
      cell: (e) => (
        <Link
          href={`/videos/${e.recommended_video_id}`}
          className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        >
          {e.recommended_video_id}
        </Link>
      ),
    },
    {
      key: "title",
      header: "Title",
      sortable: true,
      sortValue: (e) => e.title ?? "",
      cell: (e) => <span className="line-clamp-1 max-w-md">{e.title ?? "—"}</span>,
    },
    {
      key: "collection_run_id",
      header: "Observed in run",
      sortable: true,
      sortValue: (e) => e.collection_run_id,
      cell: (e) => (
        <Link
          href={`/runs/${e.collection_run_id}`}
          className="font-mono text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {e.collection_run_id}
        </Link>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (e) => e.status,
      cell: (e) => <Badge variant="outline">{e.status}</Badge>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Observed recommendation edges from this source video, ranked by their
          position in the “Up Next” feed (#1 first) and attributed to the run
          that recorded them.
        </p>
        <Button
          render={<Link href={`/network/videos/${videoId}`} />}
          nativeButton={false}
          variant="outline"
          size="sm"
        >
          <Share2 className="size-3.5" aria-hidden />
          Ego-network context
        </Button>
      </div>

      {edgesQuery.isLoading ? (
        <LoadingState label="Loading recommendations…" />
      ) : edgesQuery.isError ? (
        <ErrorState message={(edgesQuery.error as Error).message} />
      ) : edgesQuery.data && edgesQuery.data.length > 0 ? (
        <DataTable
          columns={columns}
          rows={edgesQuery.data}
          getRowKey={(e) => e.observation_id}
          initialSortKey="position"
          ariaLabel="Recommendations observed for this video"
        />
      ) : (
        <EmptyState
          icon={CircleOff}
          title="No observed recommendations"
          description="No recommendation edges have been recorded for this video. Recommendation observation uses a layered provider strategy (library fields, the INNERTUBE /next endpoint, and watch-page dumps) and records an explicit unsupported error only when every provider returns nothing. You can still analyze the network from any edges recorded for other videos."
        />
      )}
    </div>
  );
}
