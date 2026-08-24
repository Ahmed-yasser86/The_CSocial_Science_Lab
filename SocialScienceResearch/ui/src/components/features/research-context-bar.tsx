"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowLeftRight,
  Database,
  FlaskConical,
  FolderKanban,
  LogOut,
  MonitorUp,
  Play,
  X,
} from "lucide-react";
import {
  useResearchContext,
  withContext,
  stripContext,
} from "@/lib/context";
import { useActiveSession, useActiveWorkspace } from "@/lib/session";
import { useProject, useDataset, useWorkspaces } from "@/services/queries";
import type { Workspace } from "@/services/workspaces";
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
  const { workspaceId } = useActiveWorkspace();
  const projectQuery = useProject(session?.activeProjectId ?? "");
  const datasetQuery = useDataset(session?.activeDatasetId ?? "");

  if (!hasContext && !session && !workspaceId) return null;

  return (
    <div className="flex items-center gap-3 border-t px-4 py-1.5 md:px-6">
      {workspaceId ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Workspace
          </span>
          <WorkspaceChip workspaceId={workspaceId} />
        </div>
      ) : null}
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

/** Workspace identity chip + switcher (plan §4.2). Server state is
 *  authoritative: switching PUTs ``active_workspace_id``, which rebinds the
 *  backend's database routing; the local query cache is cleared by the
 *  provider so no stale cross-workspace rows can render. */
function WorkspaceChip({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const { setActiveWorkspace, clearActiveWorkspace } = useActiveWorkspace();
  const workspacesQuery = useWorkspaces();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const current = workspacesQuery.data?.find(
    (w) => w.workspace_id === workspaceId,
  );
  const others: Workspace[] = (workspacesQuery.data ?? []).filter(
    (w) => w.workspace_id !== workspaceId,
  );

  function switchTo(id: string) {
    setOpen(false);
    setActiveWorkspace(id);
    router.push("/w");
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid="workspace-chip"
        className="inline-flex h-5 items-center gap-1 rounded-4xl border border-border bg-muted/40 px-2 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <FlaskConical className="size-3 shrink-0" aria-hidden />
        <span className="max-w-48 truncate">
          {current?.name ?? workspaceId}
        </span>
        <ArrowLeftRight className="size-3 shrink-0 opacity-60" aria-hidden />
      </button>
      {open ? (
        <div
          role="menu"
          data-testid="workspace-switcher"
          className="absolute left-0 top-7 z-50 w-64 rounded-lg border bg-popover p-1 shadow-md"
        >
          <p className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Switch workspace
          </p>
          {others.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              No other workspaces yet.
            </p>
          ) : (
            others.map((workspace) => (
              <button
                key={workspace.workspace_id}
                type="button"
                role="menuitem"
                onClick={() => switchTo(workspace.workspace_id)}
                data-testid="workspace-switch-option"
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              >
                <ArrowLeftRight
                  className="size-3.5 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="truncate">{workspace.name}</span>
              </button>
            ))
          )}
          <div className="my-1 h-px bg-border" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              clearActiveWorkspace();
              router.push("/");
            }}
            data-testid="back-to-workspaces"
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
          >
            <LogOut className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            Back to workspaces
          </button>
        </div>
      ) : null}
    </div>
  );
}
