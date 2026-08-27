"use client";

import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import {
  NetworkGraph,
  type GraphLink,
  type GraphNode,
} from "@/components/features/network-graph";
import {
  getCommenterNetworkExportUrl,
  useCommenterNetworkGraph,
  useCommenterNetworkMetrics,
} from "@/services/networkFull";
import {
  EXPORT_FORMATS,
  type CommenterProjection,
} from "@/lib/network-full-types";

const CO_COMMENT_WEIGHTS: { value: string; label: string }[] = [
  { value: "co_comment:jaccard", label: "Jaccard" },
  { value: "co_comment:overlap_coefficient", label: "Overlap coefficient" },
  { value: "co_comment:intersection", label: "Intersection" },
  { value: "co_comment:counts", label: "Counts" },
];

const PROJECTIONS: { value: CommenterProjection; label: string }[] = [
  { value: "commenter", label: "Commenter co-comment" },
  { value: "co_comment_video", label: "Commenters × videos" },
  { value: "co_comment_channel", label: "Commenters × channels" },
  { value: "heterogeneous", label: "Heterogeneous (all kinds)" },
];

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg">{value}</div>
    </div>
  );
}

export function AudienceNetworkView({ runId }: { runId: string | null }) {
  const [tab, setTab] = useState<"graph" | "metrics">("graph");
  const [projection, setProjection] = useState<CommenterProjection>("commenter");
  const [weight, setWeight] = useState<string>("co_comment:jaccard");
  const [minShared, setMinShared] = useState<number>(2);
  const [topN, setTopN] = useState<number>(200);
  const [weighted, setWeighted] = useState<boolean>(true);

  const graphQuery = useCommenterNetworkGraph({
    runId,
    projection,
    weight,
    minShared,
    topN,
    weighted,
    enabled: !!runId,
  });
  const metricsQuery = useCommenterNetworkMetrics({
    runId,
    projection,
    weight,
    minShared,
    topN,
    weighted,
    enabled: !!runId,
  });

  const graphNodes = useMemo<GraphNode[]>(() => {
    if (!graphQuery.data) return [];
    return graphQuery.data.nodes.map((n) => ({
      id: n.id,
      title: n.label ?? n.id,
      kind: n.kind,
      in_degree: n.degree,
      out_degree: 0,
      community_id: n.community_id ?? null,
    }));
  }, [graphQuery.data]);

  const graphLinks = useMemo<GraphLink[]>(() => {
    if (!graphQuery.data) return [];
    return graphQuery.data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
    }));
  }, [graphQuery.data]);

  if (!runId) {
    return (
      <Card className="p-4">
        <EmptyState
          title="Select a collection run"
          description="Choose a collection run from the Scope picker above to build the audience (commenter) network for that slice."
          className="min-h-32"
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Projection
            </Label>
            <Select
              value={projection}
              onValueChange={(v) => setProjection(v as CommenterProjection)}
              items={PROJECTIONS}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Weight
            </Label>
            <Select
              value={weight}
              onValueChange={(v) => setWeight((v as string) ?? "co_comment:jaccard")}
              items={CO_COMMENT_WEIGHTS}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Min shared
            </Label>
            <Input
              type="number"
              min={1}
              max={100}
              value={minShared}
              onChange={(e) =>
                setMinShared(Math.max(1, Number(e.target.value) || 1))
              }
              className="w-24"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Top N nodes
            </Label>
            <Input
              type="number"
              min={10}
              max={1000}
              value={topN}
              onChange={(e) =>
                setTopN(Math.min(1000, Math.max(10, Number(e.target.value) || 10))
              )}
              className="w-24"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={weighted}
              onCheckedChange={(c) => setWeighted(c === true)}
            />
            Weighted
          </label>
          <div className="flex items-center gap-1.5">
            {EXPORT_FORMATS.map((format) => (
              <a
                key={format}
                href={getCommenterNetworkExportUrl({
                  runId,
                  projection,
                  weight,
                  minShared,
                  topN,
                  weighted,
                  format,
                })}
                download
                className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <Download className="size-3.5" aria-hidden />
                {format}
              </a>
            ))}
          </div>
        </div>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList>
          <TabsTrigger value="graph">Graph</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="graph" className="mt-4 space-y-4">
          <Card className="p-4">
            {graphQuery.isError ? (
              <ErrorState
                message={
                  graphQuery.error instanceof Error
                    ? graphQuery.error.message
                    : "Failed to load audience network"
                }
                retry={() => graphQuery.refetch()}
              />
            ) : !graphQuery.data ? (
              <LoadingState label="Building audience network…" />
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">
                    {graphQuery.data.node_count} nodes
                  </Badge>
                  <Badge variant="outline">
                    {graphQuery.data.edge_count} edges
                  </Badge>
                  <Badge variant="outline">
                    {graphQuery.data.community_count} communities
                  </Badge>
                  {graphQuery.data.modularity != null ? (
                    <Badge variant="outline">
                      Q={graphQuery.data.modularity.toFixed(3)}
                    </Badge>
                  ) : null}
                </div>
                <NetworkGraph
                  nodes={graphNodes}
                  links={graphLinks}
                  height={620}
                  colorMode="community"
                />
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  {(["commenter", "video", "channel"] as const).map((k) => (
                    <span key={k} className="inline-flex items-center gap-1.5">
                      <span className="inline-block size-2.5 rounded-full bg-border" />
                      {k}
                    </span>
                  ))}
                </div>
              </>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="mt-4 space-y-4">
          <Card className="p-4">
            {metricsQuery.isError ? (
              <ErrorState
                message={
                  metricsQuery.error instanceof Error
                    ? metricsQuery.error.message
                    : "Failed to load audience metrics"
                }
                retry={() => metricsQuery.refetch()}
              />
            ) : !metricsQuery.data ? (
              <LoadingState label="Computing audience metrics…" />
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  <Stat label="Nodes" value={metricsQuery.data.node_count} />
                  <Stat label="Edges" value={metricsQuery.data.edge_count} />
                  <Stat
                    label="Density"
                    value={metricsQuery.data.density.toFixed(4)}
                  />
                  <Stat
                    label="Communities"
                    value={metricsQuery.data.community_count}
                  />
                  <Stat
                    label="Modularity"
                    value={
                      metricsQuery.data.modularity != null
                        ? metricsQuery.data.modularity.toFixed(3)
                        : "—"
                    }
                  />
                  <Stat
                    label="Components"
                    value={metricsQuery.data.weakly_connected_components}
                  />
                  <Stat
                    label="Avg clustering"
                    value={metricsQuery.data.avg_clustering.toFixed(3)}
                  />
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
                  <RankingList
                    title="Top bridges"
                    rows={metricsQuery.data.top_bridges}
                  />
                  <RankingList
                    title="Top core"
                    rows={metricsQuery.data.top_core}
                  />
                  <RankingList
                    title="Top prolific"
                    rows={metricsQuery.data.top_prolific}
                  />
                </div>
              </>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RankingList({
  title,
  rows,
}: {
  title: string;
  rows: { id: string; label?: string | null; betweenness: number }[];
}) {
  return (
    <div className="rounded-md border border-border p-3">
      <h4 className="mb-2 text-sm font-medium">{title}</h4>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No nodes ranked.</p>
      ) : (
        <ol className="space-y-1 text-sm">
          {rows.map((r, i) => (
            <li
              key={r.id}
              className="flex items-center justify-between gap-2 font-mono text-xs"
            >
              <span className="truncate">
                {i + 1}. {r.label ?? r.id}
              </span>
              <span className="text-muted-foreground">
                {r.betweenness.toFixed(3)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
