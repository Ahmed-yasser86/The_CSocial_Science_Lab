"use client";

import { useEffect, useRef, useState } from "react";
import {
  CircleAlert,
  History,
  Play,
  RefreshCw,
  Square,
} from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { JobProgressCard } from "@/components/features/job-progress-card";
import {
  canContinue,
  shapeTimeline,
  statusLabel,
  VERDICT_CHIP_CLASSES,
  VERDICT_DESCRIPTIONS,
  VERDICT_LABELS,
  type EchoDetection,
  type EchoSignalStatus,
  type EchoTimelineRow,
  type EchoVerdict,
} from "@/lib/echo-chamber";
import { formatPercent } from "@/lib/format";
import {
  continueEchoChamber,
  detectEchoChamber,
  echoChamberKeys,
  listEchoDetections,
  stopEchoChamber,
  useEchoDetection,
} from "@/services/echoChamber";

const MAX_LAYERS_TOTAL = 10;

function SignalCell({
  label,
  value,
  status,
}: {
  label: string;
  value: number | null;
  status: EchoSignalStatus;
}) {
  if (status !== "available" || value === null) {
    return (
      <span
        className="text-xs text-muted-foreground"
        title={`${label}: not observed`}
      >
        not observed
      </span>
    );
  }
  return <span className="font-mono text-xs">{formatPercent(value)}</span>;
}

function VerdictBanner({ detection }: { detection: EchoDetection }) {
  const score = detection.score;
  const verdict: EchoVerdict =
    score?.verdict ?? (canContinue(detection) ? "inconclusive" : "inconclusive");
  const naturalStop =
    detection.status === "exhausted" || detection.status === "unsupported_stop";
  return (
    <Card data-testid="echo-verdict">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-3">
          <span
            data-testid="echo-verdict-chip"
            className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${VERDICT_CHIP_CLASSES[verdict]}`}
          >
            {VERDICT_LABELS[verdict]}
          </span>
          {score?.value != null ? (
            <span className="font-mono text-sm text-muted-foreground">
              score {score.value.toFixed(3)}
            </span>
          ) : null}
        </div>
        <CardDescription>{VERDICT_DESCRIPTIONS[verdict]}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {naturalStop ? (
          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {detection.status === "exhausted"
              ? "The frontier was exhausted: every reachable video's recommendations have been observed. This natural stop is distinct from a verdict."
              : "A crawled layer observed zero recommendation edges, so the crawl stopped honestly instead of inventing content."}
          </p>
        ) : null}
        <div className="overflow-hidden rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Component</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Effective weight</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(score?.components ?? []).map((component) => (
                <TableRow key={component.key}>
                  <TableCell className="text-sm">{component.label}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {component.status === "available" &&
                    component.value != null
                      ? formatPercent(component.value)
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {component.status === "available"
                      ? `${(component.weight_effective * 100).toFixed(1)}%`
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        component.status === "available"
                          ? "default"
                          : "outline"
                      }
                    >
                      {component.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="text-xs text-muted-foreground">
          All values are observed structural properties of the crawled
          recommendation graph around the seed. Nothing here claims anything
          about viewer beliefs or causation.
        </p>
      </CardContent>
    </Card>
  );
}

function TimelineTable({ rows }: { rows: EchoTimelineRow[] }) {
  return (
    <div
      className="overflow-x-auto rounded-md border"
      data-testid="echo-timeline"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Layer</TableHead>
            <TableHead>Nodes</TableHead>
            <TableHead>Edges</TableHead>
            <TableHead>Frontier collapse</TableHead>
            <TableHead>Top-channel share</TableHead>
            <TableHead>Community share</TableHead>
            <TableHead>Commenter overlap</TableHead>
            <TableHead>Network nodes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.layerRunId} data-testid="echo-timeline-row">
              <TableCell className="font-medium">{row.layerIndex}</TableCell>
              <TableCell className="font-mono text-xs">
                {row.nodesDiscovered}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {row.edgesObserved}
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Frontier collapse"
                  value={row.collapsePercent}
                  status={row.statuses.s1}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Top-channel share"
                  value={row.topChannelShare}
                  status={row.statuses.s3}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Community share"
                  value={row.communityShare}
                  status={row.statuses.s2}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Commenter overlap"
                  value={row.commenterOverlap}
                  status={row.statuses.s5}
                />
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {row.nodesTotal ?? "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function EchoChamberView() {
  const [videoUrl, setVideoUrl] = useState("");
  const [maxLayers, setMaxLayers] = useState(5);
  const [collectComments, setCollectComments] = useState(false);
  const [projection, setProjection] = useState<"video" | "channel">("video");
  const [extraLayers, setExtraLayers] = useState(2);
  const [detectionId, setDetectionId] = useState<string | null>(null);

  // Detection history: persisted rows for this workspace, newest first.
  // Without this a finished analysis was unreachable after a reload (the
  // selected id only lived in component state).
  const historyQuery = useQuery({
    queryKey: echoChamberKeys.list,
    queryFn: () => listEchoDetections(),
  });
  const history = historyQuery.data?.items ?? [];

  // Auto-select the most recent detection once, so returning researchers see
  // their latest analysis instead of an empty state.
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    if (autoSelectedRef.current || detectionId) return;
    const latest = history[0];
    if (latest && historyQuery.isSuccess) {
      setDetectionId(latest.detection_id);
      autoSelectedRef.current = true;
    }
  }, [history, historyQuery.isSuccess, detectionId]);

  const detectionQuery = useEchoDetection(detectionId);
  const detection = detectionQuery.data;

  const detect = useMutation({
    mutationFn: () =>
      detectEchoChamber({
        video_url: videoUrl.trim() || undefined,
        max_layers: maxLayers,
        collect_comments: collectComments,
        projection,
      }),
    onSuccess: (payload) => setDetectionId(payload.detection_id),
  });

  const cont = useMutation({
    mutationFn: () =>
      continueEchoChamber(detectionId as string, extraLayers),
    onSuccess: () => detectionQuery.refetch(),
  });

  const stop = useMutation({
    mutationFn: () => stopEchoChamber(detectionId as string),
    onSuccess: () => detectionQuery.refetch(),
  });

  const running =
    !!detection && (detection.status === "pending" || detection.status === "running");
  const rows = detection ? shapeTimeline(detection.layers) : [];

  return (
    <div className="space-y-6" data-testid="echo-chamber-view">
      <Card>
        <CardHeader>
          <CardTitle>Detect an echo chamber</CardTitle>
          <CardDescription>
            Paste a video link. The detector crawls up to N recommendation
            layers around it as one background job and reports observed
            per-layer signals — never estimates.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="echo-video-url">Video URL or ID</Label>
              <Input
                id="echo-video-url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={videoUrl}
                onChange={(event) => setVideoUrl(event.target.value)}
                disabled={running}
                data-testid="echo-video-url"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="echo-max-layers">Max layers</Label>
              <Input
                id="echo-max-layers"
                type="number"
                min={1}
                max={MAX_LAYERS_TOTAL}
                value={maxLayers}
                onChange={(event) =>
                  setMaxLayers(
                    Math.max(
                      1,
                      Math.min(MAX_LAYERS_TOTAL, Number(event.target.value) || 1),
                    ),
                  )
                }
                disabled={running}
                className="w-28"
                data-testid="echo-max-layers"
              />
            </div>
            <Button
              onClick={() => detect.mutate()}
              disabled={running || videoUrl.trim().length === 0 || detect.isPending}
              data-testid="echo-detect-button"
            >
              <Play className="size-4" aria-hidden />
              {detect.isPending ? "Starting…" : "Detect"}
            </Button>
          </div>
          <div className="flex items-center gap-3">
            <div className="space-y-1.5" data-testid="echo-projection">
              <Label htmlFor="echo-projection-sel">Measure over</Label>
              <select
                id="echo-projection-sel"
                value={projection}
                onChange={(e) =>
                  setProjection(e.target.value as "video" | "channel")
                }
                disabled={running}
                className="h-9 rounded-md border bg-background px-2 text-sm"
              >
                <option value="video">Videos (recommendation graph)</option>
                <option value="channel">Channels (channel graph)</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
            <Checkbox
              id="echo-collect-comments"
              checked={collectComments}
              onCheckedChange={(checked) =>
                setCollectComments(checked === true)
              }
              disabled={running}
              data-testid="echo-collect-comments"
            />
            <Label htmlFor="echo-collect-comments" className="text-sm font-normal">
              Collect comments during the crawl (enables the commenter-overlap
              signal)
            </Label>
          </div>
          </div>
          {detect.isError ? (
            <p className="text-sm text-destructive">{String(detect.error)}</p>
          ) : null}
        </CardContent>
      </Card>

      {history.length > 0 && (
        <Card className="p-4" data-testid="echo-history">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium">
              <History className="size-4" aria-hidden /> Recent detections
            </span>
            {history.slice(0, 8).map((item) => (
              <button
                key={item.detection_id}
                type="button"
                onClick={() => setDetectionId(item.detection_id)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  item.detection_id === detectionId
                    ? "border-primary bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                title={`${item.status} · ${item.created_at}`}
              >
                {item.detection_id.slice(4, 18)}… · {statusLabel(item.status)}
              </button>
            ))}
          </div>
        </Card>
      )}

      {!detection ? (
        <Card className="p-8 text-center text-sm text-muted-foreground" data-testid="echo-empty">
          No detection yet. Paste a video link above and press Detect to start
          a layered crawl.
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="secondary" data-testid="echo-status">
              {statusLabel(detection.status)}
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {detection.detection_id}
            </span>
            {running ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => stop.mutate()}
                disabled={stop.isPending}
                data-testid="echo-stop"
              >
                <Square className="size-3.5" aria-hidden />
                Stop
              </Button>
            ) : null}
            {canContinue(detection) ? (
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={1}
                  max={MAX_LAYERS_TOTAL}
                  value={extraLayers}
                  onChange={(event) =>
                    setExtraLayers(
                      Math.max(
                        1,
                        Math.min(
                          MAX_LAYERS_TOTAL,
                          Number(event.target.value) || 1,
                        ),
                      ),
                    )
                  }
                  className="w-24"
                  aria-label="Extra layers"
                  data-testid="echo-extra-layers"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => cont.mutate()}
                  disabled={cont.isPending}
                  data-testid="echo-continue"
                >
                  <RefreshCw className="size-3.5" aria-hidden />
                  Continue crawling
                </Button>
              </div>
            ) : null}
          </div>

          {detection.error ? (
            <p className="text-sm text-muted-foreground" data-testid="echo-error">
              {detection.error}
            </p>
          ) : null}

          {detection.job_id ? (
            <JobProgressCard jobId={detection.job_id} title="Echo crawl" />
          ) : null}

          {rows.length > 0 ? (
            <TimelineTable rows={rows} />
          ) : (
            <Card className="p-6 text-center text-sm text-muted-foreground" data-testid="echo-empty-running">
              The seed layer is being prepared. Timeline rows appear as each
              layer completes.
            </Card>
          )}

          {detection.score ? <VerdictBanner detection={detection} /> : null}
        </div>
      )}
    </div>
  );
}
