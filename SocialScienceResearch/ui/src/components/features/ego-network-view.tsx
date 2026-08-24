"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDownToLine, ArrowUpFromLine, Download, Loader2, Sparkles } from "lucide-react";
import { useRuns, useChannels, useNetworkVideoContext } from "@/services/queries";
import {
  LoadingState,
  ErrorState,
  EmptyState,
  Toast,
} from "@/components/features/state";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import type { GraphNodeKind } from "@/lib/network-full-types";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { DataTable, type Column } from "@/components/features/data-table";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { exportGraph, exportVideoMetadata } from "@/lib/export-graph";
import { ScrapeFiltersDialog } from "@/components/features/network-expansion/scrape-filters-dialog";
import {
  useExpansionJob,
  scrapeExpansionVideo,
  scrapeExpansionAll,
} from "@/services/networkExpansion";
import type { ScrapeFilters } from "@/lib/network-expansion-types";
import { formatNumber } from "@/lib/format";

interface RecommendationEdge {
  source_video_id?: string;
  recommended_video_id?: string;
  title?: string | null;
  position?: number | null;
  run_id?: string | null;
  run_type?: string | null;
}

export function EgoNetworkView({ videoId }: { videoId: string }) {
  const router = useRouter();
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set());
  const runsQuery = useRuns("recommendation");
  const recommendationRuns =
    runsQuery.data?.filter((r) => r.status !== "pending" && r.status !== "running") ?? [];
  const runNames = new Map(
    recommendationRuns.map((r) => [r.run_id, r.name ?? r.run_id]),
  );

  const channelsQuery = useChannels();
  const channels = channelsQuery.data ?? [];
  const channelNames = new Map(channels.map((c) => [c.channel_id, c.title ?? c.channel_id]));
  const [selectedChannelIds, setSelectedChannelIds] = useState<Set<string>>(new Set());

  const contextQuery = useNetworkVideoContext(
    videoId,
    selectedRunIds.size ? [...selectedRunIds] : undefined,
  );

  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [scrapeVideoTarget, setScrapeVideoTarget] = useState<string | null>(null);
  const [scrapeAllOpen, setScrapeAllOpen] = useState(false);
  const expansionJob = useExpansionJob();

  // Logical network filters (not a generic variable/operator builder): they
  // prune the ego web by node role and prominence. The run selector above
  // already scopes which collection runs contribute edges.
  const [nodeKinds, setNodeKinds] = useState<Set<GraphNodeKind>>(
    new Set(["both", "source", "target", "other"]),
  );
  const [minDegree, setMinDegree] = useState(0);
  const [hasTitleOnly, setHasTitleOnly] = useState(false);

  function toggleKind(kind: GraphNodeKind) {
    setNodeKinds((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  function toggleSetValue(
    setter: (updater: (prev: Set<string>) => Set<string>) => void,
    value: string,
  ) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  const nodeChannels = contextQuery.data?.node_channels ?? {};

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), type === "success" ? 3000 : 5000);
  };

  const startExpansionJob = async (
    fn: () => Promise<{ job_id: string }>,
    message: string,
  ) => {
    try {
      await expansionJob.mutateAsync(fn);
      showToast(message, "success");
    } catch (err) {
      showToast(`Failed to start expansion: ${(err as Error).message}`, "error");
    }
  };

  const handleScrapeVideo = async (filters: ScrapeFilters) => {
    const target = scrapeVideoTarget;
    setScrapeVideoTarget(null);
    if (!target) return;
    await startExpansionJob(
      () => scrapeExpansionVideo(target, filters),
      `Expansion queued for video ${target}`,
    );
  };

  const handleScrapeAll = async (filters: ScrapeFilters) => {
    const context = contextQuery.data;
    // Expand the whole connected slice (the queried video plus every node
    // reachable through the ego scope) so newly scraped recommendations can
    // cross-link and form their own central nodes.
    const videoIds = new Set<string>([videoId]);
    for (const e of context?.graph_edges ?? []) {
      if (e.source_video_id) videoIds.add(e.source_video_id);
      if (e.recommended_video_id) videoIds.add(e.recommended_video_id);
    }
    for (const e of context?.recommended_by ?? []) if (e.source_video_id) videoIds.add(e.source_video_id);
    for (const e of context?.recommends ?? []) if (e.recommended_video_id) videoIds.add(e.recommended_video_id);
    setScrapeAllOpen(false);
    await startExpansionJob(
      () =>
        scrapeExpansionAll({
          run_id: selectedRunIds.size === 1 ? [...selectedRunIds][0] : null,
          video_ids: [...videoIds],
          filters,
        }),
      "Scrape-all expansion queued",
    );
  };

  const handleNodeClick = (id: string) => {
    router.push(`/network/videos/${id}`);
  };

  const graph = useMemo(() => {
    const context = contextQuery.data;
    if (!context) return { nodes: [] as GraphNode[], links: [] as GraphLink[] };

    // Connected web: every edge touching the ego scope (the queried video,
    // everyone it recommends, everyone who recommends it). Recommendations
    // link to each other here - a video that was itself scraped as a
    // recommendation now contributes its own out-edges, so it renders as a
    // normal central node (in-degree + out-degree) instead of being pushed to
    // the rim of a star centered on the queried video.
    const edges = context.graph_edges ?? [];
    const inDegree = new Map<string, number>();
    const outDegree = new Map<string, number>();
    const titleById = new Map<string, string>();

    for (const e of edges) {
      const s = e.source_video_id;
      const t = e.recommended_video_id;
      if (!s || !t) continue;
      outDegree.set(s, (outDegree.get(s) ?? 0) + 1);
      inDegree.set(t, (inDegree.get(t) ?? 0) + 1);
      if (e.title && !titleById.has(t)) titleById.set(t, e.title);
    }

    const ids = new Set<string>([videoId]);
    for (const e of edges) {
      if (e.source_video_id) ids.add(e.source_video_id);
      if (e.recommended_video_id) ids.add(e.recommended_video_id);
    }

    const nodes: GraphNode[] = [...ids].map((id) => {
      const nIn = inDegree.get(id) ?? 0;
      const nOut = outDegree.get(id) ?? 0;
      const kind: GraphNodeKind =
        nOut > 0 && nIn > 0
          ? "both"
          : nOut > 0
            ? "source"
            : nIn > 0
              ? "target"
              : "other";
      return {
        id,
        title: titleById.get(id),
        kind,
        in_degree: nIn,
        out_degree: nOut,
      };
    });

    const links: GraphLink[] = edges
      .filter((e) => e.source_video_id && e.recommended_video_id)
      .map((e) => ({
        source: e.source_video_id as string,
        target: e.recommended_video_id as string,
        run_id: e.run_id,
        run_type: e.run_type,
      }));

    return { nodes, links };
  }, [contextQuery.data, videoId]);

  const visibleGraph = useMemo(() => {
    const visibleIds = new Set<string>();
    for (const n of graph.nodes) {
      if (!nodeKinds.has(n.kind)) continue;
      if (n.in_degree + n.out_degree < minDegree) continue;
      if (hasTitleOnly && !n.title) continue;
      const channel = nodeChannels[n.id];
      if (selectedChannelIds.size > 0 && (!channel || !selectedChannelIds.has(channel)))
        continue;
      visibleIds.add(n.id);
    }
    return {
      nodes: graph.nodes.filter((n) => visibleIds.has(n.id)),
      links: graph.links.filter(
        (l) => visibleIds.has(String(l.source)) && visibleIds.has(String(l.target)),
      ),
    };
  }, [graph, nodeKinds, minDegree, hasTitleOnly, nodeChannels, selectedChannelIds]);

  const recommendedByColumns: Column<RecommendationEdge>[] = [
    {
      key: "source_video_id",
      header: "Source video",
      sortable: true,
      sortValue: (e) => e.source_video_id,
      cell: (e) => (
        <Link
          href={`/network/videos/${e.source_video_id}`}
          className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        >
          {e.source_video_id}
        </Link>
      ),
    },
    {
      key: "title",
      header: "Title",
      cell: (e) => <span className="line-clamp-1 max-w-md">{e.title ?? "—"}</span>,
    },
    {
      key: "position",
      header: "Position",
      sortable: true,
      sortValue: (e) => e.position ?? -1,
      cell: (e) => (e.position == null ? "—" : `#${e.position + 1}`),
      className: "text-right tabular-nums",
    },
    {
      key: "run_id",
      header: "Run",
      sortable: true,
      sortValue: (e) => e.run_id ?? "",
      cell: (e) => (
        <code className="text-xs text-muted-foreground">
          {e.run_id ? runNames.get(e.run_id) ?? e.run_id : "—"}
        </code>
      ),
    },
    {
      key: "run_type",
      header: "Run Type",
      sortable: true,
      sortValue: (e) => e.run_type ?? "",
      cell: (e) => <code className="text-xs text-muted-foreground">{e.run_type ?? "—"}</code>,
    },
  ];

  const recommendsColumns: Column<RecommendationEdge>[] = [
    {
      key: "recommended_video_id",
      header: "Recommended video",
      sortable: true,
      sortValue: (e) => e.recommended_video_id,
      cell: (e) => (
        <Link
          href={`/network/videos/${e.recommended_video_id}`}
          className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        >
          {e.recommended_video_id}
        </Link>
      ),
    },
    {
      key: "title",
      header: "Title",
      cell: (e) => <span className="line-clamp-1 max-w-md">{e.title ?? "—"}</span>,
    },
    {
      key: "position",
      header: "Position",
      sortable: true,
      sortValue: (e) => e.position ?? -1,
      cell: (e) => (e.position == null ? "—" : `#${e.position + 1}`),
      className: "text-right tabular-nums",
    },
    {
      key: "run_id",
      header: "Run",
      sortable: true,
      sortValue: (e) => e.run_id ?? "",
      cell: (e) => (
        <code className="text-xs text-muted-foreground">
          {e.run_id ? runNames.get(e.run_id) ?? e.run_id : "—"}
        </code>
      ),
    },
    {
      key: "run_type",
      header: "Run Type",
      sortable: true,
      sortValue: (e) => e.run_type ?? "",
      cell: (e) => <code className="text-xs text-muted-foreground">{e.run_type ?? "—"}</code>,
    },
  ];

  if (contextQuery.isLoading) return <LoadingState label="Loading ego-network…" />;
  if (contextQuery.isError)
    return <ErrorState message={(contextQuery.error as Error).message} />;
  const context = contextQuery.data!;

  if (context.in_degree === 0 && context.out_degree === 0) {
    return (
      <EmptyState
        title="No network context for this video"
        description="This video has no observed recommendation edges in the selected slice."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Connected recommendation network: who recommends this video (in-edges),
          whom it recommends (out-edges), and the cross-links among them - every
          edge touching the ego scope, attributed to the selected runs. Filter by
          run, channel, node role or prominence to focus the web on specific
          videos or channels.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <details className="relative rounded-md border border-border">
            <summary className="cursor-pointer select-none px-3 py-1.5 text-xs">
              Runs: {selectedRunIds.size ? `${selectedRunIds.size} selected` : "All runs"}
            </summary>
            <div className="absolute z-20 mt-1 max-h-72 w-64 overflow-auto rounded-md border border-border bg-popover p-2 text-popover-foreground shadow-md">
              <label className="flex items-center gap-2 px-1 py-1 text-xs">
                <input
                  type="checkbox"
                  checked={selectedRunIds.size === 0}
                  onChange={() => setSelectedRunIds(new Set())}
                />
                All runs
              </label>
              {recommendationRuns.map((r) => (
                <label key={r.run_id} className="flex items-center gap-2 px-1 py-1 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedRunIds.has(r.run_id)}
                    onChange={() => toggleSetValue(setSelectedRunIds, r.run_id)}
                  />
                  {r.name ?? r.run_id}
                </label>
              ))}
            </div>
          </details>

          <details className="relative rounded-md border border-border">
            <summary className="cursor-pointer select-none px-3 py-1.5 text-xs">
              Channels: {selectedChannelIds.size ? `${selectedChannelIds.size} selected` : "All channels"}
            </summary>
            <div className="absolute z-20 mt-1 max-h-72 w-64 overflow-auto rounded-md border border-border bg-popover p-2 text-popover-foreground shadow-md">
              <label className="flex items-center gap-2 px-1 py-1 text-xs">
                <input
                  type="checkbox"
                  checked={selectedChannelIds.size === 0}
                  onChange={() => setSelectedChannelIds(new Set())}
                />
                All channels
              </label>
              {channels.map((c) => (
                <label key={c.channel_id} className="flex items-center gap-2 px-1 py-1 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedChannelIds.has(c.channel_id)}
                    onChange={() => toggleSetValue(setSelectedChannelIds, c.channel_id)}
                  />
                  {c.title ?? c.channel_id}
                </label>
              ))}
            </div>
          </details>

          {(["both", "source", "target", "other"] as GraphNodeKind[]).map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => toggleKind(kind)}
              aria-pressed={nodeKinds.has(kind)}
              className="rounded-full border border-border px-2.5 py-1 text-xs transition-colors hover:border-foreground/40 aria-pressed:border-foreground/60 aria-pressed:bg-muted"
            >
              {kind}
            </button>
          ))}

          <label className="flex items-center gap-1.5 text-xs">
            Min degree
            <input
              type="number"
              min={0}
              value={minDegree}
              onChange={(e) => setMinDegree(Number(e.target.value) || 0)}
              className="w-16 rounded-md border border-border bg-background px-2 py-1 tabular-nums"
            />
          </label>

          <label className="flex items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={hasTitleOnly}
              onChange={(e) => setHasTitleOnly(e.target.checked)}
            />
            Has title
          </label>

          {(selectedRunIds.size > 0 ||
            selectedChannelIds.size > 0 ||
            minDegree > 0 ||
            hasTitleOnly ||
            nodeKinds.size < 4) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedRunIds(new Set());
                setSelectedChannelIds(new Set());
                setMinDegree(0);
                setHasTitleOnly(false);
                setNodeKinds(new Set(["both", "source", "target", "other"]));
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">In-degree</p>
          <p className="text-2xl font-semibold tabular-nums">{formatNumber(context.in_degree)}</p>
        </Card>
        <Card className="p-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Out-degree</p>
          <p className="text-2xl font-semibold tabular-nums">{formatNumber(context.out_degree)}</p>
        </Card>
        <Card className="p-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">PageRank</p>
          <p className="text-2xl font-semibold tabular-nums">
            {context.pagerank === null ? "—" : context.pagerank.toFixed(6)}
          </p>
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Graph</h2>
          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="outline" size="sm" disabled={visibleGraph.nodes.length === 0} />
                }
              >
                <Download aria-hidden />
                Export
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Download visible graph</DropdownMenuLabel>
                </DropdownMenuGroup>
                <DropdownMenuItem
                  onClick={() =>
                    exportGraph("edges-csv", visibleGraph.nodes, visibleGraph.links, `ego-network-${videoId}`)
                  }
                >
                  Edge list (CSV)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() =>
                    exportGraph("nodes-csv", visibleGraph.nodes, visibleGraph.links, `ego-network-${videoId}`)
                  }
                >
                  Nodes (CSV)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() =>
                    exportGraph("json", visibleGraph.nodes, visibleGraph.links, `ego-network-${videoId}`)
                  }
                >
                  Graph (JSON)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() =>
                    exportGraph("xlsx", visibleGraph.nodes, visibleGraph.links, `ego-network-${videoId}`)
                  }
                >
                  Spreadsheet (XLSX)
                </DropdownMenuItem>
                <DropdownMenuGroup>
                  <DropdownMenuLabel>All video metadata</DropdownMenuLabel>
                </DropdownMenuGroup>
                <DropdownMenuItem
                  onClick={() =>
                    exportVideoMetadata("csv", visibleGraph.nodes, `ego-metadata-${videoId}`)
                  }
                >
                  Metadata (CSV)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() =>
                    exportVideoMetadata("json", visibleGraph.nodes, `ego-metadata-${videoId}`)
                  }
                >
                  Metadata (JSON)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() =>
                    exportVideoMetadata("xlsx", visibleGraph.nodes, `ego-metadata-${videoId}`)
                  }
                >
                  Metadata (XLSX)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setScrapeAllOpen(true)}
              disabled={expansionJob.isRunning}
            >
              {expansionJob.isRunning ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Sparkles aria-hidden />
              )}
              Scrape all recommendations
            </Button>
          </div>
        </div>
        <NetworkGraph 
          nodes={visibleGraph.nodes} 
          links={visibleGraph.links} 
          onNavigate={handleNodeClick}
          onScrapeClick={async (id) => {
            setScrapeVideoTarget(id);
          }}
        />
        {expansionJob.jobId ? (
          <div className="mt-3">
            <JobProgressCard
              key={expansionJob.jobId}
              jobId={expansionJob.jobId}
              title="Scraping recommendations"
            />
          </div>
        ) : null}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Who recommends this video">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-medium">
            <ArrowDownToLine className="size-4 text-muted-foreground" aria-hidden />
            Recommended by ({context.recommended_by.length})
          </h2>
          <DataTable columns={recommendedByColumns} rows={context.recommended_by.filter((e) => visibleGraph.nodes.some((n) => n.id === e.source_video_id))} getRowKey={(e) => `${e.source_video_id}-${e.run_id ?? ""}`} initialSortKey="position" ariaLabel="Videos recommending this video" />
        </section>
        <section aria-label="Who this video recommends">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-medium">
            <ArrowUpFromLine className="size-4 text-muted-foreground" aria-hidden />
            Recommends ({context.recommends.length})
          </h2>
          <DataTable columns={recommendsColumns} rows={context.recommends.filter((e) => visibleGraph.nodes.some((n) => n.id === e.recommended_video_id))} getRowKey={(e) => `${e.recommended_video_id}-${e.run_id ?? ""}`} initialSortKey="position" ariaLabel="Videos recommended by this video" />
        </section>
      </div>

      <ScrapeFiltersDialog
        open={scrapeAllOpen}
        onOpenChange={setScrapeAllOpen}
        title="Scrape all recommendations"
        description={`Expand the ego network (${videoId} and its neighbors) one hop. A new auto-Project organizes this action's runs and datasets.`}
        onConfirm={handleScrapeAll}
      />

      <ScrapeFiltersDialog
        open={scrapeVideoTarget !== null}
        onOpenChange={(open) => {
          if (!open) setScrapeVideoTarget(null);
        }}
        title="Scrape recommendations"
        description={
          scrapeVideoTarget
            ? `One-hop expansion of video ${scrapeVideoTarget}.`
            : undefined
        }
        onConfirm={handleScrapeVideo}
      />

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