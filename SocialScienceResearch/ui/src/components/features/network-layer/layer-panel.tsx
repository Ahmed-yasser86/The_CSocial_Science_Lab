"use client";

import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { LayerStepper } from "@/components/features/network-layer/layer-stepper";
import { NewRelationsPanel } from "@/components/features/network-layer/new-relations-panel";
import { LayerGraph } from "@/components/features/network-layer/layer-graph";
import { ScraperConfigPanel } from "@/components/features/network-layer/scraper-config-panel";
import { NetworkGraph, type GraphLink, type GraphNode } from "@/components/features/network-graph";
import { useCrawlNextLayer, useLayers } from "@/services/networkLayer";
import { useNetworkGraph } from "@/services/networkFull";
import type { LayerProjection } from "@/lib/network-layer-types";
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

export function LayerPanel({ runId }: { runId?: string | null }) {
  const layersQuery = useLayers(runId);
  const crawl = useCrawlNextLayer();
  const [selectedLayerRunId, setSelectedLayerRunId] = useState<string | null>(null);
  const [projection, setProjection] = useState<LayerProjection>("video");
  const [collectComments, setCollectComments] = useState(true);
  const [highlightVideoIds, setHighlightVideoIds] = useState<string[] | null>(null);
  const [showFullNetwork, setShowFullNetwork] = useState(false);

  const layers = [...(layersQuery.data ?? [])].sort(
    (a, b) => a.layer_index - b.layer_index,
  );
  const defaultLayer = layers.length ? layers[0] : null;

  const selectedValid = layers.some(
    (layer) => layer.layer_run_id === selectedLayerRunId,
  );
  const effectiveSelectedLayerRunId =
    showFullNetwork
      ? null
      : selectedLayerRunId && selectedValid
        ? selectedLayerRunId
        : (defaultLayer?.layer_run_id ?? null);

  function handleStartCrawl(body: {
    parent_layer_run_id: string;
    projection: LayerProjection;
    collect_comments: boolean;
    max_recommendations_per_video?: number;
  }) {
    setSelectedLayerRunId(null);
    setShowFullNetwork(false);
    crawl.mutate(body, {
      onSuccess: (_data) => {
        layersQuery.refetch().then(({ data }) => {
          const sorted = [...(data ?? [])].sort(
            (a, b) => a.layer_index - b.layer_index,
          );
          if (sorted.length > 0) {
            setSelectedLayerRunId(sorted[sorted.length - 1].layer_run_id);
          }
        });
      },
    });
  }

  return (
    <div className="space-y-4">
      <LayerStepper
        selectedLayerRunId={effectiveSelectedLayerRunId}
        onSelectLayer={(id) => {
          setSelectedLayerRunId(id);
          setShowFullNetwork(false);
        }}
        runId={runId}
        projection={projection}
        onProjectionChange={setProjection}
        collectComments={collectComments}
        onCollectCommentsChange={setCollectComments}
        crawl={crawl}
        onStartCrawl={handleStartCrawl}
      />

      <ScraperConfigPanel />

      <Card className="p-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={showFullNetwork}
            onCheckedChange={(v) => setShowFullNetwork(v === true)}
          />
          Show full network (all connected videos in database)
        </label>
      </Card>

      {showFullNetwork ? (
        <FullNetworkGraph projection={projection} />
      ) : (
        <>
          <NewRelationsPanel
            layerRunId={effectiveSelectedLayerRunId}
            highlighted={highlightVideoIds}
            onHighlight={setHighlightVideoIds}
          />
          <LayerGraph
            layerRunId={effectiveSelectedLayerRunId}
            projection={projection}
            onProjectionChange={setProjection}
            highlightVideoIds={highlightVideoIds}
          />
        </>
      )}
    </div>
  );
}

function FullNetworkGraph({ projection }: { projection: LayerProjection }) {
  const graphQuery = useNetworkGraph(
    undefined, undefined, undefined, "either", projection,
  );

  const mapped = useMemo(() => {
    if (!graphQuery.data) return null;
    return mapVideoPayload(graphQuery.data as NetworkGraphPayload);
  }, [graphQuery.data]);

  if (graphQuery.isError) {
    return (
      <Card className="p-4">
        <p className="text-sm text-destructive">
          {graphQuery.error instanceof Error
            ? graphQuery.error.message
            : "Failed to load full network graph"}
        </p>
      </Card>
    );
  }

  if (!mapped) {
    return (
      <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading full network…
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">Full network (all connected videos)</h3>
      <NetworkGraph
        nodes={mapped.nodes}
        links={mapped.links}
        runs={graphQuery.data?.runs}
        channels={graphQuery.data?.channels}
      />
    </Card>
  );
}
