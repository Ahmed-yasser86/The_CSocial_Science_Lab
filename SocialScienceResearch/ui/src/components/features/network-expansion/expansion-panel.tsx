"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import {
  useExpansions,
  useExpansionStats,
  useExpansionGraph,
} from "@/services/networkExpansion";
import { formatNumber } from "@/lib/format";
import type { ExpansionGraphPayload } from "@/lib/network-expansion-types";

export function ExpansionPanel({
  selectedActionId,
  onSelectAction,
}: {
  selectedActionId: string | null;
  onSelectAction: (actionId: string) => void;
}) {
  const expansionsQuery = useExpansions();
  const [projection, setProjection] = useState<"video" | "channel">("video");

  const actions = expansionsQuery.data ?? [];
  const effectiveActionId =
    selectedActionId && actions.some((a) => a.action_id === selectedActionId)
      ? selectedActionId
      : (actions[0]?.action_id ?? null);

  const statsQuery = useExpansionStats(effectiveActionId);
  const graphQuery = useExpansionGraph(effectiveActionId, projection);

  if (expansionsQuery.isError) {
    return (
      <ErrorState
        message={
          expansionsQuery.error instanceof Error
            ? expansionsQuery.error.message
            : "Failed to load expansion actions"
        }
        retry={() => expansionsQuery.refetch()}
      />
    );
  }

  if (expansionsQuery.isLoading) {
    return <LoadingState label="Loading expansion actions…" />;
  }

  if (actions.length === 0) {
    return (
      <EmptyState
        title="No expansion actions yet"
        description="Scrape recommendations (per video or for the whole slice) to build the network graph one hop at a time."
        className="min-h-48 p-6"
      />
    );
  }

  const stats = statsQuery.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={effectiveActionId ?? ""}
          onValueChange={(value) => {
            if (value) onSelectAction(value);
          }}
          items={actions.map((a) => ({
            value: a.action_id,
            label: `${a.kind === "video" ? "Video" : "All"} · ${formatTimestamp(a.started_at)}`,
          }))}
        >
          <SelectTrigger className="w-72" aria-label="Select expansion action">
            <SelectValue placeholder="Select expansion action" />
          </SelectTrigger>
          <SelectContent>
            {actions.map((a) => (
              <SelectItem key={a.action_id} value={a.action_id}>
                {a.kind === "video" ? "Video" : "All"} ·{" "}
                {formatTimestamp(a.started_at)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={projection}
          onValueChange={(value) => setProjection(value as "video" | "channel")}
          items={[
            { value: "video", label: "Video graph" },
            { value: "channel", label: "Channel graph" },
          ]}
        >
          <SelectTrigger className="w-44" aria-label="Expansion graph projection">
            <SelectValue placeholder="Projection" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="video">Video graph</SelectItem>
            <SelectItem value="channel">Channel graph</SelectItem>
          </SelectContent>
        </Select>

        {stats?.action.project_id ? (
          <a
            href={`/projects/${stats.action.project_id}`}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <ExternalLink className="size-3.5" aria-hidden />
            Open auto-project
          </a>
        ) : null}
      </div>

      {statsQuery.isError ? (
        <ErrorState
          message={
            statsQuery.error instanceof Error
              ? statsQuery.error.message
              : "Failed to load expansion stats"
          }
          retry={() => statsQuery.refetch()}
        />
      ) : stats ? (
        <>
          <div
            className="grid grid-cols-2 gap-4 md:grid-cols-4"
            role="group"
            aria-label="Expansion overall stats"
          >
            <Tile label="Nodes" value={formatNumber(stats.overall.node_count)} />
            <Tile label="Edges" value={formatNumber(stats.overall.edge_count)} />
            <Tile label="Channels" value={formatNumber(stats.overall.channel_count)} />
            <Tile label="Sources" value={formatNumber(stats.overall.source_count)} />
            <Tile
              label="Components"
              value={formatNumber(stats.overall.component_count)}
            />
            <Tile
              label="Avg out-degree"
              value={
                stats.overall.avg_out_degree === null ||
                stats.overall.avg_out_degree === undefined
                  ? "—"
                  : formatNumber(stats.overall.avg_out_degree)
              }
            />
            <Tile
              label="Density"
              value={
                stats.overall.density === null || stats.overall.density === undefined
                  ? "—"
                  : formatNumber(stats.overall.density)
              }
            />
            <Tile
              label="Comments"
              value={formatNumber(stats.overall.comment_count)}
            />
          </div>

          <Card className="p-4">
            <h3 className="mb-2 text-sm font-medium">Per-video stats</h3>
            {stats.videos.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No source videos in this action.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Video</TableHead>
                      <TableHead>Channel</TableHead>
                      <TableHead className="text-right">Recs</TableHead>
                      <TableHead className="text-right">In</TableHead>
                      <TableHead className="text-right">New targets</TableHead>
                      <TableHead className="text-right">New channels</TableHead>
                      <TableHead className="text-right">New edges</TableHead>
                      <TableHead className="text-right">Comments</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stats.videos.map((row) => (
                      <TableRow key={row.video_id}>
                        <TableCell>
                          <span className="font-mono text-xs">{row.video_id}</span>
                          {row.title ? (
                            <span className="ml-2 text-muted-foreground">
                              {row.title}
                            </span>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          {row.channel_name ?? row.channel_id ?? "—"}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.recommendation_count}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.in_degree}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.new_targets}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.new_channels}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.new_edges}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.comments_collected}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Card>

          <Card className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-medium">Action graph</h3>
              <Badge variant="outline">{projection}</Badge>
            </div>
            {graphQuery.isLoading ? (
              <LoadingState label="Loading action graph…" />
            ) : graphQuery.data ? (
              <ExpansionGraphView
                payload={graphQuery.data}
                projection={projection}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                No graph data for this action.
              </p>
            )}
          </Card>
        </>
      ) : (
        <LoadingState label="Loading expansion stats…" />
      )}
    </div>
  );
}

function ExpansionGraphView({
  payload,
  projection,
}: {
  payload: ExpansionGraphPayload;
  projection: "video" | "channel";
}) {
  if (projection === "channel") {
    const channelNodes = (payload as unknown as {
      nodes: { channel_id: string; channel_name?: string | null }[];
    }).nodes;
    const channelEdges = (payload as unknown as {
      edges: { source: string; target: string; video_edge_count: number }[];
    }).edges;
    return (
      <p className="text-sm text-muted-foreground">
        {channelNodes.length} channel node(s), {channelEdges.length} aggregated
        edge(s). Switch to the video graph for the full interactive view.
      </p>
    );
  }

  const graphNodes: GraphNode[] = (payload.nodes as unknown[]).map((n) => {
    const node = n as {
      video_id: string;
      title?: string | null;
      channel_id?: string | null;
      channel_name?: string | null;
      thumbnail_url?: string | null;
      views?: number | null;
      likes?: number | null;
      duration?: number | null;
      kind: GraphNode["kind"];
      in_degree: number;
      out_degree: number;
      run_ids?: string[];
      run_types?: string[];
    };
    return {
      id: node.video_id,
      title: node.title,
      channel: node.channel_name ?? node.channel_id,
      channel_id: node.channel_id,
      thumbnail: node.thumbnail_url,
      views: node.views,
      likes: node.likes,
      duration: node.duration,
      kind: node.kind,
      in_degree: node.in_degree,
      out_degree: node.out_degree,
      run_ids: node.run_ids,
      run_types: node.run_types,
    };
  });

  const graphLinks: GraphLink[] = (payload.edges as unknown[]).map((e) => {
    const edge = e as {
      source: string;
      target: string;
      position?: number | null;
      run_id?: string | null;
      run_type?: string | null;
      run_name?: string | null;
      title?: string | null;
    };
    return {
      source: edge.source,
      target: edge.target,
      position: edge.position,
      run_id: edge.run_id,
      run_type: edge.run_type,
      run_name: edge.run_name,
      title: edge.title,
    };
  });

  return (
    <NetworkGraph
      nodes={graphNodes}
      links={graphLinks}
      runs={payload.runs}
      channels={payload.channels}
    />
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

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}
