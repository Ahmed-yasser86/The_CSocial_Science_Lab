export type LabTab =
  | "metrics"
  | "insights"
  | "temporal"
  | "edges"
  | "graph"
  | "layers"
  | "commenters"
  | "expansion"
  | "matrices"
  | "sampling"
  | "channels";

export type GraphProjection = "video" | "channel";

export interface LabSession {
  tab: LabTab;
  runId: string | null;
  graphProjection: GraphProjection;
  graphLayerIndex: number | null;
  identity: string;
  annotation: string;
  /** Nominal canvas node diameter preference in px (bounded 5..40). */
  graphNodeSize: number;
}

export const GRAPH_NODE_SIZE_MIN = 5;
export const GRAPH_NODE_SIZE_MAX = 40;
/** Default reproduces the historical node radius band (6..18px). */
export const GRAPH_NODE_SIZE_DEFAULT = 24;

/** Clamp an arbitrary stored value into the supported node-size range. */
export function normalizeGraphNodeSize(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return GRAPH_NODE_SIZE_DEFAULT;
  return Math.min(
    GRAPH_NODE_SIZE_MAX,
    Math.max(GRAPH_NODE_SIZE_MIN, Math.round(n)),
  );
}

const STORAGE_KEY = "ssr-lab-session";

/** Resolve a usable Storage, falling back to an in-memory map when the
 *  environment has no working localStorage (SSR, jsdom stub, private mode). */
function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    const s = window.localStorage;
    s.setItem("__ssr_probe__", "1");
    s.removeItem("__ssr_probe__");
    return s;
  } catch {
    return null;
  }
}

const memory = new Map<string, string>();

function readRaw(): string | null {
  const s = getStorage();
  if (s) {
    try {
      return s.getItem(STORAGE_KEY);
    } catch {
      /* fall through to memory */
    }
  }
  return memory.get(STORAGE_KEY) ?? null;
}

function writeRaw(value: string): void {
  const s = getStorage();
  if (s) {
    try {
      s.setItem(STORAGE_KEY, value);
      return;
    } catch {
      /* fall through to memory */
    }
  }
  memory.set(STORAGE_KEY, value);
}

function removeRaw(): void {
  const s = getStorage();
  if (s) {
    try {
      s.removeItem(STORAGE_KEY);
      return;
    } catch {
      /* fall through to memory */
    }
  }
  memory.delete(STORAGE_KEY);
}

export function loadLabSession(): Partial<LabSession> {
  try {
    const raw = readRaw();
    return raw ? (JSON.parse(raw) as Partial<LabSession>) : {};
  } catch {
    return {};
  }
}

export function saveLabSession(patch: Partial<LabSession>): LabSession {
  const next: LabSession = { ...defaultLabSession(), ...loadLabSession(), ...patch };
  writeRaw(JSON.stringify(next));
  return next;
}

export function clearLabSession(): void {
  removeRaw();
}

export function defaultLabSession(): LabSession {
  return {
    tab: "metrics",
    runId: null,
    graphProjection: "video",
    graphLayerIndex: null,
    identity: "",
    annotation: "",
    graphNodeSize: GRAPH_NODE_SIZE_DEFAULT,
  };
}

export interface LabPreset {
  id: string;
  label: string;
  description: string;
  patch: Partial<LabSession>;
}

/** Layout presets are starting points, not constraints (US-73-78 foundation). */
export const LAB_PRESETS: LabPreset[] = [
  {
    id: "explore",
    label: "Explore",
    description: "Video graph with the force-directed canvas.",
    patch: { tab: "graph", graphProjection: "video" },
  },
  {
    id: "echo",
    label: "Echo-chamber",
    description: "Commenter overlap across channels.",
    patch: { tab: "commenters" },
  },
  {
    id: "channels",
    label: "Channels",
    description: "Channel-level projection of the network.",
    patch: { tab: "graph", graphProjection: "channel" },
  },
  {
    id: "insights",
    label: "Insights",
    description: "Auto-generated research insights.",
    patch: { tab: "insights" },
  },
  {
    id: "matrices",
    label: "Matrices",
    description: "Structural matrices (community + layers).",
    patch: { tab: "matrices" },
  },
  {
    id: "layers",
    label: "Layers",
    description: "Recommendation-expansion crawl layers.",
    patch: { tab: "layers" },
  },
  {
    id: "sampling",
    label: "Sampling",
    description: "Pre-sample feasibility planning (US-32/33).",
    patch: { tab: "sampling" },
  },
];

export function presetById(id: string): LabPreset | undefined {
  return LAB_PRESETS.find((p) => p.id === id);
}
