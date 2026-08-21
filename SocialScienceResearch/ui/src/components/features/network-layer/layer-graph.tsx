"use client";

import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/features/state";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import { useLayerGraph } from "@/services/networkLayer";
import { useScrapeNetwork } from "@/services/networkFull";
import type {
  ChannelGraphPayload,
  LayerProjection,
} from "@/lib/network-layer-types";
import type { NetworkGraphPayload } from "@/lib/network-full-types";

function mapVideoPayload(payload: NetworkGraphPayload): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  return {
    nodes: payload.nodes.map((n): GraphNode => ({
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
    })),
    links: payload.edges.map((e): GraphLink => ({
      source: e.source,
      target: e.target,
      position: e.position,
      run_id: e.run_id,
      run_type: e.run_type,
      run_name: e.run_name,
      title: e.title,
    })),
  };
}

function mapChannelPayload(payload: ChannelGraphPayload): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  return {
    nodes: payload.nodes.map((node): GraphNode => ({
      id: node.channel_id,
      title: node.channel_name ?? node.channel_id,
      channel: node.channel_name ?? node.channel_id,
      channel_id: node.channel_id,
      thumbnail: node.avatar_url,
      views: node.subscriber_count,
      kind:
        node.in_degree > 0 && node.out_degree > 0
          ? "both"
          : node.out_degree > 0
            ? "source"
            : node.in_degree > 0
              ? "target"
              : "other",
      in_degree: node.in_degree,
      out_degree: node.out_degree,
      run_ids: node.run_ids,
      run_types: node.run_types,
    })),
    links: payload.edges.map((edge): GraphLink => ({
      source: edge.source,
      target: edge.target,
      title: `${edge.video_edge_count} video edge(s)`,
    })),
  };
}

export function LayerGraph({
  layerRunId,
  projection,
  onProjectionChange,
  highlightVideoIds,
}: {
  layerRunId: string | null;
  projection: LayerProjection;
  onProjectionChange: (projection: LayerProjection) => void;
  highlightVideoIds: string[] | null;
}) {
  const graphQuery = useLayerGraph(layerRunId, projection);
  const scrapeMutation = useScrapeNetwork("video");

  const mapped = useMemo(() => {
    if (!graphQuery.data) return null;
    const payload = graphQuery.data as NetworkGraphPayload | ChannelGraphPayload;
    return projection === "channel"
      ? mapChannelPayload(payload as ChannelGraphPayload)
      : mapVideoPayload(payload as NetworkGraphPayload);
  }, [graphQuery.data, projection]);

  const visible = useMemo(() => {
    if (!mapped) return null;
    if (!highlightVideoIds || projection !== "video") {
      return mapped;
    }
    const wanted = new Set(highlightVideoIds);
    const nodes = mapped.nodes.filter((node) => wanted.has(node.id));
    const wantedIds = new Set(nodes.map((node) => node.id));
    const links = mapped.links.filter(
      (link) => wantedIds.has(link.source) && wantedIds.has(link.target),
    );
    return { nodes, links };
  }, [mapped, highlightVideoIds, projection]);

  if (!layerRunId) return null;

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">Layer {projection} graph</h3>
        <div className="flex items-center gap-1 rounded-lg bg-muted p-0.5">
          <button
            type="button"
            aria-pressed={projection === "video"}
            onClick={() => onProjectionChange("video")}
            className="rounded-md px-2.5 py-1 text-xs font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-background aria-pressed:text-foreground aria-pressed:shadow-sm"
          >
            Video graph
          </button>
          <button
            type="button"
            aria-pressed={projection === "channel"}
            onClick={() => onProjectionChange("channel")}
            className="rounded-md px-2.5 py-1 text-xs font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-background aria-pressed:text-foreground aria-pressed:shadow-sm"
          >
            Channel graph
          </button>
        </div>
      </div>

      {graphQuery.isError ? (
        <ErrorState
          message={
            graphQuery.error instanceof Error
              ? graphQuery.error.message
              : "Failed to load layer graph"
          }
          retry={() => graphQuery.refetch()}
        />
      ) : graphQuery.data && visible ? (
        <NetworkGraph
          nodes={visible.nodes}
          links={visible.links}
          runs={graphQuery.data.runs}
          channels={graphQuery.data.channels}
          onScrapeClick={
            projection === "video"
              ? (videoId) => scrapeMutation.mutateAsync({ video_id: videoId }).then(() => undefined)
              : undefined
          }
        />
      ) : (
        <LoadingState label="Loading layer graph…" />
      )}
    </Card>
  );
}
