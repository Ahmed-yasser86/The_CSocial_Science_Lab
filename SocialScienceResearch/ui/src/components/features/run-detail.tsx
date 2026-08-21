"use client";

import Link from "next/link";
import { useSearchParams, usePathname, useRouter } from "next/navigation";
import { useRun, useRunErrors } from "@/services/queries";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { ErrorList } from "@/components/features/error-list";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatDateTime, formatNumber } from "@/lib/format";
import { RunVideosBrowser } from "@/components/features/run-videos-browser";
import { RunSubRunsBrowser } from "@/components/features/run-sub-runs-browser";
import { FoldersTab } from "@/components/features/folders-tab";
import { ExportTab } from "@/components/features/export-tab";

type TabId = "overview" | "videos" | "sub-runs" | "folders" | "export";

export function RunDetail({ runId }: { runId: string }) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const initialTab = (searchParams.get("tab") as TabId) ?? "overview";

  const runQuery = useRun(runId);
  const errorsQuery = useRunErrors(runId);

  if (runQuery.isLoading) return <LoadingState label="Loading run…" />;
  if (runQuery.isError)
    return (
      <ErrorState
        message={(runQuery.error as Error).message}
        detail="This run may not exist."
      />
    );
  const run = runQuery.data!;

  const targetId = run.target_channel_id ?? run.target_video_id;

  function onTabChange(value: string) {
    const newTab = value as TabId;
    if (newTab === "overview") {
      router.replace(pathname);
    } else {
      router.replace(`${pathname}?tab=${newTab}`);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm">{run.name ?? run.run_id}</span>
        <RunStatusBadge status={run.status} />
        <Badge variant="secondary">{run.run_type}</Badge>
        {run.target_video_id ? (
          <Link
            href={`/videos/${run.target_video_id}`}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            video {run.target_video_id}
          </Link>
        ) : run.target_channel_id ? (
          <Link
            href={`/channels/${run.target_channel_id}`}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            channel {run.target_channel_id}
          </Link>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground">
          provider {run.provider}
          {run.provider_version ? ` v${run.provider_version}` : ""}
        </span>
      </div>

      <Tabs value={initialTab} onValueChange={onTabChange} className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="videos">Videos</TabsTrigger>
          <TabsTrigger value="sub-runs">Sub-runs</TabsTrigger>
          <TabsTrigger value="folders">Folders</TabsTrigger>
          <TabsTrigger value="export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Target URL" value={<span className="break-all">{run.target_url}</span>} />
            <Field
              label="Target id"
              value={
                targetId ? (
                  <Link
                    href={
                      run.target_channel_id
                        ? `/channels/${targetId}`
                        : `/videos/${targetId}`
                    }
                    className="font-mono text-primary underline-offset-2 hover:underline"
                  >
                    {targetId}
                  </Link>
                ) : (
                  "—"
                )
              }
            />
            <Field
              label="Started"
              value={<span className="font-mono">{formatDateTime(run.started_at)}</span>}
            />
            <Field
              label="Finished"
              value={<span className="font-mono">{formatDateTime(run.finished_at)}</span>}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Discovered" value={run.entities_discovered} />
            <Stat label="New" value={run.entities_succeeded} />
            <Stat label="Existing" value={run.entities_existing} />
            <Stat label="Failed" value={run.entities_failed} />
            <Stat label="Comments" value={run.comments_collected} />
          </div>

          {run.notes.length > 0 ? (
            <Card className="p-3">
              <ul className="list-inside list-disc space-y-1 text-sm">
                {run.notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            </Card>
          ) : null}

          <Card className="p-3">
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Configuration snapshot
            </h3>
            <pre className="overflow-x-auto rounded-md bg-muted/40 p-3 text-xs">
              {JSON.stringify(run.config_json, null, 2)}
            </pre>
          </Card>

          <section aria-labelledby="errors-heading">
            <h2 id="errors-heading" className="mb-2 text-sm font-medium">
              Errors
            </h2>
            {errorsQuery.isLoading ? (
              <LoadingState label="Loading errors…" />
            ) : errorsQuery.isError ? (
              <ErrorState message={(errorsQuery.error as Error).message} />
            ) : errorsQuery.data && errorsQuery.data.length > 0 ? (
              <ErrorList errors={errorsQuery.data} />
            ) : (
              <EmptyState title="No recorded errors" description="This run completed without per-entity failures." />
            )}
          </section>
        </TabsContent>

        <TabsContent value="videos" className="mt-4">
          <RunVideosBrowser runId={runId} />
        </TabsContent>

        <TabsContent value="sub-runs" className="mt-4">
          <RunSubRunsBrowser runId={runId} />
        </TabsContent>

        <TabsContent value="folders" className="mt-4">
          <FoldersTab />
        </TabsContent>

        <TabsContent value="export" className="mt-4">
          <ExportTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card className="p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-0.5 text-sm">{value}</div>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xl font-semibold tabular-nums">{formatNumber(value)}</p>
    </Card>
  );
}