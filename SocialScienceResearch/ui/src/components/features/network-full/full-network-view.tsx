"use client";

import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState } from "@/components/features/state";
import { useRuns } from "@/services/queries";
import {
  NetworkMetricTiles,
  DegreeDistributionPanel,
  RankingPanel,
} from "@/components/features/network-full/network-metrics-tiles";
import { TemporalOverlay } from "@/components/features/network-full/temporal-overlay";
import { EdgeTable } from "@/components/features/network-full/edge-table";
import { useNetworkMetrics, getNetworkExportUrl, useNetworkGraph, useScrapeNetwork } from "@/services/networkFull";
import { EXPORT_FORMATS } from "@/lib/network-full-types";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import { LayerPanel } from "@/components/features/network-layer/layer-panel";
import { CommenterOverlapView } from "@/components/features/commenters/commenter-overlap-view";
import { ExpansionPanel } from "@/components/features/network-expansion/expansion-panel";
import { ScrapeFiltersDialog } from "@/components/features/network-expansion/scrape-filters-dialog";
import { useExpansionJob, scrapeExpansionAll, scrapeExpansionVideo } from "@/services/networkExpansion";
import type { ScrapeFilters as ExpansionFilters } from "@/lib/network-expansion-types";
import type { ChannelGraphPayload, GraphProjection, NetworkGraphPayload } from "@/lib/network-full-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Sparkles, FolderPlus } from "lucide-react";
import { Toast } from "@/components/features/state";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { AddToProjectDialog } from "@/components/features/network-full/add-to-project-dialog";
import { NetworkInsightsPanel } from "@/components/features/network-full/network-insights-panel";
import {
  loadLabSession,
  saveLabSession,
  LAB_PRESETS,
  type LabTab,
} from "@/lib/lab-session";

function mapGraphPayload(payload: {
  nodes: {
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
    community_id?: number | null;
    recommendations_scraped?: boolean;
  }[];
  edges: {
    source: string;
    target: string;
    position?: number | null;
    run_id?: string | null;
    run_type?: string | null;
    run_name?: string | null;
    title?: string | null;
  }[];
}) {
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
      community_id: n.community_id,
      recommendations_scraped: n.recommendations_scraped,
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

function mapChannelGraphPayload(payload: ChannelGraphPayload): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  return {
    nodes: payload.nodes.map((n): GraphNode => {
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
    }),
    links: payload.edges.map((e): GraphLink => ({
      source: e.source,
      target: e.target,
      run_id: e.run_ids?.[0] ?? null,
      run_type: null,
      run_name: null,
      title: `${e.video_edge_count} video edge${e.video_edge_count === 1 ? "" : "s"}`,
    })),
  };
}

export function FullNetworkView() {
  const runsQuery = useRuns();
  // Resumable Lab session (US-73-78 foundation): restore the previous view
  // from localStorage so a researcher can pick up where they left off.
  const initialSession = loadLabSession();
  const [runId, setRunId] = useState<string | null>(initialSession.runId ?? null);
  const [temporalRuns, setTemporalRuns] = useState<string[]>([]);
  const [tab, setTab] = useState<LabTab>(initialSession.tab ?? "metrics");
  const [graphRunId, setGraphRunId] = useState<string | null>(
    initialSession.runId ?? null,
  );
  const [graphChannelId, setGraphChannelId] = useState<string | null>(null);
  const [graphProjection, setGraphProjection] = useState<GraphProjection>(
    initialSession.graphProjection ?? "video",
  );
  const [graphLayerIndex, setGraphLayerIndex] = useState<number | null>(
    initialSession.graphLayerIndex ?? null,
  );
  const [identity, setIdentity] = useState<string>(initialSession.identity ?? "");
  const [annotation, setAnnotation] = useState<string>(
    initialSession.annotation ?? "",
  );
  const [showAnnotations, setShowAnnotations] = useState(false);
  const [graphConnected, setGraphConnected] = useState<"only" | "isolated" | null>(null);
  const [graphScraped, setGraphScraped] = useState<"scraped" | "unscraped" | null>(null);
  const [graphVideoId, setGraphVideoId] = useState<string | null>(null);
  const [addToProjectOpen, setAddToProjectOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [scrapeAllOpen, setScrapeAllOpen] = useState(false);
  const [scrapeVideoTarget, setScrapeVideoTarget] = useState<string | null>(null);
  const [selectedExpansionId, setSelectedExpansionId] = useState<string | null>(null);
  const expansionJob = useExpansionJob();

  const runs = useMemo(() => {
    const data = (runsQuery.data ?? []).slice();
    data.sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
    const ids = data.map((run) => run.run_id);
    return [...new Set(ids)];
  }, [runsQuery.data]);

  // Persist Lab session state so the workspace is resumable (US-73-78).
  useEffect(() => {
    saveLabSession({
      tab,
      runId,
      graphProjection,
      graphLayerIndex,
      identity,
      annotation,
    });
  }, [tab, runId, graphProjection, graphLayerIndex, identity, annotation]);

  const applyPreset = (preset: (typeof LAB_PRESETS)[number]) => {
    const p = preset.patch;
    if (p.tab) setTab(p.tab);
    if (p.graphProjection) setGraphProjection(p.graphProjection);
    if (p.graphLayerIndex !== undefined) setGraphLayerIndex(p.graphLayerIndex);
    if (p.runId !== undefined) {
      setRunId(p.runId);
      setGraphRunId(p.runId || null);
    }
    saveLabSession(p);
  };

  const runNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const run of runsQuery.data ?? []) {
      if (run.name && !names.has(run.run_id)) names.set(run.run_id, run.name);
    }
    return names;
  }, [runsQuery.data]);

  const metrics = useNetworkMetrics(runId ?? undefined, 10, {
    retry: 1,
    onError: (err: Error) => console.error('Failed to load network metrics:', err),
  });

  const graphQuery = useNetworkGraph(
    graphRunId ?? undefined,
    graphChannelId ?? undefined,
    "source",
    graphProjection,
    { retry: 1 },
    graphLayerIndex ?? undefined,
    graphConnected ?? undefined,
    graphScraped ?? undefined,
  );

  const scrapeRunMutation = useScrapeNetwork("run");
  const scrapeChannelMutation = useScrapeNetwork("channel");

  function showToast(message: string, type: "success" | "error") {
    setToast({ message, type });
    setTimeout(() => setToast(null), type === "success" ? 3000 : 5000);
  }

  const handleScrapeRun = async () => {
    if (!graphRunId) return;
    try {
      await scrapeRunMutation.mutateAsync({ run_id: graphRunId, dedupe: true });
      showToast(`Re-scrape queued for run ${graphRunId}`, "success");
    } catch (err) {
      showToast(`Failed to start scrape: ${(err as Error).message}`, "error");
    }
  };

  const handleScrapeChannel = async () => {
    if (!graphChannelId) return;
    try {
      await scrapeChannelMutation.mutateAsync({
        channel_id: graphChannelId,
        dedupe: true,
      });
      showToast(`Scrape queued for channel ${graphChannelId}`, "success");
    } catch (err) {
      showToast(`Failed to start scrape: ${(err as Error).message}`, "error");
    }
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

  const handleScrapeAll = async (filters: ExpansionFilters) => {
    const scopeRunId = graphRunId ?? runId;
    setScrapeAllOpen(false);
    await startExpansionJob(
      () =>
        scrapeExpansionAll({
          run_id: scopeRunId,
          video_ids: [],
          filters,
        }),
      "Scrape-all expansion queued",
    );
  };

  const handleScrapeVideoExpansion = async (filters: ExpansionFilters) => {
    const target = scrapeVideoTarget;
    setScrapeVideoTarget(null);
    if (!target) return;
    await startExpansionJob(
      () => scrapeExpansionVideo(target, filters),
      `Expansion queued for video ${target}`,
    );
  };

  const openVideoScrapeDialog = async (videoId: string): Promise<void> => {
    setScrapeVideoTarget(videoId);
  };

  function toggleTemporalRun(id: string) {
    setTemporalRuns((prev) => {
      if (prev.includes(id)) return prev.filter((r) => r !== id);
      return [...prev, id];
    });
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Network slice
            </Label>
            <RunPicker
              runs={runs}
              names={runNames}
              value={runId}
              placeholder="All runs"
              onChange={(value) => {
                // Drive both the metrics/edges slice (runId) and the graph
                // slice (graphRunId) so a run chosen here actually filters the
                // network graph instead of only the metrics tab.
                setRunId(value);
                setGraphRunId(value || null);
              }}
            />
          </div>

          <div className="flex items-center gap-1.5">
            {EXPORT_FORMATS.map((format) => (
              <a
                key={format}
                href={getNetworkExportUrl(format, runId ?? undefined)}
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

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Layout presets
          </Label>
          {LAB_PRESETS.map((preset) => (
            <Button
              key={preset.id}
              variant="outline"
              size="sm"
              title={preset.description}
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAnnotations((s) => !s)}
          >
            {showAnnotations ? "Hide notes" : "Notes & identity"}
          </Button>
        </div>

        {showAnnotations ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Researcher
              </Label>
              <Input
                value={identity}
                placeholder="Your name / handle"
                onChange={(e) => setIdentity(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Session notes
              </Label>
              <textarea
                className="min-h-[60px] w-full rounded-md border border-border bg-background px-2 py-1 text-sm outline-none focus-visible:border-ring"
                value={annotation}
                placeholder="Observations for this network slice…"
                onChange={(e) => setAnnotation(e.target.value)}
              />
            </div>
          </div>
        ) : null}
      </Card>

      <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
        <TabsList>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="temporal">Temporal</TabsTrigger>
          <TabsTrigger value="edges">Edges</TabsTrigger>
          <TabsTrigger value="graph">Graph</TabsTrigger>
          <TabsTrigger value="layers">Layers</TabsTrigger>
          <TabsTrigger value="commenters">Commenters</TabsTrigger>
          <TabsTrigger value="expansion">Expansion</TabsTrigger>
        </TabsList>

        <TabsContent value="metrics" className="mt-4 space-y-4">
          {metrics.isError ? (
            <ErrorState
              message={
                metrics.error instanceof Error
                  ? metrics.error.message
                  : "Failed to load network metrics"
              }
              retry={() => metrics.refetch()}
            />
          ) : metrics.data ? (
            <>
              {runId ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">slice</Badge>
                  <code>{runNames.get(runId) ?? runId}</code>
                </div>
              ) : null}
              <NetworkMetricTiles metrics={metrics.data} />
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <DegreeDistributionPanel distribution={metrics.data.degree_distribution} />
                <RankingPanel title="Top hubs" videos={metrics.data.top_hubs} valueLabel="hub" />
                <RankingPanel title="Top authorities" videos={metrics.data.top_authorities} valueLabel="auth" />
                <RankingPanel title="Most recommended" videos={metrics.data.most_recommended} valueLabel="×" />
                <RankingPanel title="Most active sources" videos={metrics.data.most_active_sources} valueLabel="→" />
              </div>
            </>
          ) : (
            <LoadingState label="Loading network metrics…" />
          )}
        </TabsContent>

        <TabsContent value="insights" className="mt-4 space-y-4">
          <NetworkInsightsPanel
            metrics={metrics.data}
            graph={graphProjection === "video" && graphQuery.data ? (graphQuery.data as NetworkGraphPayload) : undefined}
            loading={metrics.isLoading}
          />
        </TabsContent>

        <TabsContent value="temporal" className="mt-4 space-y-4">
          <Card className="p-4">
            <h3 className="mb-2 text-sm font-medium">Runs to compare</h3>
            {runs.length === 0 ? (
              <EmptyState
                title="No collection runs yet"
                description="Collect something first, then compare runs over time."
                className="min-h-24 p-4"
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {runs.map((id) => {
                  const isSelected = temporalRuns.includes(id);
                  return (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => toggleTemporalRun(id)}
                      className="rounded-md border border-border px-2.5 py-1 font-mono text-xs outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                    >
                      {runNames.get(id) ?? id}
                    </button>
                  );
                })}
              </div>
            )}
          </Card>
          <TemporalOverlay runIds={temporalRuns} />
        </TabsContent>

        <TabsContent value="edges" className="mt-4">
          <EdgeTable runId={runId ?? undefined} />
        </TabsContent>

        <TabsContent value="graph" className="mt-4 space-y-4">
          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Projection
              </Label>
              <Select
                value={graphProjection}
                onValueChange={(v) => setGraphProjection(v as GraphProjection)}
                items={[
                  { value: "video", label: "Video graph" },
                  { value: "channel", label: "Channel graph" },
                ]}
              >
                <SelectTrigger className="w-48" aria-label="Select graph projection">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="video">Video graph</SelectItem>
                  <SelectItem value="channel">Channel graph</SelectItem>
                </SelectContent>
              </Select>
              {graphProjection === "channel" && graphQuery.data ? (
                <Badge variant="outline">
                  {(graphQuery.data as ChannelGraphPayload).unattributed_edges > 0
                    ? `${(graphQuery.data as ChannelGraphPayload).unattributed_edges} edges without channel attribution`
                    : "All edges attributed"}
                </Badge>
              ) : null}

              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Layer
                </Label>
                <Select
                  value={graphLayerIndex === null ? "" : String(graphLayerIndex)}
                  onValueChange={(v) =>
                    setGraphLayerIndex(v === "" ? null : Number(v))
                  }
                  items={[
                    { value: "", label: "All layers" },
                    { value: "0", label: "Layer 0 (sources)" },
                    { value: "1", label: "Layer 1" },
                    { value: "2", label: "Layer 2" },
                    { value: "3", label: "Layer 3" },
                  ]}
                >
                  <SelectTrigger className="w-40" aria-label="Filter by layer">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All layers</SelectItem>
                    <SelectItem value="0">Layer 0 (sources)</SelectItem>
                    <SelectItem value="1">Layer 1</SelectItem>
                    <SelectItem value="2">Layer 2</SelectItem>
                    <SelectItem value="3">Layer 3</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Connectivity
                </Label>
                <Select
                  value={graphConnected ?? ""}
                  onValueChange={(v) =>
                    setGraphConnected(v === "" ? null : (v as "only" | "isolated"))
                  }
                  items={[
                    { value: "", label: "All nodes" },
                    { value: "only", label: "Connected only" },
                    { value: "isolated", label: "Isolated only" },
                  ]}
                >
                  <SelectTrigger className="w-44" aria-label="Filter by connectivity">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All nodes</SelectItem>
                    <SelectItem value="only">Connected only</SelectItem>
                    <SelectItem value="isolated">Isolated only</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Scrape state
                </Label>
                <Select
                  value={graphScraped ?? ""}
                  onValueChange={(v) =>
                    setGraphScraped(v === "" ? null : (v as "scraped" | "unscraped"))
                  }
                  items={[
                    { value: "", label: "All nodes" },
                    { value: "scraped", label: "Scraped" },
                    { value: "unscraped", label: "Not scraped" },
                  ]}
                >
                  <SelectTrigger className="w-40" aria-label="Filter by scrape state">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All nodes</SelectItem>
                    <SelectItem value="scraped">Scraped</SelectItem>
                    <SelectItem value="unscraped">Not scraped</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {graphConnected === "isolated" || graphScraped !== null || graphLayerIndex !== null ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setGraphLayerIndex(null);
                    setGraphConnected(null);
                    setGraphScraped(null);
                  }}
                >
                  Clear advanced filters
                </Button>
              ) : null}
            </div>
            {graphQuery.isError ? (
              <ErrorState
                message={
                  graphQuery.error instanceof Error
                    ? graphQuery.error.message
                    : "Failed to load network graph"
                }
                retry={() => graphQuery.refetch()}
              />
            ) : graphQuery.data ? (
              graphProjection === "channel" ? (
                <NetworkGraph
                  nodes={mapChannelGraphPayload(graphQuery.data as ChannelGraphPayload).nodes}
                  links={mapChannelGraphPayload(graphQuery.data as ChannelGraphPayload).links}
                  runs={graphQuery.data.runs}
                  channels={graphQuery.data.channels}
                  selectedRun={graphRunId ?? runId ?? undefined}
                  selectedChannel={graphChannelId ?? undefined}
                  onRunChange={(v) => setGraphRunId(v === "__all" ? null : v)}
                  onChannelChange={(v) => setGraphChannelId(v === "__all" ? null : v)}
                  onClearFilters={() => {
                    setGraphRunId(null);
                    setGraphChannelId(null);
                  }}
                  onScrapeClick={(channelId) => openVideoScrapeDialog(channelId)}
                />
              ) : (
                <NetworkGraph
                  nodes={mapGraphPayload(graphQuery.data as NetworkGraphPayload).nodes}
                  links={mapGraphPayload(graphQuery.data as NetworkGraphPayload).links}
                  runs={graphQuery.data.runs}
                  channels={graphQuery.data.channels}
                  selectedRun={graphRunId ?? runId ?? undefined}
                  selectedChannel={graphChannelId ?? undefined}
                  onRunChange={(v) => setGraphRunId(v === "__all" ? null : v)}
                  onChannelChange={(v) => setGraphChannelId(v === "__all" ? null : v)}
                  onClearFilters={() => {
                    setGraphRunId(null);
                    setGraphChannelId(null);
                  }}
                  onScrapeClick={(videoId) => openVideoScrapeDialog(videoId)}
                  onOverlapClick={(videoId) => {
                    setGraphVideoId(videoId);
                    setTab("commenters");
                  }}
                />
              )
            ) : (
              <LoadingState label="Loading network graph…" />
            )}

            {graphQuery.data && graphProjection === "video" ? (
              <div className="mt-4 border-t pt-3">
                <NodeListPanel
                  nodes={mapGraphPayload(graphQuery.data as NetworkGraphPayload).nodes}
                  isolatedOnly={graphConnected === "isolated"}
                  onScrape={openVideoScrapeDialog}
                />
              </div>
            ) : null}

            <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
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
              {graphRunId ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleScrapeRun()}
                  disabled={scrapeRunMutation.isPending || scrapeRunMutation.isRunning}
                >
                  {scrapeRunMutation.isRunning ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <Sparkles aria-hidden />
                  )}
                  Re-scrape this run
                </Button>
              ) : null}
              {graphChannelId ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleScrapeChannel()}
                  disabled={scrapeChannelMutation.isPending || scrapeChannelMutation.isRunning}
                >
                  {scrapeChannelMutation.isRunning ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <Sparkles aria-hidden />
                  )}
                  Scrape this channel
                </Button>
              ) : null}
              {graphProjection === "video" && graphQuery.data ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAddToProjectOpen(true)}
                >
                  <FolderPlus aria-hidden />
                  Add to project
                </Button>
              ) : null}
            </div>
            {scrapeRunMutation.jobId ? (
              <div className="mt-3">
                <JobProgressCard
                  key={scrapeRunMutation.jobId}
                  jobId={scrapeRunMutation.jobId}
                  title="Re-scraping run"
                />
              </div>
            ) : null}
            {scrapeChannelMutation.jobId ? (
              <div className="mt-3">
                <JobProgressCard
                  key={scrapeChannelMutation.jobId}
                  jobId={scrapeChannelMutation.jobId}
                  title="Scraping channel"
                />
              </div>
            ) : null}
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
        </TabsContent>
        <TabsContent value="layers" className="mt-4">
          <LayerPanel />
        </TabsContent>
        <TabsContent value="commenters" className="mt-4">
          <CommenterOverlapView
            initialVideoIds={graphVideoId ? [graphVideoId] : []}
            initialChannelIds={graphChannelId ? [graphChannelId] : []}
          />
        </TabsContent>
        <TabsContent value="expansion" className="mt-4">
          <ExpansionPanel
            selectedActionId={selectedExpansionId}
            onSelectAction={setSelectedExpansionId}
          />
        </TabsContent>
      </Tabs>

      <ScrapeFiltersDialog
        open={scrapeAllOpen}
        onOpenChange={setScrapeAllOpen}
        title="Scrape all recommendations"
        description={`Expand the current network slice one hop${
          graphRunId ? " (scoped to the selected run)" : ""
        }. A new auto-Project organizes this action's runs and datasets.`}
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
        onConfirm={handleScrapeVideoExpansion}
      />

      <AddToProjectDialog
        open={addToProjectOpen}
        onOpenChange={setAddToProjectOpen}
        nodeIds={
          graphProjection === "video" && graphQuery.data
            ? (graphQuery.data as NetworkGraphPayload).nodes.map((n) => n.video_id)
            : []
        }
        runId={graphRunId ?? undefined}
        onSaved={() => showToast("Filtered network saved to project", "success")}
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

function RunPicker({
  runs,
  names,
  value,
  placeholder,
  onChange,
}: {
  runs: string[];
  names: Map<string, string>;
  value: string | null;
  placeholder: string;
  onChange: (value: string | null) => void;
}) {
  return (
    <Select
      value={value ?? ""}
      onValueChange={(next) => onChange(next || null)}
      items={runs.map((id) => ({ value: id, label: names.get(id) ?? id }))}
    >
      <SelectTrigger className="w-72" aria-label="Select network slice run">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="">{placeholder}</SelectItem>
        {runs.map((id) => (
          <SelectItem key={id} value={id}>
            {names.get(id) ?? id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function NodeListPanel({
  nodes,
  isolatedOnly,
  onScrape,
}: {
  nodes: GraphNode[];
  isolatedOnly: boolean;
  onScrape: (videoId: string) => void;
}) {
  const sorted = useMemo(() => {
    const list = nodes.slice();
    list.sort((a, b) => {
      const deg = (b.in_degree + b.out_degree) - (a.in_degree + a.out_degree);
      return deg !== 0 ? deg : (a.id).localeCompare(b.id);
    });
    return list;
  }, [nodes]);

  const [expanded, setExpanded] = useState(true);

  if (sorted.length === 0) return null;

  const disconnectedCount = sorted.filter(
    (n) => n.in_degree === 0 && n.out_degree === 0,
  ).length;

  return (
    <div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1.5 text-sm font-medium outline-none hover:text-foreground/80"
        >
          <span aria-hidden>{expanded ? "▾" : "▸"}</span>
          {isolatedOnly ? "Isolated (non-connected) videos" : "Node list"}
          <Badge variant="outline">{sorted.length}</Badge>
          {!isolatedOnly && disconnectedCount > 0 ? (
            <Badge variant="secondary">{disconnectedCount} non-connected</Badge>
          ) : null}
        </button>
        {isolatedOnly ? (
          <Button variant="ghost" size="sm" onClick={() => onScrape(sorted[0].id)}>
            Scrape first
          </Button>
        ) : null}
      </div>
      {expanded ? (
        <div className="mt-2 max-h-64 overflow-y-auto rounded-md border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur">
              <tr>
                <th className="px-2 py-1 font-medium">Video</th>
                <th className="px-2 py-1 font-medium">Channel</th>
                <th className="px-2 py-1 font-medium">Degree</th>
                <th className="px-2 py-1 font-medium">Scraped</th>
                <th className="px-2 py-1 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((node) => (
                <tr key={node.id} className="border-t first:border-t-0">
                  <td className="max-w-56 truncate px-2 py-1 font-mono" title={node.title ?? undefined}>
                    {node.id}
                  </td>
                  <td className="max-w-40 truncate px-2 py-1">{node.channel ?? "—"}</td>
                  <td className="px-2 py-1">
                    {node.out_degree}→ {node.in_degree}←
                  </td>
                  <td className="px-2 py-1">
                    {node.recommendations_scraped ? (
                      <Badge variant="default">scraped</Badge>
                    ) : (
                      <Badge variant="outline">unscraped</Badge>
                    )}
                  </td>
                  <td className="px-2 py-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onScrape(node.id)}
                    >
                      Scrape
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
