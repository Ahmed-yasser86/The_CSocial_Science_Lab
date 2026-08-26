"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Briefcase, Ban, Loader2, Skull } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useJobs, useCancelJob, useKillStuckJobs } from "@/services/queries";
import { useToast } from "@/components/ui/toast";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState } from "@/components/features/state";
import { formatNumber, formatDateTime } from "@/lib/format";
import { JobDetailDialog } from "@/components/features/job-detail-dialog";
import type { Job, JobStatus, CollectionStatus } from "@/lib/types";

const ACTIVE_STATUSES: JobStatus[] = ["pending", "running"];

const RUN_STATUS: Record<JobStatus, CollectionStatus> = {
  pending: "pending",
  running: "running",
  succeeded: "success",
  failed: "failed",
  cancelled: "failed",
};

export function JobsTray() {
  const { data: jobs, isLoading, isError } = useJobs();
  const cancel = useCancelJob();
  const killStuck = useKillStuckJobs();
  const { toast } = useToast();
  const [detailJobId, setDetailJobId] = useState<string | null>(null);

  const activeCount = useMemo(
    () => (jobs ?? []).filter((j) => ACTIVE_STATUSES.includes(j.status)).length,
    [jobs],
  );

  const activeJobs = useMemo(
    () => (jobs ?? []).filter((j) => ACTIVE_STATUSES.includes(j.status)),
    [jobs],
  );
  const recentJobs = useMemo(
    () =>
      (jobs ?? [])
        .filter((j) => !ACTIVE_STATUSES.includes(j.status))
        .slice(0, 8),
    [jobs],
  );

  function requestCancel(job: Job) {
    cancel.mutate(job.job_id, {
      onSuccess: () => {
        toast({
          title: "Cancel requested",
          description: `Job ${job.job_id} will stop after the current step.`,
        });
      },
      onError: (error) => {
        toast({
          title: "Could not cancel job",
          description: (error as Error).message,
          variant: "destructive",
        });
      },
    });
  }

  function requestKillStuck() {
    if (
      !window.confirm(
        "Kill ALL pending/running jobs and recycle the worker pool? " +
          "Stuck jobs blocked on a stalled network call cannot be cancelled cooperatively, " +
          "so this force-terminates them. In-progress work will be lost.",
      )
    ) {
      return;
    }
    killStuck.mutate(undefined, {
      onSuccess: (res) => {
        toast({
          title: "Killed stuck jobs",
          description:
            res.killed > 0
              ? `${res.killed} job(s) terminated and the worker pool was recycled.`
              : "No pending/running jobs to kill.",
        });
      },
      onError: (error) => {
        toast({
          title: "Could not kill stuck jobs",
          description: (error as Error).message,
          variant: "destructive",
        });
      },
    });
  }

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="relative text-muted-foreground hover:text-foreground"
            aria-label="Jobs tray"
          />
        }
      >
        <Briefcase className="size-4" aria-hidden />
        <span className="hidden lg:inline">Jobs</span>
        {activeCount > 0 ? (
          <span
            className={cn(
              "inline-flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground",
            )}
          >
            {activeCount}
          </span>
        ) : null}
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={6}
        className="w-96 gap-0 overflow-hidden p-0"
      >
        <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
          <p className="text-sm font-medium">Jobs</p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {activeCount} active
            </span>
            <Button
              variant="outline"
              size="xs"
              onClick={requestKillStuck}
              disabled={killStuck.isPending || activeCount === 0}
              title="Force-terminate all pending/running jobs and recycle the worker pool"
            >
              {killStuck.isPending ? (
                <Loader2 className="size-3 animate-spin" aria-hidden />
              ) : (
                <Skull className="size-3" aria-hidden />
              )}
              Kill stuck
            </Button>
          </div>
        </div>

        <div className="max-h-[26rem] overflow-y-auto">
          {isLoading ? (
            <LoadingState label="Loading jobs…" className="min-h-32" />
          ) : isError ? (
            <p className="p-4 text-sm text-muted-foreground">
              Jobs are unavailable right now.
            </p>
          ) : jobs && jobs.length > 0 ? (
            <div className="space-y-3 p-3">
              {activeJobs.length > 0 ? (
                <JobGroup title="Active">
                  {activeJobs.map((job) => (
                    <JobRow
                      key={job.job_id}
                      job={job}
                      cancelling={cancel.isPending && cancel.variables === job.job_id}
                      onCancel={() => requestCancel(job)}
                      onOpen={() => setDetailJobId(job.job_id)}
                    />
                  ))}
                </JobGroup>
              ) : null}
              {recentJobs.length > 0 ? (
                <JobGroup title="Recent">
                  {recentJobs.map((job) => (
                    <JobRow
                      key={job.job_id}
                      job={job}
                      onCancel={() => requestCancel(job)}
                      onOpen={() => setDetailJobId(job.job_id)}
                    />
                  ))}
                </JobGroup>
              ) : null}
            </div>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">
              No jobs yet. Start a collection to see it here.
            </p>
          )}
        </div>
      </PopoverContent>
      <JobDetailDialog
        jobId={detailJobId}
        onOpenChange={(open) => {
          if (!open) setDetailJobId(null);
        }}
      />
    </Popover>
  );
}

function JobGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      {children}
    </div>
  );
}

function JobRow({
  job,
  onCancel,
  onOpen,
  cancelling = false,
}: {
  job: Job;
  onCancel: () => void;
  onOpen: () => void;
  cancelling?: boolean;
}) {
  const active = ACTIVE_STATUSES.includes(job.status);
  return (
    <div className="space-y-1 rounded-md border p-2.5">
      <div className="flex items-center justify-between gap-2">
        <Link
          href={`/jobs/${job.job_id}`}
          className="truncate font-mono text-xs underline-offset-2 outline-none hover:underline focus-visible:underline"
          title="Open job details page"
        >
          {job.job_id}
        </Link>
        {active ? (
          <Button
            variant="outline"
            size="xs"
            onClick={onCancel}
            disabled={cancelling || job.cancel_requested}
          >
            {cancelling ? (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            ) : (
              <Ban className="size-3" aria-hidden />
            )}
            {job.cancel_requested ? "Cancelling" : "Cancel"}
          </Button>
        ) : (
          <JobStatusBadge status={job.status} />
        )}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground capitalize">
          {job.kind.replace(/_/g, " ")}
        </span>
        <span className="text-[10px] text-muted-foreground">
          {job.finished_at
            ? formatDateTime(job.finished_at)
            : formatDateTime(job.created_at)}
        </span>
      </div>
      {active ? <JobProgress job={job} /> : null}
    </div>
  );
}

function JobStatusBadge({ status }: { status: JobStatus }) {
  if (status === "cancelled") {
    return <Badge variant="outline">Cancelled</Badge>;
  }
  return <RunStatusBadge status={RUN_STATUS[status]} />;
}

function JobProgress({ job }: { job: Job }) {
  const { discovered, succeeded, failed } = job.progress;
  return (
    <p className="text-xs text-muted-foreground">
      {job.progress.message ??
        `${formatNumber(succeeded)} succeeded · ${formatNumber(failed)} failed of ${formatNumber(discovered)} discovered`}
    </p>
  );
}
