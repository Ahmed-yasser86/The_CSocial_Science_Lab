"use client";

import { useCallback, useMemo, useState } from "react";
import { Download, Info } from "lucide-react";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import {
  NetworkGraph,
  CommenterDetailDrawer,
  communityColorFor,
  type GraphLink,
  type GraphNode,
} from "@/components/features/network-graph";
import {
  Drawer,
  DrawerContent,
} from "@/components/ui/drawer";
import { CommunityHighlightControls } from "@/components/features/network-full/community-highlight-controls";
import {
  getCommenterDetail,
  getCommenterNetworkExportUrl,
  useCommenterNetworkGraph,
  useCommenterNetworkMetrics,
} from "@/services/networkFull";
import {
  CommenterCommunityInsightsPanel,
  CommenterRolesPanel,
} from "@/components/features/network-full/roles-community-panels";
import { ReproducibilityFooter } from "@/components/features/network-full/reproducibility-footer";
import {
  EXPORT_FORMATS,
  type CommenterDetail,
  type CommenterNetworkMetrics,
  type CommenterProjection,
  type CommunityEntity,
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

export function AudienceNetworkView({
  runId,
  jobIds,
}: {
  runId: string | null;
  jobIds?: string[] | null;
}) {
  const [tab, setTab] = useState<"graph" | "metrics">("graph");
  const [projection, setProjection] = useState<CommenterProjection>("commenter");
  const [weight, setWeight] = useState<string>("co_comment:jaccard");
  const [minShared, setMinShared] = useState<number>(2);
  const [topN, setTopN] = useState<number>(200);
  const [maxCandidates, setMaxCandidates] = useState<number>(2000);
  const [weighted, setWeighted] = useState<boolean>(true);

  const hasScope = !!runId || !!(jobIds && jobIds.length > 0);

  // Controlled node inspector so ranking rows can open a commenter's detail
  // drawer from outside the graph canvas.
  const [inspectNodeId, setInspectNodeId] = useState<string | null>(null);

  const loadCommenterDetail = useCallback(
    (handle: string): Promise<CommenterDetail> =>
      getCommenterDetail(handle, {
        runId,
        jobIds: jobIds ?? undefined,
        projection,
        weight,
        weighted,
      }),
    [runId, jobIds, projection, weight, weighted],
  );

  const graphQuery = useCommenterNetworkGraph({
    runId,
    jobIds,
    projection,
    weight,
    minShared,
    topN,
    maxCandidates,
    weighted,
    enabled: hasScope,
  });
  const metricsQuery = useCommenterNetworkMetrics({
    runId,
    jobIds,
    projection,
    weight,
    minShared,
    topN,
    maxCandidates,
    weighted,
    enabled: hasScope,
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

  // N4: derive communities client-side from the fetched audience graph so any
  // community can be isolated as a highlighted sub-graph.
  const [highlightedCommunityId, setHighlightedCommunityId] = useState<string | null>(null);
  const audienceCommunities = useMemo<CommunityEntity[]>(() => {
    const byCommunity = new Map<number, string[]>();
    for (const n of graphNodes) {
      if (n.community_id == null) continue;
      const cid = n.community_id;
      if (!byCommunity.has(cid)) byCommunity.set(cid, []);
      byCommunity.get(cid)!.push(n.id);
    }
    return Array.from(byCommunity.entries())
      .sort((a, b) => b[1].length - a[1].length)
      .map(([cid, ids], idx) => ({
        id: String(cid),
        community_id: cid,
        label: `Community ${idx + 1}`,
        size: ids.length,
        node_ids: ids,
        top_node_ids: ids.slice(0, 10),
      }));
  }, [graphNodes]);

  const highlightedNodeIds = useMemo<Set<string> | null>(() => {
    if (!highlightedCommunityId) return null;
    const comm = audienceCommunities.find((c) => c.id === highlightedCommunityId);
    return comm ? new Set(comm.node_ids) : null;
  }, [highlightedCommunityId, audienceCommunities]);

  // N5: reproducibility footer for the current audience slice.
  const audienceWeightSpec = graphQuery.data?.weight_spec ?? null;
  const reproducibilityFooter = graphQuery.data ? (
    <ReproducibilityFooter
      algorithm="networkx"
      seed={42}
      weightSpec={audienceWeightSpec}
      runIds={runId ? [runId] : []}
    />
  ) : null;

  if (!hasScope) {
    return (
      <Card className="p-4">
        <EmptyState
          title="Select a scope"
          description="Choose a collection run (or a collection job) from the Scope picker above to build the audience (commenter) network for that slice."
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
            >
              <SelectTrigger className="w-56" aria-label="Select projection">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROJECTIONS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Weight
              </Label>
              <Popover>
                <PopoverTrigger
                  render={
                    <button
                      type="button"
                      aria-label="What is weight?"
                      className="rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  }
                >
                  <Info className="size-3.5" aria-hidden />
                </PopoverTrigger>
                <PopoverContent className="max-w-xs space-y-2 text-xs leading-relaxed">
                  <p>
                    Nodes are <span className="font-medium">commenters</span>. An
                    edge links two commenters when they co-commented on the same
                    videos or channels.
                  </p>
                  <p>
                    The edge <span className="font-medium">weight</span> scores
                    how similar their commenting behaviour is, by the chosen
                    metric:
                  </p>
                  <ul className="list-disc space-y-1 pl-4">
                    <li>
                      <span className="font-medium">Jaccard</span> — shared ÷
                      union of their videos (0–1).
                    </li>
                    <li>
                      <span className="font-medium">Overlap</span> — shared ÷ the
                      smaller commenter&apos;s video set (0–1).
                    </li>
                    <li>
                      <span className="font-medium">Intersection / Counts</span> —
                      raw number of shared videos.
                    </li>
                  </ul>
                  <p>
                    The <span className="font-medium">Weighted</span> toggle
                    decides whether those strengths feed the centrality / role /
                    community math (ON) or every link counts equally (OFF).
                  </p>
                </PopoverContent>
              </Popover>
            </div>
            <Select
              value={weight}
              onValueChange={(v) => setWeight((v as string) ?? "co_comment:jaccard")}
            >
              <SelectTrigger className="w-56" aria-label="Select weight metric">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CO_COMMENT_WEIGHTS.map((w) => (
                  <SelectItem key={w.value} value={w.value}>
                    {w.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Min shared
              </Label>
              <Popover>
                <PopoverTrigger
                  render={
                    <button
                      type="button"
                      aria-label="What is min shared?"
                      className="rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  }
                >
                  <Info className="size-3.5" aria-hidden />
                </PopoverTrigger>
                <PopoverContent className="max-w-xs space-y-2 text-xs leading-relaxed">
                  <p>
                    Only commenter pairs that co-commented on at least this many
                    shared videos become linked. A pair with fewer shared videos
                    is dropped, so weak one-off overlaps don&apos;t create edges.
                  </p>
                  <p>
                    Higher values keep only the strongest, most consistent
                    co-comment relationships; lower values let looser overlaps
                    through.
                  </p>
                </PopoverContent>
              </Popover>
            </div>
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
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Max candidates
              </Label>
              <Info className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <Input
              type="number"
              min={100}
              max={50000}
              value={maxCandidates}
              onChange={(e) =>
                setMaxCandidates(
                  Math.min(50000, Math.max(100, Number(e.target.value) || 100)),
                )
              }
              className="w-28"
            />
            <p className="text-[11px] leading-tight text-muted-foreground">
              Cap on commenters scanned for co-comment edges. Higher = more
              complete graph, but a longer compute time (larger runs may time out).
            </p>
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
          <TabsTrigger value="roles">Roles</TabsTrigger>
          <TabsTrigger value="communities">Communities</TabsTrigger>
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
                  {(() => {
                    const q = graphQuery.data.modularity;
                    if (q == null) return null;
                    return (
                      <>
                        <Badge variant="outline">Q={q.toFixed(3)}</Badge>
                        <Popover>
                          <PopoverTrigger
                            render={
                              <button
                                type="button"
                                aria-label="What is Q (modularity)?"
                                className="rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                              />
                            }
                          >
                            <Info className="size-3.5" aria-hidden />
                          </PopoverTrigger>
                          <PopoverContent className="max-w-xs space-y-2 text-xs leading-relaxed">
                            <p>
                              <span className="font-medium">Q (modularity)</span>{" "}
                              scores how strongly the network splits into separate
                              communities.
                            </p>
                            <p>
                              Roughly −0.5 to 1: 0 means no better than random;
                              higher means nodes connect far more within their
                              community than by chance.
                            </p>
                            <p>
                              <span className="font-medium">Q={q.toFixed(3)}</span>{" "}
                              here is very high — the commenter groups are tightly
                              and cleanly separated. Above ~0.3 signals clear
                              structure; above 0.7 is unusually strong.
                            </p>
                          </PopoverContent>
                        </Popover>
                      </>
                    );
                  })()}
                </div>
                <NetworkGraph
                  nodes={graphNodes}
                  links={graphLinks}
                  height={620}
                  colorMode="community"
                  highlightedNodeIds={highlightedNodeIds}
                  loadCommenterDetail={loadCommenterDetail}
                  inspectNodeId={inspectNodeId}
                  onInspectNodeChange={setInspectNodeId}
                  weighted={weighted}
                />
                {audienceCommunities.length > 0 ? (
                  <div className="mt-3">
                    <CommunityHighlightControls
                      communities={audienceCommunities}
                      selectedId={highlightedCommunityId}
                      onSelect={setHighlightedCommunityId}
                    />
                  </div>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  {audienceCommunities.length > 0 ? (
                    audienceCommunities.map((c) => (
                      <span
                        key={c.id}
                        className="inline-flex items-center gap-1.5"
                      >
                        <span
                          className="inline-block size-2.5 rounded-full"
                          style={{ backgroundColor: communityColorFor(c.community_id) }}
                        />
                        {c.label}
                      </span>
                    ))
                  ) : (
                    <span>No community coloring</span>
                  )}
                </div>
                {reproducibilityFooter}
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

                <div className="mt-4 flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    Click a handle to inspect that commenter.
                  </p>
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() =>
                      exportRankingsCsv(metricsQuery.data)
                    }
                  >
                    <Download className="size-3.5" aria-hidden />
                    Export CSV
                  </Button>
                </div>
                <div className="mt-2 grid grid-cols-1 gap-4 lg:grid-cols-3">
                  <RankingList
                    title="Top bridges"
                    rows={metricsQuery.data.top_bridges}
                    onSelect={setInspectNodeId}
                  />
                  <RankingList
                    title="Top core"
                    rows={metricsQuery.data.top_core}
                    onSelect={setInspectNodeId}
                  />
                  <RankingList
                    title="Top prolific"
                    rows={metricsQuery.data.top_prolific}
                    onSelect={setInspectNodeId}
                  />
                </div>
              </>
            )}
            {reproducibilityFooter}
          </Card>
        </TabsContent>

        <TabsContent value="roles" className="mt-4 space-y-4">
          <CommenterRolesPanel
            runId={runId}
            projection={projection}
            weight={weight}
            minShared={minShared}
            topN={topN}
            maxCandidates={maxCandidates}
            onSelectCommenter={setInspectNodeId}
          />
        </TabsContent>

        <TabsContent value="communities" className="mt-4 space-y-4">
          <CommenterCommunityInsightsPanel
            runId={runId}
            projection={projection}
            weight={weight}
            minShared={minShared}
            topN={topN}
            maxCandidates={maxCandidates}
            onSelectCommenter={setInspectNodeId}
          />
        </TabsContent>
      </Tabs>

      {/* Commenter detail drawer, available from any tab (the graph's own
          drawer only exists while the Graph tab is mounted). */}
      <Drawer
        open={tab !== "graph" && !!inspectNodeId}
        onOpenChange={(open) => {
          if (!open) setInspectNodeId(null);
        }}
      >
        <DrawerContent side="right">
          {inspectNodeId ? (
            <CommenterDetailDrawer
              handle={inspectNodeId}
              loader={loadCommenterDetail}
            />
          ) : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function RankingList({
  title,
  rows,
  onSelect,
}: {
  title: string;
  rows: { id: string; label?: string | null; betweenness: number }[];
  onSelect?: (id: string) => void;
}) {
  return (
    <div className="rounded-md border border-border p-3">
      <h4 className="mb-2 text-sm font-medium">{title}</h4>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No nodes ranked.</p>
      ) : (
        <ol className="space-y-1 text-sm">
          {rows.map((r, i) => (
            <li key={r.id}>
              <button
                type="button"
                disabled={!onSelect}
                onClick={() => onSelect?.(r.id)}
                className="flex w-full items-center justify-between gap-2 font-mono text-xs text-left hover:text-primary disabled:cursor-default disabled:hover:text-inherit"
              >
                <span className="truncate">
                  {i + 1}. {r.label ?? r.id}
                </span>
                <span className="text-muted-foreground">
                  {r.betweenness.toFixed(3)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function exportRankingsCsv(m: CommenterNetworkMetrics) {
  const sections: [string, CommenterNetworkMetrics["top_bridges"]][] = [
    ["top_bridges", m.top_bridges],
    ["top_core", m.top_core],
    ["top_prolific", m.top_prolific],
  ];
  const lines = ["section,rank,id,label,betweenness"];
  for (const [name, rows] of sections) {
    rows.forEach((r, i) => {
      const label = `"${(r.label ?? "").replace(/"/g, '""')}"`;
      lines.push(`${name},${i + 1},${r.id},${label},${r.betweenness}`);
    });
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "audience-rankings.csv";
  a.click();
  URL.revokeObjectURL(url);
}
