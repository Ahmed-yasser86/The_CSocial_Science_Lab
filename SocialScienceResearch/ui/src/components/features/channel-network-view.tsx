"use client";

import { useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingState } from "@/components/features/state";
import { useRuns } from "@/services/queries";
import {
  useNetworkGraph,
  useScrapeNetwork,
} from "@/services/networkFull";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles } from "lucide-react";
import type {
  ChannelGraphPayload,
  GraphProjection,
  NetworkGraphPayload,
} from "@/lib/network-full-types";
import { Toast } from "@/components/features/state";

function mapGraphPayload(payload: NetworkGraphPayload): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  return {
    nodes: payload.nodes.map(
      (n): GraphNode => ({
        id: n.video_id,
        title: n.title,
        channel: n.channel_name ?? n.channel_id,
        channel_id: n.channel_id,
        thumbnail: n.thumbnail_url,
        views: n.views,
        likes: n.likes,
        duration: n.duration,
        kind: n.kind,
        in_degree: n.in_degree,
        out_degree: n.out_degree,
        run_ids: n.run_ids,
        run_types: n.run_types,
        community_id: n.community_id,
      }),
    ),
    links: payload.edges.map(
      (e): GraphLink => ({
        source: e.source,
        target: e.target,
        position: e.position,
        run_id: e.run_id,
        run_type: e.run_type,
        run_name: e.run_name,
        title: e.title,
      }),
    ),
  };
}

function mapChannelGraphPayload(payload: ChannelGraphPayload): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  return {
    nodes: payload.nodes.map(
      (n): GraphNode => {
        const kind: GraphNode["kind"] =
          n.out_degree > 0 && n.in_degree > 0
            ? "both"
            : n.out_degree > 0
              ? "source"
              : n.in_degree > 0
                ? "target"
                : "other";
        return {
          id: n.channel_id,
          title: n.channel_name,
          channel: n.channel_name,
          channel_id: n.channel_id,
          thumbnail: n.avatar_url,
          views: n.subscriber_count,
          likes: null,
          duration: null,
          kind,
          in_degree: n.in_degree,
          out_degree: n.out_degree,
          run_ids: n.run_ids,
          run_types: n.run_types,
        };
      },
    ),
    links: payload.edges.map(
      (e): GraphLink => ({
        source: e.source,
        target: e.target,
        run_id: e.run_ids?.[0] ?? null,
        run_type: null,
        run_name: null,
        title: `${e.video_edge_count} video edge${e.video_edge_count === 1 ? "" : "s"}`,
      }),
    ),
  };
}

export function ChannelNetworkView({ channelId }: { channelId: string }) {
  const runsQuery = useRuns();
  const [runId, setRunId] = useState<string | null>(null);
  const [projection, setProjection] = useState<GraphProjection>("channel");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const graphQuery = useNetworkGraph(
    runId ?? undefined,
    [channelId],
    undefined,
    "either",
    projection,
    { retry: 1 },
  );

  const scrapeMutation = useScrapeNetwork("channel");

  const runs = useMemo(() => {
    const data = (runsQuery.data ?? []).slice();
    data.sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
    return [...new Set(data.map((r) => r.run_id))];
  }, [runsQuery.data]);

  const runNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const run of runsQuery.data ?? []) {
      if (run.name && !names.has(run.run_id)) names.set(run.run_id, run.name);
    }
    return names;
  }, [runsQuery.data]);

  function showToast(message: string, type: "success" | "error") {
    setToast({ message, type });
    setTimeout(() => setToast(null), type === "success" ? 3000 : 5000);
  }

  const handleScrape = async () => {
    try {
      await scrapeMutation.mutateAsync({ channel_id: channelId, dedupe: true });
      showToast(`Scrape queued for channel ${channelId}`, "success");
    } catch (err) {
      showToast(`Failed to start scrape: ${(err as Error).message}`, "error");
    }
  };

  const payload = graphQuery.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="space-y-1">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Projection
          </Label>
          <Select
            value={projection}
            onValueChange={(v) => setProjection(v as GraphProjection)}
          >
            <SelectTrigger className="w-48" aria-label="Select graph projection">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="channel">Channel graph</SelectItem>
              <SelectItem value="video">Video graph</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Run slice
          </Label>
          <Select
            value={runId ?? ""}
            onValueChange={(v) => setRunId(v || null)}
          >
            <SelectTrigger className="w-64" aria-label="Filter by run">
              <SelectValue placeholder="All runs" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All runs</SelectItem>
              {runs.map((id) => (
                <SelectItem key={id} value={id}>
                  {runNames.get(id) ?? id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-5"
          onClick={() => void handleScrape()}
          disabled={scrapeMutation.isPending || scrapeMutation.isRunning}
        >
          {scrapeMutation.isRunning ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Sparkles aria-hidden />
          )}
          Re-scrape this channel
        </Button>
        {payload && "unattributed_edges" in payload ? (
          <Badge variant="outline" className="mt-5">
            {(payload as ChannelGraphPayload).unattributed_edges > 0
              ? `${(payload as ChannelGraphPayload).unattributed_edges} edges without channel attribution`
              : "All edges attributed"}
          </Badge>
        ) : null}
      </div>

      {graphQuery.isError ? (
        <ErrorState
          message={
            graphQuery.error instanceof Error
              ? graphQuery.error.message
              : "Failed to load channel network"
          }
          retry={() => graphQuery.refetch()}
        />
      ) : graphQuery.data ? (
        projection === "channel" ? (
          <NetworkGraph
            nodes={mapChannelGraphPayload(graphQuery.data as ChannelGraphPayload).nodes}
            links={mapChannelGraphPayload(graphQuery.data as ChannelGraphPayload).links}
            runs={graphQuery.data.runs}
            channels={graphQuery.data.channels}
            selectedRun={runId ?? undefined}
            onRunChange={(v) => setRunId(v === "__all" ? null : v)}
            onClearFilters={() => setRunId(null)}
          />
        ) : (
          <NetworkGraph
            nodes={mapGraphPayload(graphQuery.data as NetworkGraphPayload).nodes}
            links={mapGraphPayload(graphQuery.data as NetworkGraphPayload).links}
            runs={graphQuery.data.runs}
            channels={graphQuery.data.channels}
            selectedRun={runId ?? undefined}
            onRunChange={(v) => setRunId(v === "__all" ? null : v)}
            onClearFilters={() => setRunId(null)}
          />
        )
      ) : (
        <LoadingState label="Loading channel network…" />
      )}

      {scrapeMutation.jobId ? (
        <JobProgressCard
          key={scrapeMutation.jobId}
          jobId={scrapeMutation.jobId}
          title="Scraping channel"
        />
      ) : null}

      {toast && (
        <div className="fixed bottom-4 right-4 z-50 animate-slide-in">
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        </div>
      )}
    </div>
  );
}
