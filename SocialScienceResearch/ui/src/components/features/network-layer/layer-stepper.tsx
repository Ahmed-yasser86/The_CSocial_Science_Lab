"use client";

import { useEffect, useState } from "react";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, LoadingState } from "@/components/features/state";
import { formatJobStage } from "@/components/features/job-progress-card";
import { useRuns } from "@/services/queries";
import {
  useBootstrapLayer,
  useCrawlNextLayer,
  useLayers,
} from "@/services/networkLayer";
import { formatNumber } from "@/lib/format";
import type { LayerProjection } from "@/lib/network-layer-types";

export function LayerStepper({
  selectedLayerRunId,
  onSelectLayer,
  runId,
  projection,
  onProjectionChange,
  collectComments,
  onCollectCommentsChange,
  crawl,
  onStartCrawl,
}: {
  selectedLayerRunId: string | null;
  onSelectLayer: (layerRunId: string) => void;
  runId?: string | null;
  projection: LayerProjection;
  onProjectionChange: (projection: LayerProjection) => void;
  collectComments: boolean;
  onCollectCommentsChange: (collect: boolean) => void;
  crawl: ReturnType<typeof useCrawlNextLayer>;
  onStartCrawl: (body: {
    parent_layer_run_id: string;
    projection: LayerProjection;
    collect_comments: boolean;
    max_recommendations_per_video?: number;
  }) => void;
}) {
  const layersQuery = useLayers(runId);
  const runsQuery = useRuns();
  const bootstrapMutation = useBootstrapLayer();
  const [bootstrapRunId, setBootstrapRunId] = useState<string>("");
  const [maxRecsPerVideo, setMaxRecsPerVideo] = useState<string>("");

  // When the Lab scopes the Layer tab to a specific run, drive the bootstrap
  // seed run from that selection so "Bootstrap layer 0" builds the run's own
  // layer family instead of forcing the researcher to pick again.
  useEffect(() => {
    if (runId) setBootstrapRunId(runId);
  }, [runId]);

  const layers = [...(layersQuery.data ?? [])].sort(
    (a, b) => a.layer_index - b.layer_index,
  );
  const runs = runsQuery.data ?? [];

  // Disambiguate layers that share an index (e.g. two crawls of the same
  // parent) so the tab bar doesn't show two identical "Layer 1" buttons.
  const indexCounts = new Map<number, number>();
  for (const layer of layers) {
    indexCounts.set(
      layer.layer_index,
      (indexCounts.get(layer.layer_index) ?? 0) + 1,
    );
  }

  const selectedLayer =
    layers.find((layer) => layer.layer_run_id === selectedLayerRunId) ??
    layers[0];

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
    const trimmed = maxRecsPerVideo.trim();
    const parsed =
      trimmed === "" ? undefined : Math.max(1, Math.floor(Number(trimmed)));
    onStartCrawl({
      parent_layer_run_id: selectedLayer.layer_run_id,
      projection,
      collect_comments: collectComments,
      max_recommendations_per_video:
        parsed !== undefined && !Number.isNaN(parsed) ? parsed : undefined,
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
    const scopeName =
      runsQuery.data?.find((r) => r.run_id === runId)?.name ?? runId;
    return (
      <Card className="p-4">
        <EmptyState
          title={
            runId
              ? `No crawl layers for this run yet`
              : "No crawl layers yet"
          }
          description={
            runId
              ? `Bootstrap a seed layer from ${scopeName ?? runId} to start crawling its recommendation network.`
              : "Bootstrap a seed layer from an existing run, then crawl the recommendation network layer by layer."
          }
          className="mb-4"
        />
        <div className="flex flex-wrap items-end gap-3">
          {runId ? (
            <Badge variant="outline" className="font-mono">
              {scopeName ?? runId}
            </Badge>
          ) : (
            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Seed run
              </Label>
              <Select
                value={bootstrapRunId || undefined}
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
          )}
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
              {indexCounts.get(layer.layer_index) &&
              indexCounts.get(layer.layer_index)! > 1
                ? ` · ${layer.layer_run_id.slice(0, 4)}`
                : null}
            </button>
          ))}
        </div>
      </div>

      {selectedLayer ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-muted-foreground">
            {selectedLayer.layer_index === 0 ? (
              <>Seed layer built from </>
            ) : (
              <>Layer {selectedLayer.layer_index} expands the frontier of </>
            )}
            <span className="font-medium text-foreground">
              {runs.find((r) => r.run_id === selectedLayer.parent_run_id)?.name ??
                selectedLayer.parent_run_id ??
                "an unknown run"}
            </span>
            {selectedLayer.layer_index > 0 ? (
              <> &mdash; {selectedLayer.frontier_video_ids.length} frontier video(s) &rarr; {selectedLayer.discovered_video_ids.length} enriched</>
            ) : null}
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">
              {selectedLayer.discovered_video_ids.length} video(s) enriched
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
          {selectedLayer.frontier_video_ids.length === 0 ? (
            <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              This layer&rsquo;s frontier is empty &mdash; the seed run has no
              videos or recommendation edges to crawl from. Pick a run that has
              collected content to start a real layer.
            </p>
          ) : null}
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

        <div className="space-y-1.5">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Recs / video
          </Label>
          <Input
            type="number"
            min={1}
            max={2000}
            value={maxRecsPerVideo}
            onChange={(e) => setMaxRecsPerVideo(e.target.value)}
            placeholder="all"
            className="w-28"
            aria-label="Max recommendations to keep per frontier video (optional)"
          />
        </div>

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

      {isCrawling && crawl.job ? (
        <CrawlProgress job={crawl.job} />
      ) : isCrawling && crawl.isPending ? (
        <div className="mt-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />
          Submitting crawl job…
        </div>
      ) : null}
    </Card>
  );
}

function CrawlProgress({
  job,
}: {
  job: {
    status: string;
    progress?: {
      stage: string;
      discovered: number;
      succeeded: number;
      failed: number;
      message: string | null;
    } | null;
    message?: string | null;
  };
}) {
  const progress = job.progress;
  const discovered = progress?.discovered ?? 0;
  const succeeded = progress?.succeeded ?? 0;
  const failed = progress?.failed ?? 0;
  const pct =
    discovered > 0 ? Math.round(((succeeded + failed) / discovered) * 100) : 0;

  return (
    <div className="mt-3 space-y-2 rounded-md border border-primary/20 bg-primary/5 p-3">
      <div className="flex items-center gap-2 text-sm">
        <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />
        <span className="font-medium">
          {formatJobStage(progress?.stage)}
        </span>
      </div>
      {discovered > 0 ? (
        <>
          <Progress value={pct} className="h-1.5" />
          <p className="text-xs text-muted-foreground">
            {formatNumber(succeeded)} succeeded
            {failed > 0 ? `, ${formatNumber(failed)} failed` : ""} of{" "}
            {formatNumber(discovered)} target(s)
          </p>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">
          {progress?.message ?? "Working…"}
        </p>
      )}
    </div>
  );
}
