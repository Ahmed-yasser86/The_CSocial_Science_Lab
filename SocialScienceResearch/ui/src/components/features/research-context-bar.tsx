"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FlaskConical, FolderKanban, MonitorUp, Play, X } from "lucide-react";
import {
  useResearchContext,
  withContext,
  stripContext,
} from "@/lib/context";
import { useActiveSession } from "@/lib/session";
import { useProject, useDataset } from "@/services/queries";
import { Button } from "@/components/ui/button";

export function ResearchContextBar() {
  const pathname = usePathname();
  const {
    context,
    hasContext,
    projectName,
    channelId,
    videoId,
  } = useResearchContext();
  const { session, clearActiveSession } = useActiveSession();
  const projectQuery = useProject(session?.activeProjectId ?? "");
  const datasetQuery = useDataset(session?.activeDatasetId ?? "");

  if (!hasContext && !session) return null;

  return (
    <div className="flex items-center gap-3 border-t px-4 py-1.5 md:px-6">
      {session ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Session
          </span>
          <Chip
            label={projectQuery.data?.name ?? session.activeProjectId}
            icon={FolderKanban}
            href={`/projects/${session.activeProjectId}`}
          />
          {session.activeDatasetId ? (
            <Chip
              label={datasetQuery.data?.name ?? session.activeDatasetId}
              icon={Database}
            />
          ) : null}
          <button
            type="button"
            aria-label="End active session"
            data-testid="end-session"
            onClick={clearActiveSession}
            className="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <X className="size-3" aria-hidden />
          </button>
        </div>
      ) : null}
      {hasContext ? (
        <>
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Context
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {projectName ? (
              <Chip label={projectName} icon={FlaskConical} />
            ) : null}
            {channelId ? (
              <Chip
                label={channelId}
                icon={MonitorUp}
                href={withContext(`/channels/${channelId}`, context)}
              />
            ) : null}
            {videoId ? (
              <Chip
                label={videoId}
                icon={Play}
                href={withContext(`/videos/${videoId}`, context)}
              />
            ) : null}
            {context.queryHash ? (
              <Chip label={`query:${context.queryHash}`} icon={FlaskConical} />
            ) : null}
            {context.variables?.length ? (
              <Chip label={`${context.variables.length} variable(s)`} />
            ) : null}
          </div>
          <Button
            render={<Link href={stripContext(pathname)} />}
            nativeButton={false}
            variant="ghost"
            size="xs"
            className="ml-auto text-muted-foreground"
          >
            <X className="size-3" aria-hidden />
            Clear
          </Button>
        </>
      ) : null}
    </div>
  );
}

function Chip({
  label,
  icon: Icon,
  href,
}: {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  href?: string;
}) {
  const inner = (
    <>
      {Icon ? <Icon className="size-3 shrink-0" aria-hidden /> : null}
      <span className="max-w-48 truncate">{label}</span>
    </>
  );
  const className =
    "inline-flex h-5 items-center gap-1 rounded-4xl border border-border bg-muted/40 px-2 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none";
  if (href) {
    return (
      <Link href={href} className={className}>
        {inner}
      </Link>
    );
  }
  return <span className={className}>{inner}</span>;
}
