"use client";

import { useEffect, useRef } from "react";
import { Ban, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useJob, useCancelJob } from "@/services/queries";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { formatNumber } from "@/lib/format";
import type { JobProgress } from "@/lib/types";

export function formatJobStage(stage?: string): string {
  if (!stage) return "Running";
    const map: Record<string, string> = {
      "recommendation/start": "Starting recommendation scrape",
      "recommendation/batch/start": "Starting batch recommendation scrape",
      "recommendation/batch/progress": "Scraping videos",
      "recommendation/extracting": "Extracting recommendations",
    "recommendation/top_n": "Collecting top-N recommendations",
    "recommendation/dedup": "Deduplicating recommendations",
    "recommendation/edges_found": "Found recommendation edges",
    "recommendation/dataset_persisted": "Persisting dataset",
    "recommendation/complete": "Recommendation scrape complete",
    "expansion/start": "Starting expansion",
    "expansion/complete": "Expansion complete",
    "layer/scrape": "Scraping layer",
    "layer/enrich": "Enriching layer targets",
    "layer/classify": "Classifying new nodes and edges",
    "layer/complete": "Layer complete",
  };
  return map[stage] ?? stage.replace(/_/g, " ");
}

export function JobProgressCard({
  jobId,
  title,
  onSuccess,
}: {
  jobId: string;
  title?: string;
  onSuccess?: (result: unknown) => void;
}) {
  const jobQuery = useJob(jobId);
  const cancel = useCancelJob();
  const job = jobQuery.data;
  const status = job?.status;

  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  useEffect(() => {
    if (status === "succeeded" && onSuccessRef.current) {
      onSuccessRef.current(jobQuery.data);
    }
    // Fire once when the job transitions to a succeeded state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const progress: JobProgress | undefined = job?.progress;
  const succeeded = progress?.succeeded ?? 0;
  const failed = progress?.failed ?? 0;
  const discovered = progress?.discovered ?? 0;
  const pct =
    discovered > 0 ? Math.round(((succeeded + failed) / discovered) * 100) : 0;

  if (status === "succeeded") {
    return (
      <Card className="flex items-center gap-2 p-4 text-sm">
        <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
        <span>{title ?? "Job"} completed</span>
        <span className="font-mono text-xs text-muted-foreground">
          {jobId}
        </span>
        {job?.message ? (
          <span className="ml-auto text-xs text-muted-foreground">
            {job.message}
          </span>
        ) : null}
      </Card>
    );
  }

  if (status === "failed" || status === "cancelled") {
    return (
      <Card className="flex items-center gap-2 p-4 text-sm">
        {status === "failed" ? (
          <XCircle className="size-4 text-destructive" aria-hidden />
        ) : (
          <Ban className="size-4 text-muted-foreground" aria-hidden />
        )}
        <span>{status === "failed" ? "Job failed" : "Job cancelled"}</span>
        <span className="font-mono text-xs text-muted-foreground">
          {jobId}
        </span>
      </Card>
    );
  }

  const running = status === "pending" || status === "running";

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          {running ? (
            <Loader2
              className="size-4 animate-spin text-muted-foreground"
              aria-hidden
            />
          ) : (
            <Loader2 className="size-4 text-muted-foreground" aria-hidden />
          )}
          <span className="font-medium">
            {title ? `${title}: ` : ""}
            {formatJobStage(progress?.stage)}
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {jobId}
          </span>
        </div>
        {running ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancel.mutate(jobId)}
            disabled={cancel.isPending}
          >
            <Ban className="size-3.5" aria-hidden />
            Cancel
          </Button>
        ) : null}
      </div>
      {running && discovered > 0 ? (
        <div className="space-y-1">
          <Progress value={pct} />
          <p className="text-xs text-muted-foreground">
            {formatNumber(succeeded)} succeeded, {formatNumber(failed)} failed
            of {formatNumber(discovered)} discovered
          </p>
        </div>
      ) : null}
      {job?.message ? (
        <p className="text-xs text-muted-foreground">{job.message}</p>
      ) : null}
    </Card>
  );
}
