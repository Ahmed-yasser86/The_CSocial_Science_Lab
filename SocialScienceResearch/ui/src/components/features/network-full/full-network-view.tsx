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
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { useRuns, useJobs } from "@/services/queries";
import {
  NetworkMetricTiles,
  DegreeDistributionPanel,
  RankingPanel,
} from "@/components/features/network-full/network-metrics-tiles";
import { CentralitiesPanel } from "@/components/features/network-full/centralities-panel";
import { TemporalOverlay } from "@/components/features/network-full/temporal-overlay";
import { EdgeTable } from "@/components/features/network-full/edge-table";
import { useNetworkMetrics, getNetworkExportUrl, useNetworkGraph, useScrapeNetwork } from "@/services/networkFull";
import { EXPORT_FORMATS } from "@/lib/network-full-types";
import { exportVideoMetadata, type ExportNode } from "@/lib/export-graph";
import { NetworkGraph, type GraphLink, type GraphNode, type NetworkGraphProps } from "@/components/features/network-graph";
import { LayerPanel } from "@/components/features/network-layer/layer-panel";
import { CommenterOverlapView } from "@/components/features/commenters/commenter-overlap-view";
import { ExpansionPanel } from "@/components/features/network-expansion/expansion-panel";
import { ScrapeFiltersDialog } from "@/components/features/network-expansion/scrape-filters-dialog";
import { useExpansionJob, scrapeExpansionAll, scrapeExpansionVideo } from "@/services/networkExpansion";
import type { ScrapeFilters as ExpansionFilters } from "@/lib/network-expansion-types";
import type { ChannelFacet, ChannelGraphPayload, GraphProjection, NetworkGraphPayload } from "@/lib/network-full-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Sparkles, FolderPlus, Maximize2, Minimize2, RotateCcw } from "lucide-react";
import { Toast } from "@/components/features/state";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { AddToProjectDialog } from "@/components/features/network-full/add-to-project-dialog";
import { NetworkInsightsPanel } from "@/components/features/network-full/network-insights-panel";
import {
  NetworkCommunityInsightsPanel,
  NetworkRolesPanel,
} from "@/components/features/network-full/roles-community-panels";
import { NetworkMatrices } from "@/components/features/network-full/network-matrices";
import { SamplingFeasibility } from "@/components/features/network-full/sampling-feasibility";
import { ChannelsPanel } from "@/components/features/network-full/channels-panel";
import { AudienceNetworkView } from "@/components/features/network-full/audience-network-view";
import {
  loadLabSession,
  saveLabSession,
  LAB_PRESETS,
  type LabFamily,
  type LabTab,
} from "@/lib/lab-session";

function FamilyToggle({
  value,
  onChange,
}: {
  value: LabFamily;
  onChange: (family: LabFamily) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-border p-0.5">
      {(["recommendation", "audience"] as const).map((f) => (
        <button
          key={f}
          type="button"
          aria-pressed={value === f}
          onClick={() => onChange(f)}
          className={
            "rounded px-2.5 py-1 text-xs font-medium outline-none focus-visible:border-ring " +
            (value === f
              ? "bg-primary text-primary-foreground"
              : "hover:bg-muted")
          }
        >
          {f === "recommendation" ? "Recommendation" : "Audience (commenters)"}
        </button>
      ))}
    </div>
  );
}

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
  const jobsQuery = useJobs();
  // Resumable Lab session (US-73-78 foundation): restore the previous view
  // from localStorage so a researcher can pick up where they left off. State is
  // initialised to defaults on the server AND the client's first paint to avoid
  // a hydration mismatch; the stored session is applied in a post-mount effect.
  const [runId, setRunId] = useState<string | null>(null);
  const [temporalRuns, setTemporalRuns] = useState<string[]>([]);
  const [tab, setTab] = useState<LabTab>("metrics");
  const [family, setFamily] = useState<LabFamily>("recommendation");
  const [graphRunId, setGraphRunId] = useState<string | null>(null);
  const [graphChannelIds, setGraphChannelIds] = useState<string[]>([]);
  const [graphProjection, setGraphProjection] = useState<GraphProjection>("video");
  const [graphLayerIndex, setGraphLayerIndex] = useState<number | null>(null);
  const [identity, setIdentity] = useState<string>("");
  const [annotation, setAnnotation] = useState<string>(
    "",
  );
  const [showAnnotations, setShowAnnotations] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [graphConnected, setGraphConnected] = useState<"only" | "isolated" | null>(null);
  const [graphScraped, setGraphScraped] = useState<"scraped" | "unscraped" | null>(null);
  const [graphIncludeSubRuns, setGraphIncludeSubRuns] = useState(false);
  const [graphVideoIds, setGraphVideoIds] = useState<string[]>([]);
  const [graphJobIds, setGraphJobIds] = useState<string[]>([]);
  const [addToProjectOpen, setAddToProjectOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [scrapeAllOpen, setScrapeAllOpen] = useState(false);
  const [scrapeVideoTarget, setScrapeVideoTarget] = useState<string | null>(null);
  const [selectedExpansionId, setSelectedExpansionId] = useState<string | null>(null);
  const [focusOpen, setFocusOpen] = useState(false);
  const [focusZoomSignal, setFocusZoomSignal] = useState(0);
  const [focusHeight, setFocusHeight] = useState(600);
  const expansionJob = useExpansionJob();

  const runs = useMemo(() => {
    const data = (runsQuery.data ?? []).slice();
    data.sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
    const ids = data.map((run) => run.run_id);
    return [...new Set(ids)];
  }, [runsQuery.data]);

  // Restore the resumable Lab session on the client only (after mount). Reading
  // localStorage during the initial render would mismatch server HTML.
  useEffect(() => {
    const s = loadLabSession();
    if (s.runId !== undefined) {
      setRunId(s.runId ?? null);
      setGraphRunId(s.runId ?? null);
    }
    if (s.tab) setTab(s.tab);
    if (s.family) setFamily(s.family);
    if (s.graphProjection) setGraphProjection(s.graphProjection);
    if (s.graphLayerIndex !== undefined) setGraphLayerIndex(s.graphLayerIndex);
    if (s.identity !== undefined) setIdentity(s.identity);
    if (s.annotation !== undefined) setAnnotation(s.annotation);
    setHydrated(true);
  }, []);

  // Persist Lab session state so the workspace is resumable (US-73-78). Gated on
  // `hydrated` so we don't overwrite the stored session with defaults before
  // the restore effect has run.
  useEffect(() => {
    if (!hydrated) return;
    saveLabSession({
      tab,
      family,
      runId,
      graphProjection,
      graphLayerIndex,
      identity,
      annotation,
    });
  }, [hydrated, tab, family, runId, graphProjection, graphLayerIndex, identity, annotation]);

  // Drop a persisted run filter that no longer exists (e.g. from a previous
  // dataset) so the graph doesn't silently render empty with no recovery.
  useEffect(() => {
    if (runs.length > 0 && runId && !runs.includes(runId)) {
      setRunId(null);
      setGraphRunId(null);
    }
  }, [runs, runId]);

  // Fullscreen focus mode: lock body scroll while open, exit on Escape, and
  // keep the embedded graph sized to the viewport.
  useEffect(() => {
    if (!focusOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFocusOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const measure = () =>
      setFocusHeight(Math.max(320, window.innerHeight - 190));
    measure();
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("resize", measure);
    };
  }, [focusOpen]);

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
    graphChannelIds,
    graphVideoIds,
    "either",
    graphProjection,
    { retry: 1 },
    graphLayerIndex ?? undefined,
    graphConnected ?? undefined,
    graphScraped ?? undefined,
    graphIncludeSubRuns || undefined,
    graphJobIds,
  );

  const hasActiveGraphFilters =
    graphRunId !== null ||
    graphChannelIds.length > 0 ||
    graphVideoIds.length > 0 ||
    graphJobIds.length > 0 ||
    graphLayerIndex !== null ||
    graphConnected !== null ||
    graphScraped !== null ||
    graphIncludeSubRuns;

  // The channel facet list must stay stable while channel filters are active:
  // a filtered graph response only carries facets for its own slice, so
  // deriving the picker from the filtered payload would shrink it to the
  // already-selected channel(s) and make multi-select impossible.
  const [unfilteredChannels, setUnfilteredChannels] = useState<ChannelFacet[]>(
    [],
  );
  useEffect(() => {
    if (graphChannelIds.length > 0) return;
    const next = graphQuery.data?.channels ?? [];
    if (next.length > 0) setUnfilteredChannels(next);
  }, [graphQuery.data, graphChannelIds]);
  const channelFacets =
    graphChannelIds.length > 0 && unfilteredChannels.length > 0
      ? unfilteredChannels
      : (graphQuery.data?.channels ?? []);

  const clearAllGraphFilters = () => {
    setRunId(null);
    setGraphRunId(null);
    setGraphChannelIds([]);
    setGraphVideoIds([]);
    setGraphJobIds([]);
    setGraphLayerIndex(null);
    setGraphConnected(null);
    setGraphScraped(null);
    setGraphIncludeSubRuns(false);
  };

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
    const channelId = graphChannelIds[0];
    if (!channelId) return;
    try {
      await scrapeChannelMutation.mutateAsync({
        channel_id: channelId,
        dedupe: true,
      });
      showToast(`Scrape queued for channel ${channelId}`, "success");
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
    // When no run scopes the slice, fall back to the videos currently visible
    // in the graph so the expansion still has a valid scope (fixes
    // "Expansion scope requires video_ids or run_id").
    const fallbackVideoIds: string[] =
      !scopeRunId && graphProjection === "video" && graphQuery.data
        ? (graphQuery.data as NetworkGraphPayload).nodes.map((n) => n.video_id)
        : [];
    setScrapeAllOpen(false);
    if (!scopeRunId && fallbackVideoIds.length === 0) {
      showToast(
        "Select a run or load videos into the graph before scraping the whole network",
        "error",
      );
      return;
    }
    await startExpansionJob(
      () =>
        scrapeExpansionAll({
          run_id: scopeRunId,
          video_ids: fallbackVideoIds,
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

  // Single source of truth for the graph's props so the inline tab view and
  // the fullscreen focus overlay always render the exact same slice with the
  // same handlers (state carries over between the two).
  const activeGraphProps = (): NetworkGraphProps | null => {
    if (!graphQuery.data) return null;
    const shared = {
      runs: graphQuery.data.runs,
      channels: channelFacets,
      selectedRun: graphRunId ?? runId ?? undefined,
      selectedChannel: graphChannelIds[0] ?? undefined,
      onRunChange: (v: string) => {
        setGraphRunId(v === "__all" ? null : v);
        if (v && v !== "__all") setRunId(v);
      },
      onChannelChange: (v: string) =>
        setGraphChannelIds((prev) =>
          v && v !== "__all"
            ? prev.includes(v)
              ? prev.filter((c) => c !== v)
              : [...prev, v]
            : [],
        ),
      onClearFilters: clearAllGraphFilters,
      onScrapeClick: (id: string) => openVideoScrapeDialog(id),
    };
    if (graphProjection === "channel") {
      const mapped = mapChannelGraphPayload(
        graphQuery.data as ChannelGraphPayload,
      );
      return { ...shared, nodes: mapped.nodes, links: mapped.links };
    }
    const mapped = mapGraphPayload(graphQuery.data as NetworkGraphPayload);
    return {
      ...shared,
      nodes: mapped.nodes,
      links: mapped.links,
      onOverlapClick: () => {
        setGraphVideoIds(mapped.nodes.map((n) => n.id));
        setTab("commenters");
      },
    };
  };
  const graphProps = activeGraphProps();

  // All video metadata for the currently visible network slice (client-side
  // export, independent of the server-side /network/export endpoint).
  const metadataNodes: ExportNode[] | null = useMemo(() => {
    if (graphProjection !== "video" || !graphQuery.data) return null;
    return (graphQuery.data as NetworkGraphPayload).nodes.map(
      (n): ExportNode => ({
        id: n.video_id,
        title: n.title,
        channel: n.channel_name ?? n.channel_id,
        channel_id: n.channel_id,
        kind: n.kind,
        in_degree: n.in_degree,
        out_degree: n.out_degree,
        views: n.views,
        likes: n.likes,
        duration: n.duration,
        community_id: n.community_id,
        recommendations_scraped: n.recommendations_scraped,
      }),
    );
  }, [graphProjection, graphQuery.data]);

  if (family === "audience") {
    return (
      <div className="space-y-4">
        <Card className="p-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Network family
              </Label>
              <FamilyToggle value={family} onChange={setFamily} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Scope (collection run)
              </Label>
              <RunPicker
                runs={runs}
                names={runNames}
                value={runId}
                placeholder="All runs"
                onChange={(value) => setRunId(value)}
              />
            </div>
          </div>
        </Card>
        <AudienceNetworkView runId={runId} />
      </div>
    );
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
              hideAllOption={tab === "layers"}
              onChange={(value) => {
                // Drive both the metrics/edges slice (runId) and the graph
                // slice (graphRunId) so a run chosen here actually filters the
                // network graph instead of only the metrics tab.
                setRunId(value);
                setGraphRunId(value || null);
              }}
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Family
            </Label>
            <FamilyToggle value={family} onChange={setFamily} />
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
          {metadataNodes ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                All video metadata
              </span>
              {(["csv", "json", "xlsx"] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() =>
                    exportVideoMetadata(
                      fmt,
                      metadataNodes,
                      `network-metadata-${runId ?? "all"}`,
                    )
                  }
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <Download className="size-3.5" aria-hidden />
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          ) : null}
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
          <TabsTrigger value="matrices">Matrices</TabsTrigger>
          <TabsTrigger value="sampling">Sampling</TabsTrigger>
          <TabsTrigger value="expansion">Expansion</TabsTrigger>
          <TabsTrigger value="channels">Channels</TabsTrigger>
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
              <CentralitiesPanel runId={runId} />
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
          <NetworkRolesPanel runId={runId} />
          <NetworkCommunityInsightsPanel runId={runId} />
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

              <ChannelMultiSelect
                channels={channelFacets}
                selected={graphChannelIds}
                onChange={setGraphChannelIds}
              />
              <VideoMultiSelect selected={graphVideoIds} onChange={setGraphVideoIds} />
              <JobMultiSelect
                jobs={(jobsQuery.data ?? []).map((j) => ({
                  job_id: j.job_id,
                  kind: j.kind,
                }))}
                selected={graphJobIds}
                onChange={setGraphJobIds}
              />

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

              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Run scope
                </Label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={graphIncludeSubRuns}
                    onCheckedChange={(v) => setGraphIncludeSubRuns(v === true)}
                    disabled={!graphRunId}
                    aria-label="Include sub-runs in the graph"
                  />
                  Include sub-runs
                </label>
                {graphRunId && (
                  <span className="text-xs text-muted-foreground">
                    {graphIncludeSubRuns
                      ? "Parent run + all descendant sub-runs"
                      : "Selected run only"}
                  </span>
                )}
              </div>

              {hasActiveGraphFilters ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAllGraphFilters}
                >
                  Clear all filters
                </Button>
              ) : null}

              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFocusOpen(true)}
                disabled={!graphProps}
                aria-label="Open fullscreen focus mode"
              >
                <Maximize2 aria-hidden />
                Focus
              </Button>
            </div>
            {graphQuery.data &&
            (
              (graphQuery.data as NetworkGraphPayload | ChannelGraphPayload)
                .nodes.length === 0
            ) &&
            hasActiveGraphFilters ? (
              <div className="flex items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                <span>
                  No network data for the current filters. The selection may point
                  to an empty or removed slice.
                </span>
                <Button variant="outline" size="sm" onClick={clearAllGraphFilters}>
                  Clear all filters
                </Button>
              </div>
            ) : null}
            {graphQuery.isError ? (
              <ErrorState
                message={
                  graphQuery.error instanceof Error
                    ? graphQuery.error.message
                    : "Failed to load network graph"
                }
                retry={() => graphQuery.refetch()}
              />
            ) : graphProps ? (
              <NetworkGraph {...graphProps} />
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
              {graphChannelIds[0] ? (
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
          <LayerPanel runId={runId ?? graphRunId} />
        </TabsContent>
        <TabsContent value="commenters" className="mt-4">
          <CommenterOverlapView
            initialVideoIds={graphVideoIds}
            initialChannelIds={graphChannelIds}
          />
        </TabsContent>
        <TabsContent value="matrices" className="mt-4">
          <NetworkMatrices runIds={graphRunId ? [graphRunId] : undefined} />
        </TabsContent>
        <TabsContent value="sampling" className="mt-4">
          <SamplingFeasibility
            defaultChannelId={graphChannelIds[0] ?? undefined}
            runIds={graphRunId ? [graphRunId] : undefined}
          />
        </TabsContent>
        <TabsContent value="expansion" className="mt-4">
          <ExpansionPanel
            selectedActionId={selectedExpansionId}
            onSelectAction={setSelectedExpansionId}
          />
        </TabsContent>
        <TabsContent value="channels" className="mt-4">
          <ChannelsPanel />
        </TabsContent>
      </Tabs>

      {focusOpen && graphProps ? (
        <div
          data-testid="network-focus-overlay"
          className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-background"
          role="dialog"
          aria-label="Fullscreen network focus mode"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-background px-4 py-2">
            <div className="space-y-0.5">
              <p className="text-sm font-medium">Network focus</p>
              <p className="text-xs text-muted-foreground">
                {graphProjection === "channel"
                  ? "Channel projection"
                  : "Video projection"}
                {graphRunId
                  ? ` · ${runNames.get(graphRunId) ?? graphRunId}`
                  : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFocusZoomSignal((s) => s + 1)}
              >
                <RotateCcw aria-hidden />
                Zoom reset
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFocusOpen(false)}
                autoFocus
              >
                <Minimize2 aria-hidden />
                Exit focus (Esc)
              </Button>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            <NetworkGraph
              {...graphProps}
              height={focusHeight}
              zoomResetSignal={focusZoomSignal}
            />
          </div>
        </div>
      ) : null}

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
  hideAllOption,
}: {
  runs: string[];
  names: Map<string, string>;
  value: string | null;
  placeholder: string;
  onChange: (value: string | null) => void;
  hideAllOption?: boolean;
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
        {hideAllOption ? null : <SelectItem value="">{placeholder}</SelectItem>}
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
      if (deg !== 0) return deg;
      return String(a.id ?? "").localeCompare(String(b.id ?? ""));
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
              {/* Cap rendered rows: with corpus-sized graphs (thousands of
                  nodes) an unvirtualized table made every re-render of the Lab
                  freeze the main thread for seconds. The badge keeps the true
                  total; the top-of-list ordering is by degree, so the cap only
                  trims the tail. */}
              {sorted.slice(0, NODE_LIST_RENDER_CAP).map((node) => (
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

type ChannelFacetLike = { channel_id: string; channel_name?: string | null };

type JobFacetLike = { job_id: string; kind?: string | null };

function JobMultiSelect({
  jobs,
  selected,
  onChange,
}: {
  jobs: JobFacetLike[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const list = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter(
      (j) => j.job_id.toLowerCase().includes(q) || (j.kind ?? "").toLowerCase().includes(q),
    );
  }, [jobs, search]);

  const toggle = (id: string) =>
    onChange(
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button variant="outline" size="sm" className="gap-1" />
        }
      >
        Jobs{selected.length ? ` (${selected.length})` : ""}
      </PopoverTrigger>
      <PopoverContent className="w-80 p-2" align="start">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search jobs…"
          className="mb-2"
          aria-label="Search jobs"
        />
        <div className="max-h-64 overflow-y-auto">
          {list.length === 0 ? (
            <div className="p-2 text-xs text-muted-foreground">No jobs</div>
          ) : (
            list.map((j) => (
              <label
                key={j.job_id}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted"
              >
                <Checkbox
                  checked={selected.includes(j.job_id)}
                  onCheckedChange={() => toggle(j.job_id)}
                />
                <span className="truncate font-mono text-xs">
                  {j.job_id}
                </span>
                <span className="ml-auto text-[10px] uppercase text-muted-foreground">
                  {j.kind ?? ""}
                </span>
              </label>
            ))
          )}
        </div>
        {selected.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1 border-t pt-2">
            {selected.map((id) => (
              <Badge
                key={id}
                variant="secondary"
                className="gap-1 font-mono"
              >
                {id.length > 16 ? `${id.slice(0, 16)}…` : id}
                <button
                  type="button"
                  aria-label={`Remove ${id}`}
                  className="ml-0.5 rounded hover:bg-background/60"
                  onClick={() => toggle(id)}
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

/** Max rows rendered in the (unvirtualized) node list table. */
const NODE_LIST_RENDER_CAP = 200;

function ChannelMultiSelect({
  channels,
  selected,
  onChange,
}: {
  channels: ChannelFacetLike[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const list = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return channels;
    return channels.filter((c) => {
      const name = (c.channel_name ?? c.channel_id ?? "").toLowerCase();
      const id = (c.channel_id ?? "").toLowerCase();
      return name.includes(q) || id.includes(q);
    });
  }, [channels, search]);

  const toggle = (id: string) =>
    onChange(
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button variant="outline" size="sm" className="gap-1" />
        }
      >
        Channels{selected.length ? ` (${selected.length})` : ""}
      </PopoverTrigger>
      <PopoverContent className="w-80 p-2" align="start">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search channels…"
          className="mb-2"
          aria-label="Search channels"
        />
        <div className="max-h-64 overflow-y-auto">
          {list.length === 0 ? (
            <div className="p-2 text-xs text-muted-foreground">No channels</div>
          ) : (
            list.map((c) => (
              <label
                key={c.channel_id}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted"
              >
                <Checkbox
                  checked={selected.includes(c.channel_id)}
                  onCheckedChange={() => toggle(c.channel_id)}
                />
                <span className="truncate">
                  {c.channel_name ?? c.channel_id}
                </span>
              </label>
            ))
          )}
        </div>
        {selected.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1 border-t pt-2">
            {selected.map((id) => (
              <Badge
                key={id}
                variant="secondary"
                className="gap-1 font-mono"
              >
                {id.length > 16 ? `${id.slice(0, 16)}…` : id}
                <button
                  type="button"
                  aria-label={`Remove ${id}`}
                  className="ml-0.5 rounded hover:bg-background/60"
                  onClick={() => toggle(id)}
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

function VideoMultiSelect({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [text, setText] = useState("");

  const add = () => {
    const ids = text
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.length) {
      onChange(Array.from(new Set([...selected, ...ids])));
    }
    setText("");
  };

  const remove = (id: string) =>
    onChange(selected.filter((x) => x !== id));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Videos
      </Label>
      <Input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add();
          }
        }}
        placeholder="Add video IDs (comma/space)…"
        className="w-60"
        aria-label="Add video IDs"
      />
      <Button variant="outline" size="sm" onClick={add}>
        Add
      </Button>
      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {selected.map((id) => (
            <Badge
              key={id}
              variant="secondary"
              className="gap-1 font-mono"
            >
              {id.length > 16 ? `${id.slice(0, 16)}…` : id}
              <button
                type="button"
                aria-label={`Remove ${id}`}
                className="ml-0.5 rounded hover:bg-background/60"
                onClick={() => remove(id)}
              >
                ×
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}
