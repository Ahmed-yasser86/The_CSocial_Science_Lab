"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingState } from "@/components/features/state";
import { useLayerRelations } from "@/services/networkLayer";
import { COUNT_LABELS } from "@/lib/network-layer-types";
import type { ComponentSummary } from "@/lib/network-layer-types";

const TILE_KEYS = [
  "new_videos",
  "new_channels",
  "new_edges",
  "edges_connecting_to_existing_nodes",
  "new_components",
  "connected_components",
  "comments_collected",
] as const;

function ComponentChips({
  label,
  components,
  tone,
  highlighted,
  onToggle,
}: {
  label: string;
  components: ComponentSummary[];
  tone: "connected" | "disconnected";
  highlighted: string[] | null;
  onToggle: (component: ComponentSummary) => void;
}) {
  if (components.length === 0) return null;
  return (
    <div>
      <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label} ({components.length})
      </h4>
      <div className="flex flex-wrap gap-1.5">
        {components.map((component) => {
          const active = highlighted?.includes(component.component_id) ?? false;
          return (
            <button
              key={component.component_id}
              type="button"
              aria-pressed={active}
              onClick={() => onToggle(component)}
              title={`${component.node_count} node(s), ${component.edge_count} edge(s)`}
              className={
                tone === "connected"
                  ? "inline-flex items-center gap-1.5 rounded-md border border-emerald-600/40 bg-emerald-50 px-2.5 py-1 text-xs outline-none hover:bg-emerald-100 focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:ring-2 aria-pressed:ring-emerald-600"
                  : "inline-flex items-center gap-1.5 rounded-md border border-amber-600/40 bg-amber-50 px-2.5 py-1 text-xs outline-none hover:bg-amber-100 focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:ring-2 aria-pressed:ring-amber-600"
              }
            >
              {active ? "✓ " : ""}
              <code>{component.component_id.slice(0, 18)}…</code>
              <span className="opacity-70">{component.node_count}n</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function NewRelationsPanel({
  layerRunId,
  highlighted,
  onHighlight,
}: {
  layerRunId: string | null;
  highlighted: string[] | null;
  onHighlight: (videoIds: string[] | null) => void;
}) {
  const relationsQuery = useLayerRelations(layerRunId);

  if (!layerRunId) return null;

  if (relationsQuery.isError) {
    return (
      <ErrorState
        message={
          relationsQuery.error instanceof Error
            ? relationsQuery.error.message
            : "Failed to load layer relations"
        }
        retry={() => relationsQuery.refetch()}
      />
    );
  }
  if (!relationsQuery.data) {
    return <LoadingState label="Loading layer relations…" />;
  }

  const report = relationsQuery.data;
  const counts = report.counts;

  function toggleHighlight(component: ComponentSummary) {
    if (highlighted?.includes(component.component_id)) {
      onHighlight(null);
    } else {
      onHighlight(component.node_video_ids);
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-medium">What layer {report.layer_index} added</h3>
        {report.new_videos.length ? (
          <Badge variant="outline">{report.new_videos.length} new video(s)</Badge>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {TILE_KEYS.map((key) => (
          <div
            key={key}
            className="rounded-lg border border-border bg-muted/40 px-3 py-2"
          >
            <div className="text-lg font-semibold tabular-nums">
              {counts[key] ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">
              {COUNT_LABELS[key] ?? key}
            </div>
          </div>
        ))}
      </div>

      {report.new_channels.length ? (
        <div className="mt-4">
          <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            New channels ({report.new_channels.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {report.new_channels.map((channel) => (
              <Badge key={channel.channel_id} variant="outline">
                {channel.channel_name ?? channel.channel_id}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {report.new_videos.length ? (
        <div className="mt-4">
          <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            New videos ({report.new_videos.length})
          </h4>
          <ul className="max-h-48 space-y-1 overflow-y-auto">
            {report.new_videos.map((video) => (
              <li key={video.video_id} className="flex items-center gap-2 text-xs">
                {video.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={video.thumbnail_url}
                    alt=""
                    width={40}
                    height={23}
                    className="h-6 w-10 shrink-0 rounded object-cover"
                  />
                ) : null}
                <span className="truncate">{video.title ?? video.video_id}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        <ComponentChips
          label="Connected components"
          components={report.connected_components}
          tone="connected"
          highlighted={highlighted}
          onToggle={toggleHighlight}
        />
        <ComponentChips
          label="Disconnected / new communities"
          components={report.disconnected_components}
          tone="disconnected"
          highlighted={highlighted}
          onToggle={toggleHighlight}
        />
        {highlighted ? (
          <button
            type="button"
            onClick={() => onHighlight(null)}
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Clear component highlight
          </button>
        ) : null}
      </div>
    </Card>
  );
}
