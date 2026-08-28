"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ExternalLink,
  FilterX,
  Loader2,
  Maximize2,
  Minus,
  Plus,
  Search,
  Sparkles,
  Users,
} from "lucide-react";
import { ErrorState, LoadingState } from "@/components/features/state";
import { CHART_VARS, resolveChartColors } from "@/lib/colors";
import { useTheme } from "@/lib/theme";
import { formatDuration, formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  ChannelFacet,
  CommenterDetail,
  GraphNodeKind,
  RunFacet,
} from "@/lib/network-full-types";
import {
  loadLabSession,
  normalizeGraphNodeSize,
  saveLabSession,
  GRAPH_NODE_SIZE_DEFAULT,
  GRAPH_NODE_SIZE_MAX,
  GRAPH_NODE_SIZE_MIN,
} from "@/lib/lab-session";

const ForceGraph2DImpl = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <LoadingState label="Rendering network…" />,
});

// react-force-graph-2d's published types omit the node drag callbacks that the
// library supports at runtime. Augment the component type locally (without
// weakening type-safety for the rest of the props) so drag handlers compile.
type ForceGraph2DDragProps = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onNodeDragStart?: (node: any) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onNodeDrag?: (node: any) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onNodeDragEnd?: (node: any) => void;
};
const ForceGraph2D = ForceGraph2DImpl as unknown as React.ComponentType<
  React.ComponentProps<typeof ForceGraph2DImpl> & ForceGraph2DDragProps
>;

export interface GraphNode {
  id: string;
  title?: string | null;
  channel?: string | null;
  channel_id?: string | null;
  thumbnail?: string | null;
  views?: number | null;
  likes?: number | null;
  duration?: number | null;
  kind: GraphNodeKind;
  in_degree: number;
  out_degree: number;
  run_ids?: string[];
  run_types?: string[];
  community_id?: number | null;
  recommendations_scraped?: boolean;
}

export interface GraphLink {
  source: string;
  target: string;
  position?: number | null;
  run_id?: string | null;
  run_type?: string | null;
  run_name?: string | null;
  title?: string | null;
  weight?: number;
}

export interface NetworkGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  height?: number;
  runs?: RunFacet[];
  channels?: ChannelFacet[];
  selectedRun?: string;
  selectedChannel?: string;
  onRunChange?: (runId: string) => void;
  onChannelChange?: (channelId: string) => void;
  onClearFilters?: () => void;
  /** Color nodes/edges by their run/layer (each run gets a distinct color). */
  colorMode?: "role" | "layer" | "community";
  /** When set, only the listed node ids stay fully opaque; the rest are dimmed
   * (used to isolate a community as a sub-graph). */
  highlightedNodeIds?: Set<string> | null;
  /** Opens the video's dedicated page. */
  onNavigate?: (videoId: string) => void;
  /** Queues a recommendation scrape for a single video (drawer action only). */
  onScrapeClick?: (videoId: string) => Promise<void>;
  /** Opens the commenter-overlap view scoped to a single video (drawer action only). */
  onOverlapClick?: (videoId: string) => void;
  /** Increment to re-fit the layout into view (used by fullscreen focus mode). */
  zoomResetSignal?: number;
  /** Fetches audience (commenter) detail for a node whose `kind` is "commenter".
   * When provided, clicking a commenter node opens a commenter-specific drawer
   * (their comments + the videos/channels they commented on) instead of the
   * generic video drawer. */
  loadCommenterDetail?: (handle: string) => Promise<CommenterDetail>;
  /** Controlled inspected-node id. When set, the drawer tracks this id instead
   * of internal click state (used to open the inspector from ranking rows). */
  inspectNodeId?: string | null;
  onInspectNodeChange?: (id: string | null) => void;
  /** Controlled community filter: when set to a community id, only nodes in that
   * community are shown (the rest are hidden). "all" shows everything. */
  communityId?: number | "all";
  /** Called whenever the community filter changes (keeps external controls in sync). */
  onCommunityIdChange?: (id: number | "all") => void;
}

const roleColors: Record<GraphNodeKind, string> = {
  source: CHART_VARS.accent,
  target: CHART_VARS.dim,
  both: CHART_VARS.accent2,
  other: CHART_VARS.faint,
  commenter: CHART_VARS.accent,
  video: CHART_VARS.accent2,
  channel: CHART_VARS.dim,
};

/** Fixed palette so each run/layer keeps a stable, distinct color. */
const RUN_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#9333ea",
  "#ea580c",
  "#0891b2",
  "#ca8a04",
  "#db2777",
  "#65a30d",
  "#4f46e5",
  "#0d9488",
  "#e11d48",
];

/** Module-level thumbnail cache: images are decoded once and reused across
 * frames. Creating a fresh Image() inside nodeCanvasObject (called per node
 * per animation frame) previously stalled the main thread on large graphs.
 */
const thumbnailCache = new Map<string, HTMLImageElement>();

function cachedThumbnail(url: string): HTMLImageElement | undefined {
  let img = thumbnailCache.get(url);
  if (!img) {
    img = new Image();
    img.crossOrigin = "anonymous";
    img.src = url;
    thumbnailCache.set(url, img);
  }
  return img.complete && img.naturalWidth > 0 ? img : undefined;
}

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/** Golden-angle spiral used to seed initial node positions.
 *
 * Nodes are fed in descending total-degree order, so the innermost spiral
 * slots (the visual center) are taken by the most connected videos. Hubs then
 * emerge as central nodes of the force layout instead of any single queried
 * video being pinned to the middle.
 */
function spiralSeed(
  index: number,
  radiusStep = 22,
): { x: number; y: number } {
  const angle = index * 2.39996323;
  const radius = Math.sqrt(index) * radiusStep;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

export function runColorFor(runId: string): string {
  return RUN_COLORS[hashString(runId) % RUN_COLORS.length];
}

/** Distinct colors for detected communities (indexed by community_id). */
const COMMUNITY_COLORS = [
  "#2563eb",
  "#16a34a",
  "#9333ea",
  "#ea580c",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#ca8a04",
  "#4f46e5",
  "#e11d48",
];

export function communityColorFor(communityId: number): string {
  return COMMUNITY_COLORS[communityId % COMMUNITY_COLORS.length];
}

function roleLabel(kind: GraphNodeKind): string {
  switch (kind) {
    case "source":
      return "Focus video";
    case "both":
      return "Recommends & recommended";
    case "target":
      return "Connected video";
    default:
      return "Other";
  }
}

function roleColor(
  kind: GraphNodeKind,
  colors: ReturnType<typeof resolveChartColors>,
): string {
  switch (kind) {
    case "source":
      return colors.accent;
    case "both":
      return colors.accent2;
    case "target":
      return colors.dim;
    default:
      return colors.faint;
  }
}

export interface GraphNodeFilter {
  search?: string;
  minDegree?: number;
  kinds?: GraphNodeKind[];
  communityId?: number | "all";
}

/** Label rendering policy: hover-only (default) or always-on. */
export type GraphLabelsMode = "hover" | "always";

const MIN_HIT_RADIUS = 9;

/** Decide whether a node's composite text label is drawn this frame.
 * Labels are hidden by default to declutter dense graphs; they appear for the
 * hovered node, for search-matched/selected nodes, and for every node when
 * the user opts into always-on labels. */
export function shouldDrawLabel(
  nodeId: string,
  opts: {
    mode?: GraphLabelsMode;
    hoveredId?: string | null;
    matchedIds?: ReadonlySet<string>;
  },
): boolean {
  if ((opts.mode ?? "hover") === "always") return true;
  if (opts.hoveredId != null && opts.hoveredId === nodeId) return true;
  return opts.matchedIds?.has(nodeId) ?? false;
}

/** Visual radius (canvas px at zoom 1) for a node of the given total degree.
 * `sizeScale` derives from the user's node-size preference; a scale of 1
 * reproduces the historical 6..18px radius band exactly. */
export function nodeVisualRadius(totalDegree: number, sizeScale = 1): number {
  const band = 6 + Math.min(12, Math.sqrt(Math.max(0, totalDegree)) * 2.5);
  return Math.max(2.5, band * sizeScale);
}

/** Pointer-area radius so small/overlapping nodes stay clickable: the effective
 * hit target is never narrower than ~14px regardless of rendered node size. */
export function nodeHitRadius(totalDegree: number, sizeScale = 1): number {
  return Math.max(MIN_HIT_RADIUS, nodeVisualRadius(totalDegree, sizeScale));
}

export function filterGraphNodes(
  nodes: GraphNode[],
  filter: GraphNodeFilter,
): GraphNode[] {
  const term = (filter.search ?? "").trim().toLowerCase();
  const minDegree = filter.minDegree ?? 0;
  const kinds = filter.kinds ?? [];
  const communityId = filter.communityId ?? "all";
  return nodes.filter((n) => {
    if (minDegree > 0 && n.in_degree + n.out_degree < minDegree) return false;
    if (kinds.length > 0 && !kinds.includes(n.kind)) return false;
    if (communityId !== "all" && n.community_id !== communityId) return false;
    if (term) {
      const haystack = [
        n.id,
        n.title ?? "",
        n.channel ?? "",
        n.channel_id ?? "",
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(term)) return false;
    }
    return true;
  });
}

export function NetworkGraph({
  nodes,
  links,
  height = 480,
  runs = [],
  channels = [],
  selectedRun,
  selectedChannel,
  onRunChange,
  onChannelChange,
  onClearFilters,
  colorMode: initialColorMode = "role",
  onNavigate,
  onScrapeClick,
  onOverlapClick,
  zoomResetSignal,
  highlightedNodeIds,
  loadCommenterDetail,
  inspectNodeId,
  onInspectNodeChange,
  communityId: controlledCommunityId,
  onCommunityIdChange,
}: NetworkGraphProps) {
  const { theme } = useTheme();
  const [colorMode, setColorMode] = useState<"role" | "layer" | "community">(initialColorMode);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- force-graph's ref type is generics-hostile
  const graphRef = useRef<any>(null);
  // Cached layout positions live in a ref (NOT state): feeding them back via
  // setState re-created `graphData`, which re-heats the simulation, which
  // fires onEngineStop again — an infinite render/engine loop that froze the
  // page on graphs with thousands of nodes.
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(
    new Map(),
  );
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [internalInspectId, setInternalInspectId] = useState<string | null>(null);
  // Support both internal click state and an externally-controlled inspected id
  // (so ranking rows can open the node inspector from outside the canvas).
  const inspectId = inspectNodeId !== undefined ? inspectNodeId : internalInspectId;
  function setInspectId(id: string | null) {
    if (inspectNodeId !== undefined) onInspectNodeChange?.(id);
    else setInternalInspectId(id);
  }
  const [scraping, setScraping] = useState(false);

  // Display preferences: node size is persisted in the lab session so it
  // survives reloads across Lab/ego/channel views; labels default to
  // hover-only. Restored post-mount to avoid a hydration mismatch.
  const [nodeSize, setNodeSize] = useState(GRAPH_NODE_SIZE_DEFAULT);
  const [labelsMode, setLabelsMode] = useState<GraphLabelsMode>("hover");

  useEffect(() => {
    const s = loadLabSession();
    if (s.graphNodeSize !== undefined) {
      setNodeSize(normalizeGraphNodeSize(s.graphNodeSize));
    }
  }, []);

  function updateNodeSize(value: number) {
    const next = Math.max(
      GRAPH_NODE_SIZE_MIN,
      Math.min(GRAPH_NODE_SIZE_MAX, value),
    );
    setNodeSize(next);
    saveLabSession({ graphNodeSize: next });
  }

  const nodeSizeScale = nodeSize / GRAPH_NODE_SIZE_DEFAULT;

  // eslint-disable-next-line react-hooks/exhaustive-deps -- theme intentionally forces a canvas recolor on toggle
  const canvasColors = useMemo(() => resolveChartColors(), [theme]);

  const [search, setSearch] = useState("");
  const [minDegree, setMinDegree] = useState(0);
  const [kinds, setKinds] = useState<GraphNodeKind[]>([]);
  const [communityIdState, setCommunityIdState] = useState<number | "all">("all");
  const communityId = controlledCommunityId ?? communityIdState;
  const setCommunityId = (id: number | "all") => {
    setCommunityIdState(id);
    onCommunityIdChange?.(id);
  };

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // Content keys: parents re-render frequently (polling, query status flips)
  // and recreate the nodes/links arrays each time. Keying the expensive memos
  // on payload CONTENT instead of array identity keeps `graphData` (and thus
  // the force simulation) stable across irrelevant re-renders — otherwise the
  // engine re-heats over and over and the page freezes on large graphs.
  const nodesKey = useMemo(() => nodes.map((n) => n.id).join("\n"), [nodes]);
  const linksKey = useMemo(
    () => links.map((l) => `${l.source}\u0000${l.target}`).join("\n"),
    [links],
  );

  // Nodes whose labels are always drawn in hover mode: the inspected (clicked)
  // node plus every node matching the active search term.
  const matchedLabelIds = useMemo(() => {
    const ids = new Set<string>();
    if (inspectId) ids.add(inspectId);
    if (search.trim()) {
      for (const n of filterGraphNodes(nodes, { search })) ids.add(n.id);
    }
    return ids;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- key on content, not array identity
  }, [nodesKey, search, inspectId]);

  const communities = useMemo(() => {
    const ids = new Set<number>();
    for (const n of nodes) if (n.community_id != null) ids.add(n.community_id);
    return [...ids].sort((a, b) => a - b);
  }, [nodes]);

  const hasActiveFilters =
    search.trim() !== "" || minDegree > 0 || kinds.length > 0 || communityId !== "all";

  const visibleNodes = useMemo(
    () =>
      filterGraphNodes(nodes, {
        search,
        minDegree,
        kinds,
        communityId,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- key on content, not array identity
    [nodesKey, search, minDegree, kinds, communityId],
  );

  const visibleLinks = useMemo(() => {
    const visible = new Set(visibleNodes.map((n) => n.id));
    return links.filter((l) => visible.has(l.source) && visible.has(l.target));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- key on content, not array identity
  }, [linksKey, visibleNodes]);

  function resetFilters() {
    setSearch("");
    setMinDegree(0);
    setKinds([]);
    setCommunityId("all");
  }

  function toggleKind(kind: GraphNodeKind) {
    setKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  }

  // Re-seed cached positions so toggling filters does not explode the layout.
  const graphData = useMemo(() => {
    const cached = positionsRef.current;
    const nodeMap = new Map(visibleNodes.map((n) => [n.id, n]));
    // Feed high-degree nodes first so the spiral seed (and thus the settled
    // force layout) keeps the most connected videos near the center.
    const ordered = [...visibleNodes].sort(
      (a, b) =>
        b.in_degree + b.out_degree - (a.in_degree + a.out_degree),
    );
    const positioned = ordered.map((n, index) => {
      const cachedPos = cached.get(n.id);
      const seed = spiralSeed(index);
      return {
        id: n.id,
        val: Math.max(2, Math.sqrt(n.in_degree + n.out_degree + 1) * 2),
        x: cachedPos?.x != null ? cachedPos.x : seed.x,
        y: cachedPos?.y != null ? cachedPos.y : seed.y,
      };
    });
    return {
      nodes: positioned,
      links: visibleLinks
        .filter((l) => nodeMap.has(l.source) && nodeMap.has(l.target))
        .map((l) => ({
          source: l.source,
          target: l.target,
          run_id: l.run_id ?? null,
        })),
    };
  }, [visibleNodes, visibleLinks]);

  function linkRunId(link: unknown): string | null {
    const runId = (link as { run_id?: string | null }).run_id;
    return runId ?? null;
  }

  /** Resolve a link's endpoint ids regardless of whether react-force-graph has
   * mutated source/target into node objects (it does after the first render). */
  function linkEndpointIds(link: unknown): [string, string] {
    const l = link as { source?: unknown; target?: unknown };
    const idOf = (v: unknown) =>
      v == null ? "" : typeof v === "object" ? String((v as { id?: unknown }).id ?? "") : String(v);
    return [idOf(l.source), idOf(l.target)];
  }

  function nodeColor(node: unknown): string {
    const id = (node as { id?: string }).id ?? "";
    const meta = nodeById.get(id);
    if (!meta) return canvasColors.ink;
    if (colorMode === "community" && meta.community_id != null) {
      return communityColorFor(meta.community_id);
    }
    if (colorMode === "layer" && meta.run_ids && meta.run_ids.length > 0) {
      return runColorFor(meta.run_ids[0]);
    }
    return roleColor(meta.kind, canvasColors);
  }

  function linkColor(link: unknown): string {
    if (highlightedNodeIds && highlightedNodeIds.size > 0) {
      const [s, t] = linkEndpointIds(link);
      if (!highlightedNodeIds.has(s) || !highlightedNodeIds.has(t)) {
        return "rgba(150,150,160,0.15)";
      }
    }
    if (colorMode === "layer") {
      const runId = linkRunId(link);
      if (runId) return runColorFor(runId);
    }
    if (colorMode === "community") {
      const sourceId = (link as { source?: string }).source ?? "";
      const meta = nodeById.get(sourceId);
      if (meta && meta.community_id != null) {
        return communityColorFor(meta.community_id);
      }
    }
    return canvasColors.link;
  }

  const hoveredNode = hoveredId ? nodeById.get(hoveredId) : undefined;
  const inspectedNode = inspectId ? nodeById.get(inspectId) : undefined;

  function handleHover(
    node: { id?: string | number; x?: number; y?: number } | null,
  ) {
    if (!node?.id) {
      setHoveredId(null);
      setTooltipPos(null);
      return;
    }
    setHoveredId(String(node.id));
    const screen = graphRef.current?.graph2ScreenCoords(
      node.x ?? 0,
      node.y ?? 0,
    );
    if (screen) setTooltipPos({ x: screen.x, y: screen.y });
  }

  function rememberPosition(node: {
    id?: string | number;
    x?: number;
    y?: number;
  }) {
    if (node?.id && node.x != null && node.y != null) {
      positionsRef.current.set(String(node.id), { x: node.x, y: node.y });
    }
  }

  // Camera (viewport) zoom controls, independent of per-node size. force-graph
  // exposes an absolute `zoom(k)` setter and a `zoom()` getter for the current
  // scale; we step multiplicatively so each click feels linear to the user.
  function currentZoom(): number {
    const z = graphRef.current?.zoom?.();
    return typeof z === "number" && z > 0 ? z : 1;
  }

  function zoomBy(factor: number) {
    const g = graphRef.current;
    if (!g?.zoom) return;
    g.zoom(Math.min(12, Math.max(0.15, currentZoom() * factor)), 250);
  }

  function zoomToFit() {
    graphRef.current?.zoomToFit?.(350, 48);
  }

  useEffect(() => {
    if (graphData.nodes.length === 0) return;
    const g = graphRef.current;
    if (!g) return;
    const charge = g.d3Force?.("charge");
    if (charge?.strength) charge.strength(-300);
    const link = g.d3Force?.("link");
    if (link?.distance) link.distance(110);
    if (link?.strength) link.strength(0.2);
  }, [graphData]);

  useEffect(() => {
    if (!zoomResetSignal) return;
    graphRef.current?.zoomToFit?.(350, 48);
  }, [zoomResetSignal]);

  async function handleScrape(videoId: string) {
    if (!onScrapeClick || scraping) return;
    setScraping(true);
    try {
      await onScrapeClick(videoId);
    } finally {
      setScraping(false);
    }
  }

  return (
    <div className="space-y-3">
      {runs.length > 0 || channels.length > 0 ? (
        <div className="flex flex-wrap items-center gap-3">
          {channels.length > 0 && (
            <Select
              value={selectedChannel ?? ""}
              onValueChange={(v) => onChannelChange?.(v || "__all")}
            >
              <SelectTrigger
                className="w-[220px]"
                aria-label="Filter by channel"
              >
                <SelectValue placeholder="All channels" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All channels</SelectItem>
                {channels.map((c) => (
                  <SelectItem key={c.channel_id} value={c.channel_id}>
                    {c.channel_name ?? c.channel_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {runs.length > 0 && (
            <Select
              value={selectedRun ?? ""}
              onValueChange={(v) => onRunChange?.(v || "__all")}
            >
              <SelectTrigger className="w-[240px]" aria-label="Filter by run">
                <SelectValue placeholder="All runs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All runs</SelectItem>
                {runs.map((r) => (
                  <SelectItem key={r.run_id} value={r.run_id}>
                    {[r.run_type, r.name, r.run_id]
                      .filter(Boolean)
                      .join(" · ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {runs.length > 0 && (
            <Select
              value={colorMode}
              onValueChange={(v) =>
                setColorMode(v as "role" | "layer" | "community")
              }
              items={[
                { value: "role", label: "Color by role" },
                { value: "layer", label: "Color by layer (run)" },
                { value: "community", label: "Color by community" },
              ]}
            >
              <SelectTrigger className="w-[190px]" aria-label="Color nodes and edges by">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="role">Color by role</SelectItem>
                <SelectItem value="layer">Color by layer (run)</SelectItem>
                <SelectItem value="community">Color by community</SelectItem>
              </SelectContent>
            </Select>
          )}

          {(selectedRun || selectedChannel) && (
            <div className="flex flex-wrap items-center gap-1.5">
              {selectedRun && (
                <Badge variant="outline" className="gap-1">
                  Run: {selectedRun}
                </Badge>
              )}
              {selectedChannel && (
                <Badge variant="outline" className="gap-1">
                  Channel:{" "}
                  {channels.find((c) => c.channel_id === selectedChannel)
                    ?.channel_name ?? selectedChannel}
                </Badge>
              )}
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onClearFilters?.()}
              >
                Clear
              </Button>
            </div>
          )}
        </div>
      ) : null}

      {nodes.length > 0 ? (
        <div className="rounded-md border bg-background/60 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Search className="size-3.5" aria-hidden />
              <span>
                Showing {visibleNodes.length} of {nodes.length} nodes
                {visibleLinks.length !== links.length
                  ? ` · ${visibleLinks.length} of ${links.length} edges`
                  : ""}
              </span>
            </div>
            {hasActiveFilters ? (
              <Button
                variant="ghost"
                size="xs"
                onClick={resetFilters}
                aria-label="Reset node filters"
              >
                <FilterX className="size-3.5" aria-hidden />
                Reset
              </Button>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="w-56">
              <Input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by id, title, channel…"
                aria-label="Search nodes"
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              Min degree
              <Input
                type="number"
                min={0}
                value={minDegree === 0 ? "" : String(minDegree)}
                onChange={(e) => {
                  const v = Number.parseInt(e.target.value, 10);
                  setMinDegree(Number.isNaN(v) || v < 0 ? 0 : v);
                }}
                className="w-16 text-xs"
                aria-label="Minimum degree"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              Node size
              <Input
                type="range"
                min={GRAPH_NODE_SIZE_MIN}
                max={GRAPH_NODE_SIZE_MAX}
                step={1}
                value={nodeSize}
                onChange={(e) => {
                  const v = Number.parseInt(e.target.value, 10);
                  if (!Number.isNaN(v)) updateNodeSize(v);
                }}
                className="w-24"
                aria-label="Node size in pixels"
              />
              <span className="tabular-nums">{nodeSize}px</span>
            </label>
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
              <Checkbox
                checked={labelsMode === "always"}
                onCheckedChange={(v) =>
                  setLabelsMode(v === true ? "always" : "hover")
                }
              />
              Labels
            </label>
            <div
              className="flex items-center gap-1"
              role="group"
              aria-label="Zoom the graph layout (camera)"
            >
              <Button
                variant="outline"
                size="xs"
                onClick={() => zoomBy(1 / 1.4)}
                aria-label="Zoom out"
                title="Zoom out"
              >
                <Minus className="size-3.5" aria-hidden />
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={zoomToFit}
                aria-label="Fit graph to view"
                title="Fit graph to view"
              >
                <Maximize2 className="size-3.5" aria-hidden />
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={() => zoomBy(1.4)}
                aria-label="Zoom in"
                title="Zoom in"
              >
                <Plus className="size-3.5" aria-hidden />
              </Button>
            </div>
            <div
              className="flex flex-wrap items-center gap-x-3 gap-y-1"
              role="group"
              aria-label="Filter by node kind"
            >
              {(["source", "target", "both", "other"] as GraphNodeKind[]).map(
                (kind) => (
                  <label
                    key={kind}
                    className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground"
                  >
                    <Checkbox
                      checked={kinds.includes(kind)}
                      onCheckedChange={() => toggleKind(kind)}
                    />
                    {roleLabel(kind)}
                  </label>
                ),
              )}
            </div>
            {communities.length > 0 ? (
              <Select
                value={String(communityId)}
                onValueChange={(v) =>
                  setCommunityId(
                    v == null || v === "all"
                      ? "all"
                      : Number.parseInt(v, 10),
                  )
                }
              >
                <SelectTrigger
                  className="h-8 w-44 text-xs"
                  aria-label="Filter by community"
                >
                  <SelectValue placeholder="All communities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All communities</SelectItem>
                  {communities.map((id) => (
                    <SelectItem key={id} value={String(id)}>
                      Community {id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>
        </div>
      ) : null}

      <div
        className="relative w-full overflow-hidden rounded-md border bg-muted/30"
        style={{ height }}
      >
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            backgroundColor="transparent"
            nodeRelSize={5}
            nodeVal={(d: unknown) => (d as { val?: number }).val ?? 2}
            nodeColor={nodeColor}
            nodeCanvasObject={(
              node: {
                id?: string | number;
                x?: number;
                y?: number;
                color?: string;
              },
              ctx: CanvasRenderingContext2D,
              globalScale: number,
            ) => {
              const id = String(node.id ?? "");
              const meta = nodeById.get(id);
              const base = nodeColor({ id });
              const radius = nodeVisualRadius(
                (meta?.in_degree ?? 0) + (meta?.out_degree ?? 0),
                nodeSizeScale,
              );

              ctx.beginPath();
              ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
              ctx.fillStyle = base;
              let nodeAlpha = hoveredId && hoveredId !== id ? 0.45 : 0.95;
              if (
                highlightedNodeIds &&
                highlightedNodeIds.size > 0 &&
                !highlightedNodeIds.has(id)
              ) {
                nodeAlpha = 0.12;
              }
              ctx.globalAlpha = nodeAlpha;
              ctx.fill();
              ctx.globalAlpha = 1;
              ctx.lineWidth = 1;
              ctx.strokeStyle = node.color ?? canvasColors.inkMuted;
              ctx.stroke();

              if (meta?.thumbnail) {
                const img = cachedThumbnail(meta.thumbnail);
                if (img) {
                  ctx.save();
                  ctx.beginPath();
                  ctx.arc(node.x ?? 0, node.y ?? 0, radius - 1, 0, 2 * Math.PI);
                  ctx.clip();
                  ctx.drawImage(
                    img,
                    (node.x ?? 0) - radius + 1,
                    (node.y ?? 0) - radius + 1,
                    (radius - 1) * 2,
                    (radius - 1) * 2,
                  );
                  ctx.restore();
                }
              }

              // Composite label: [ID] + Channel Name + Video Title. Drawn only
              // for the hovered/search-matched nodes unless labels are pinned
              // always-on via the Labels toggle.
              if (
                globalScale >= 1.1 &&
                shouldDrawLabel(id, {
                  mode: labelsMode,
                  hoveredId,
                  matchedIds: matchedLabelIds,
                })
              ) {
                const label = [
                  `[${id}]`,
                  meta?.channel ?? "",
                  meta?.title ?? "",
                ]
                  .filter(Boolean)
                  .join(" · ");
                ctx.font = "500 9px system-ui, sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = canvasColors.inkMuted;
                const textWidth = ctx.measureText(label).width;
                ctx.fillStyle = "rgba(255,255,255,0.7)";
                ctx.fillRect(
                  (node.x ?? 0) - textWidth / 2 - 3,
                  (node.y ?? 0) + radius + 3,
                  textWidth + 6,
                  13,
                );
                ctx.fillStyle = canvasColors.ink;
                ctx.fillText(
                  label,
                  node.x ?? 0,
                  (node.y ?? 0) + radius + 4,
                );
              }
            }}
            nodePointerAreaPaint={(
              node: { id?: string | number; x?: number; y?: number },
              color: string,
              ctx: CanvasRenderingContext2D,
            ) => {
              const id = String(node.id ?? "");
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(
                node.x ?? 0,
                node.y ?? 0,
                nodeHitRadius(
                  (nodeById.get(id)?.in_degree ?? 0) +
                    (nodeById.get(id)?.out_degree ?? 0),
                  nodeSizeScale,
                ),
                0,
                2 * Math.PI,
              );
              ctx.fill();
            }}
            linkColor={linkColor}
            linkWidth={1.2}
            cooldownTicks={220}
            d3VelocityDecay={0.86}
            onNodeClick={(d: unknown) => {
              const id = (d as { id?: string }).id;
              if (!id) return;
              setInspectId(id);
              setHoveredId(null);
              setTooltipPos(null);
            }}
            onNodeHover={handleHover}
            onNodeDragEnd={(node: {
              id?: string | number;
              x?: number;
              y?: number;
            }) => {
              const id = String(node?.id ?? "");
              // Treat a near-zero-travel drag as a click (trackpad jitter):
              // the pre-drag position is the last recorded layout position.
              const start = positionsRef.current.get(id);
              if (start) {
                const moved = Math.hypot(
                  (node.x ?? 0) - start.x,
                  (node.y ?? 0) - start.y,
                );
                if (moved < 3) setInspectId(id);
              }
              rememberPosition(node);
            }}
            onEngineStop={() => {
              graphData.nodes.forEach((n) =>
                rememberPosition(n as { id?: string; x?: number; y?: number }),
              );
              // Fit the spread-out layout into view so no node is stranded
              // outside the viewport after the simulation settles.
              graphRef.current?.zoomToFit?.(350, 48);
            }}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            {nodes.length > 0 ? (
              <>
                <span>No nodes match the current filters</span>
                <Button variant="outline" size="sm" onClick={resetFilters}>
                  <FilterX className="size-3.5" aria-hidden />
                  Reset filters
                </Button>
              </>
            ) : (
              <span>No network to render</span>
            )}
          </div>
        )}

        {hoveredNode && tooltipPos && (
          <div
            data-testid="network-graph-tooltip"
            className="pointer-events-none absolute z-10 w-64 rounded-md border bg-popover/95 p-3 text-sm text-popover-foreground shadow-md"
            style={{
              left: Math.min(tooltipPos.x + 14, Math.max(0, (height || 480) - 280)),
              top: tooltipPos.y + 14,
            }}
          >
            <div className="flex items-start gap-2">
              {hoveredNode.thumbnail ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={hoveredNode.thumbnail}
                  alt=""
                  className="size-10 shrink-0 rounded object-cover"
                />
              ) : null}
              <div className="min-w-0 space-y-1">
                <p className="break-words font-medium">
                  [{hoveredNode.id}]
                  {hoveredNode.channel ? (
                    <span className="ml-1 text-muted-foreground">
                      · {hoveredNode.channel}
                    </span>
                  ) : null}
                </p>
                {hoveredNode.title ? (
                  <p className="line-clamp-2 text-xs text-muted-foreground">
                    {hoveredNode.title}
                  </p>
                ) : null}
                <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                  <span>
                    {formatNumber(hoveredNode.views)} views
                  </span>
                  <span>{formatDuration(hoveredNode.duration)}</span>
                  <span>
                    →{hoveredNode.out_degree} · ←{hoveredNode.in_degree}
                  </span>
                </p>
                <a
                  href={`https://www.youtube.com/watch?v=${hoveredNode.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
                >
                  <ExternalLink className="size-3" aria-hidden />
                  Watch video
                </a>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {colorMode === "layer" && runs.length > 0 ? (
          <>
            {runs.map((r) => (
              <LegendItem key={r.run_id} color={runColorFor(r.run_id)} label={r.name ?? r.run_id} />
            ))}
            <span>Click a node to inspect it.</span>
          </>
        ) : colorMode === "community" ? (
          <>
            {Array.from(new Set(nodes.map((n) => n.community_id).filter((id): id is number => id != null)))
              .sort((a, b) => a - b)
              .map((id) => (
                <LegendItem key={id} color={communityColorFor(id)} label={`Community ${id}`} />
              ))}
            <span>Click a node to inspect it.</span>
          </>
        ) : (
          <>
            <LegendItem color={roleColors.source} label="Focus video" />
            <LegendItem color={roleColors.both} label="Recommends & recommended" />
            <LegendItem color={roleColors.target} label="Connected video" />
            <span>Click a node to inspect it.</span>
          </>
        )}
      </div>

      <Drawer
        open={!!inspectedNode}
        onOpenChange={(open) => {
          if (!open) setInspectId(null);
        }}
      >
        <DrawerContent side="right">
          {inspectedNode ? (
            inspectedNode.kind === "commenter" && loadCommenterDetail ? (
              <CommenterDetailDrawer
                handle={inspectedNode.id}
                loader={loadCommenterDetail}
              />
            ) : (
            <>
              <DrawerHeader>
                <DrawerTitle className="break-all">
                  [{inspectedNode.id}]
                </DrawerTitle>
                <DrawerDescription className="line-clamp-2">
                  {inspectedNode.title ?? "No title recorded"}
                </DrawerDescription>
              </DrawerHeader>
              <DrawerBody className="space-y-4">
                {inspectedNode.thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={inspectedNode.thumbnail}
                    alt={inspectedNode.title ?? inspectedNode.id}
                    className="aspect-video w-full rounded-md border object-cover"
                  />
                ) : null}

                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <Row label="Channel" value={inspectedNode.channel} />
                  <Row label="Kind" value={roleLabel(inspectedNode.kind)} />
                  <Row label="Views" value={formatNumber(inspectedNode.views)} />
                  <Row label="Duration" value={formatDuration(inspectedNode.duration)} />
                  <Row label="Out-degree" value={String(inspectedNode.out_degree)} />
                  <Row label="In-degree" value={String(inspectedNode.in_degree)} />
                </dl>

                {inspectedNode.run_types && inspectedNode.run_types.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {inspectedNode.run_types.map((t) => (
                      <Badge key={t} variant="secondary">
                        {t}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </DrawerBody>
              <div className="flex flex-col gap-2 border-t bg-muted/50 p-4">
                {onScrapeClick ? (
                  <Button
                    onClick={() => void handleScrape(inspectedNode.id)}
                    disabled={scraping}
                  >
                    {scraping ? (
                      <Loader2 className="animate-spin" aria-hidden />
                    ) : (
                      <Sparkles aria-hidden />
                    )}
                    Scrape recommendations
                  </Button>
                ) : null}
                {onOverlapClick ? (
                  <Button
                    variant="outline"
                    onClick={() => onOverlapClick(inspectedNode.id)}
                  >
                    <Users aria-hidden />
                    Commenter overlap
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  onClick={
                    onNavigate
                      ? () => onNavigate(inspectedNode.id)
                      : undefined
                  }
                  render={
                    onNavigate ? undefined : (
                      <Link href={`/network/videos/${inspectedNode.id}`} />
                    )
                  }
                  nativeButton={!!onNavigate}
                >
                  <ExternalLink aria-hidden />
                  Open video page
                </Button>
              </div>
            </>
          )) : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

/** Drawer body for an audience (commenter) node: shows the commenter's recent
 * comments and the videos/channels they commented on (fetched from the
 * `/network/commenters/{handle}/detail` endpoint). */
function CommenterDetailDrawer({
  handle,
  loader,
}: {
  handle: string;
  loader: (handle: string) => Promise<CommenterDetail>;
}) {
  const [state, setState] = useState<{
    status: "loading" | "ok" | "error";
    data?: CommenterDetail;
    error?: string;
  }>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    loader(handle)
      .then((d) => {
        if (!cancelled) setState({ status: "ok", data: d });
      })
      .catch((e) => {
        if (!cancelled)
          setState({
            status: "error",
            error: e instanceof Error ? e.message : "Failed to load commenter",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [handle, loader]);

  return (
    <>
      <DrawerHeader>
        <DrawerTitle className="break-all">
          {state.data?.label ?? handle}
        </DrawerTitle>
        <DrawerDescription className="line-clamp-2">
          Commenter · {state.data?.comment_count ?? 0} comments
        </DrawerDescription>
      </DrawerHeader>
      <DrawerBody className="space-y-4">
        {state.status === "loading" ? (
          <LoadingState label="Loading commenter…" />
        ) : state.status === "error" ? (
          <ErrorState message={state.error ?? "Failed to load commenter"} />
        ) : (
          <CommenterDetailBody detail={state.data!} />
        )}
      </DrawerBody>
    </>
  );
}

function CommenterDetailBody({ detail }: { detail: CommenterDetail }) {
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <Row label="Kind" value={detail.kind} />
        <Row label="Comments" value={String(detail.comment_count)} />
      </dl>

      <div>
        <h5 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Recent comments
        </h5>
        {detail.sampled_comments.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No sampled comments available.
          </p>
        ) : (
          <ul className="space-y-2">
            {detail.sampled_comments.map((c, i) => (
              <li key={i} className="rounded-md border border-border p-2 text-sm">
                <p className="line-clamp-3 text-foreground/90">{c.text}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {c.video_title ?? c.video_id}
                  {c.channel_title ? ` · ${c.channel_title}` : ""}
                  {c.is_author ? " · author" : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {detail.videos.length > 0 ? (
        <div>
          <h5 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Videos commented on
          </h5>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {detail.videos.slice(0, 8).map((v) => (
              <li key={v.video_id} className="truncate">
                {v.title ?? v.video_id} · {v.comment_count}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words text-right">{value || "—"}</dd>
    </>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="size-2.5 rounded-full border border-border"
        style={{ background: color }}
      />
      {label}
    </span>
  );
}