"use client";

import { useState } from "react";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, LoadingState } from "@/components/features/state";
import { useRuns } from "@/services/queries";
import {
  useBootstrapLayer,
  useCrawlNextLayer,
  useLayers,
} from "@/services/networkLayer";
import type { LayerProjection } from "@/lib/network-layer-types";

export function LayerStepper({
  selectedLayerRunId,
  onSelectLayer,
  projection,
  onProjectionChange,
  collectComments,
  onCollectCommentsChange,
  crawl,
  onStartCrawl,
}: {
  selectedLayerRunId: string | null;
  onSelectLayer: (layerRunId: string) => void;
  projection: LayerProjection;
  onProjectionChange: (projection: LayerProjection) => void;
  collectComments: boolean;
  onCollectCommentsChange: (collect: boolean) => void;
  crawl: ReturnType<typeof useCrawlNextLayer>;
  onStartCrawl: (body: {
    parent_layer_run_id: string;
    projection: LayerProjection;
    collect_comments: boolean;
  }) => void;
}) {
  const layersQuery = useLayers();
  const runsQuery = useRuns();
  const bootstrapMutation = useBootstrapLayer();
  const [bootstrapRunId, setBootstrapRunId] = useState<string>("");

  const layers = [...(layersQuery.data ?? [])].sort(
    (a, b) => a.layer_index - b.layer_index,
  );
  const runs = runsQuery.data ?? [];

  const selectedLayer =
    layers.find((layer) => layer.layer_run_id === selectedLayerRunId) ??
    layers[layers.length - 1];

  const isCrawling = crawl.isPending || crawl.isRunning;

  async function handleBootstrap() {
    if (!bootstrapRunId) return;
    try {
      const layer = await bootstrapMutation.mutateAsync({
        runId: bootstrapRunId,
        projection,
      });
      onSelectLayer(layer.layer_run_id);
    } catch {
      // error surfaced through mutation state
    }
  }

  async function handleCrawlNext() {
    if (!selectedLayer) return;
    onStartCrawl({
      parent_layer_run_id: selectedLayer.layer_run_id,
      projection,
      collect_comments: collectComments,
    });
  }

  if (layersQuery.isLoading && !layersQuery.data) {
    return (
      <Card className="p-4">
        <LoadingState label="Loading layers…" />
      </Card>
    );
  }

  if (layers.length === 0) {
    return (
      <Card className="p-4">
        <EmptyState
          title="No crawl layers yet"
          description="Bootstrap a seed layer from an existing run, then crawl the recommendation network layer by layer."
          className="mb-4"
        />
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Seed run
            </Label>
            <Select
              value={bootstrapRunId}
              onValueChange={(next) => setBootstrapRunId(next ?? "")}
            >
              <SelectTrigger className="w-80" aria-label="Select seed run">
                <SelectValue placeholder="Pick a run to start from" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((run) => (
                  <SelectItem key={run.run_id} value={run.run_id}>
                    {run.name ?? run.run_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() => void handleBootstrap()}
            disabled={!bootstrapRunId || bootstrapMutation.isPending}
          >
            {bootstrapMutation.isPending ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Plus aria-hidden />
            )}
            Bootstrap layer 0
          </Button>
        </div>
        {bootstrapMutation.isError ? (
          <p className="mt-2 text-xs text-destructive">
            {(bootstrapMutation.error as Error).message}
          </p>
        ) : null}
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Layers
          </Label>
          {layers.map((layer) => (
            <button
              key={layer.layer_run_id}
              type="button"
              aria-pressed={selectedLayer?.layer_run_id === layer.layer_run_id}
              onClick={() => onSelectLayer(layer.layer_run_id)}
              className="rounded-md border border-border px-2.5 py-1 text-xs outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-primary aria-pressed:text-primary-foreground"
            >
              Layer {layer.layer_index}
              {layer.layer_index === 0 ? " (seed)" : null}
            </button>
          ))}
        </div>
      </div>

      {selectedLayer ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">
            {selectedLayer.discovered_video_ids.length} discovered
          </Badge>
          <Badge variant="outline">
            {selectedLayer.frontier_video_ids.length} frontier
          </Badge>
          <Badge variant="outline">
            {selectedLayer.run_ids.length} run(s)
          </Badge>
          <Badge variant="outline">
            {selectedLayer.comments_collected} comment(s)
          </Badge>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-end gap-4 border-t pt-4">
        <div className="space-y-1.5">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Projection
          </Label>
          <Select
            value={projection}
            onValueChange={(next) =>
              onProjectionChange((next ?? "video") as LayerProjection)
            }
          >
            <SelectTrigger className="w-44" aria-label="Select graph projection">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="video">Video graph</SelectItem>
              <SelectItem value="channel">Channel graph</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <label className="flex items-center gap-2 pb-1.5 text-sm">
          <Checkbox
            checked={collectComments}
            onCheckedChange={(value) => onCollectCommentsChange(value === true)}
          />
          Collect comments for new videos
        </label>

        <Button
          onClick={() => void handleCrawlNext()}
          disabled={isCrawling || !selectedLayer}
        >
          {isCrawling ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Sparkles aria-hidden />
          )}
          {isCrawling ? "Crawling layer…" : `Crawl next layer`}
        </Button>
      </div>

      {crawl.isError ? (
        <p className="mt-2 text-xs text-destructive">
          {(crawl.error as Error).message}
        </p>
      ) : null}
    </Card>
  );
}
