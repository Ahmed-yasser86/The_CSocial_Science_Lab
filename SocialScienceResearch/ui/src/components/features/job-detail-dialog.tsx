"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { getJobResult } from "@/services/api";
import { formatDateTime } from "@/lib/format";
import { useJob } from "@/services/queries";
import type { Job } from "@/lib/types";

export function JobDetailDialog({
  jobId,
  onOpenChange,
}: {
  jobId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const jobQuery = useJob(jobId);
  const job = jobQuery.data;

  return (
    // modal={false}: job details are a passive progress surface users keep
    // open while crawls run. A modal dialog marks the whole app shell
    // inert/aria-hidden (Base UI), which makes the navbar disappear for the
    // entire duration of a scrape. Non-modal keeps the rest of the app live.
    <Dialog open={jobId !== null} onOpenChange={onOpenChange} modal={false}>
      <DialogContent className="sm:max-w-lg" showBackdrop={false}>
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{jobId}</DialogTitle>
          <DialogDescription>
            {job ? jobSummary(job) : "Loading job state…"}
          </DialogDescription>
        </DialogHeader>
        {jobId ? (
          <div className="space-y-3">
            <JobProgressCard jobId={jobId} title="Live progress" />
            {job?.status === "succeeded" || job?.status === "failed" ? (
              <JobResult key={jobId} jobId={jobId} />
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function JobResult({ jobId }: { jobId: string }) {
  const [result, setResult] = useState<{ target_count?: number; error?: string } | null>(null);

  useEffect(() => {
    void getJobResult(jobId)
      .then((body) =>
        setResult({
          target_count: (body as { target_count?: number }).target_count,
          error: (body as { error?: string }).error,
        }),
      )
      .catch(() => setResult({ error: "Could not load job result" }));
  }, [jobId]);

  if (!result) return null;
  return (
    <div className="rounded-md border p-3 text-xs">
      {result.error ? (
        <p className="text-destructive">Error: {result.error}</p>
      ) : (
        <p>
          Completed with <span className="font-medium">{result.target_count ?? 0}</span>{" "}
          target{result.target_count === 1 ? "" : "s"} collected.
        </p>
      )}
    </div>
  );
}

function jobSummary(job: Job): string {
  const parts = [`Kind: ${job.kind.replace(/_/g, " ")}`, `Created: ${formatDateTime(job.created_at)}`];
  if (job.finished_at) parts.push(`Finished: ${formatDateTime(job.finished_at)}`);
  if (job.message) parts.push(`Message: ${job.message}`);
  return parts.join(" · ");
}