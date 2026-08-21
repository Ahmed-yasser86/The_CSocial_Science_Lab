"use client";

import { useState } from "react";
import { LayerStepper } from "@/components/features/network-layer/layer-stepper";
import { NewRelationsPanel } from "@/components/features/network-layer/new-relations-panel";
import { LayerGraph } from "@/components/features/network-layer/layer-graph";
import { useCrawlNextLayer, useLayers } from "@/services/networkLayer";
import type { LayerProjection } from "@/lib/network-layer-types";

export function LayerPanel() {
  const layersQuery = useLayers();
  const crawl = useCrawlNextLayer();
  const [selectedLayerRunId, setSelectedLayerRunId] = useState<string | null>(null);
  const [projection, setProjection] = useState<LayerProjection>("video");
  const [collectComments, setCollectComments] = useState(true);
  const [highlightVideoIds, setHighlightVideoIds] = useState<string[] | null>(null);

  const layers = [...(layersQuery.data ?? [])].sort(
    (a, b) => a.layer_index - b.layer_index,
  );
  const newest = layers.length ? layers[layers.length - 1] : null;

  // Fall back to the newest layer only while the list is still loading (initial
  // load, or right after a crawl is kicked off). Once the list has resolved we
  // keep the user's explicit selection so it isn't silently reverted.
  const selectedValid = layers.some(
    (layer) => layer.layer_run_id === selectedLayerRunId,
  );
  const effectiveSelectedLayerRunId =
    selectedValid || layersQuery.isLoading
      ? selectedLayerRunId
      : (newest?.layer_run_id ?? null);

  function handleStartCrawl(body: {
    parent_layer_run_id: string;
    projection: LayerProjection;
    collect_comments: boolean;
  }) {
    // Clear the selection so the panel auto-selects the newest layer once the
    // crawl job succeeds and the layer list refetches.
    setSelectedLayerRunId(null);
    crawl.mutate(body);
  }

  return (
    <div className="space-y-4">
      <LayerStepper
        selectedLayerRunId={effectiveSelectedLayerRunId}
        onSelectLayer={setSelectedLayerRunId}
        projection={projection}
        onProjectionChange={setProjection}
        collectComments={collectComments}
        onCollectCommentsChange={setCollectComments}
        crawl={crawl}
        onStartCrawl={handleStartCrawl}
      />

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
    </div>
  );
}
