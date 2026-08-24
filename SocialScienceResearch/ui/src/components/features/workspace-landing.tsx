"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Compass,
  Database,
  FolderKanban,
  FlaskConical,
  Loader2,
  Network,
  Plus,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LoadingState } from "@/components/features/state";
import { useProjectList, useProject, useDataset } from "@/services/queries";
import { withContext, useResearchContext } from "@/lib/context";
import {
  loadAdhocFlag,
  saveAdhocFlag,
  useActiveSession,
  type ActiveSession,
} from "@/lib/session";

export function WorkspaceLanding() {
  const { hydrated, session, setActiveSession, clearActiveSession } =
    useActiveSession();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [adhoc, setAdhoc] = useState(false);

  useEffect(() => {
    setAdhoc(loadAdhocFlag());
  }, []);

  function exploreWithoutProject() {
    saveAdhocFlag();
    setAdhoc(true);
  }

  if (!hydrated) {
    return (
      <div
        className="h-36 animate-pulse rounded-xl border bg-muted/40"
        aria-hidden
      />
    );
  }

  if (session) {
    return (
      <>
        <ActiveSessionCard
          session={session}
          onChangeSession={() => setPickerOpen(true)}
          onEndSession={() => clearActiveSession()}
        />
        <ProjectPickerDialog
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          onSelect={(projectId) => {
            setPickerOpen(false);
            setActiveSession(projectId, null);
          }}
        />
      </>
    );
  }

  if (adhoc) {
    return (
      <div
        className="flex items-center gap-3 rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground"
        data-testid="adhoc-session-note"
      >
        <span>Browsing without an active project.</span>
        <Button
          type="button"
          variant="outline"
          size="xs"
          onClick={() => setPickerOpen(true)}
          data-testid="adhoc-set-project"
        >
          <FolderKanban className="size-3.5" aria-hidden />
          Set active project
        </Button>
        <ProjectPickerDialog
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          onSelect={(projectId) => {
            setPickerOpen(false);
            setActiveSession(projectId, null);
          }}
        />
      </div>
    );
  }

  return (
    <Card
      className="relative overflow-hidden p-8 md:p-10"
      data-testid="welcome-panel"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <div className="flex items-start gap-4">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <FlaskConical className="size-5" aria-hidden />
        </span>
        <div className="max-w-2xl space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">
            Welcome to the research workbench
          </h2>
          <p className="text-sm text-muted-foreground">
            Take a study from question to evidence: collect YouTube data with
            full provenance, sample it reproducibly, materialize datasets, and
            analyze recommendation networks — one auditable journey.
          </p>
        </div>
      </div>

      <ol className="mt-6 grid gap-3 text-sm sm:grid-cols-3">
        <li className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium">1 · Collect</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Register channels and videos as provenance-tracked runs.
          </p>
        </li>
        <li className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium">2 · Sample &amp; analyze</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Build reproducible samples, datasets, and research queries.
          </p>
        </li>
        <li className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium">3 · Model networks</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Explore recommendation graphs in the Network Lab.
          </p>
        </li>
      </ol>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          render={<Link href="/projects?new=1" />}
          nativeButton={false}
          data-testid="welcome-start-new"
        >
          <Plus aria-hidden />
          Start new analysis
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => setPickerOpen(true)}
          data-testid="welcome-open-existing"
        >
          <Search aria-hidden />
          Open existing project
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={exploreWithoutProject}
          data-testid="welcome-explore-adhoc"
        >
          <Compass aria-hidden />
          Explore without a project
        </Button>
      </div>

      <ProjectPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onSelect={(projectId) => {
          setPickerOpen(false);
          setActiveSession(projectId, null);
        }}
      />
    </Card>
  );
}

function ActiveSessionCard({
  session,
  onChangeSession,
  onEndSession,
}: {
  session: ActiveSession;
  onChangeSession: () => void;
  onEndSession: () => void;
}) {
  const { context } = useResearchContext();
  const projectQuery = useProject(session.activeProjectId);
  const datasetQuery = useDataset(session.activeDatasetId ?? "");

  return (
    <Card className="p-6" data-testid="active-session-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Active session
          </p>
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <FolderKanban
              className="size-4 shrink-0 text-muted-foreground"
              aria-hidden
            />
            {projectQuery.isLoading ? (
              <span className="inline-flex items-center gap-2 text-sm font-normal text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                Loading project…
              </span>
            ) : (
              (projectQuery.data?.name ?? session.activeProjectId)
            )}
          </h2>
          {session.activeDatasetId ? (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Database className="size-3.5 shrink-0" aria-hidden />
              {datasetQuery.data?.name ?? session.activeDatasetId}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            render={
              <Link href={`/projects/${session.activeProjectId}`} />
            }
            nativeButton={false}
          >
            <FolderKanban className="size-3.5" aria-hidden />
            Open project
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            render={
              <Link href={withContext("/network/full", context)} />
            }
            nativeButton={false}
          >
            <Network className="size-3.5" aria-hidden />
            Open Network Lab
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onChangeSession}>
            Change session
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={onEndSession}
            data-testid="end-session"
          >
            End session
          </Button>
        </div>
      </div>
    </Card>
  );
}

export function ProjectPickerDialog({
  open,
  onOpenChange,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (projectId: string) => void;
}) {
  const [search, setSearch] = useState("");
  const projectsQuery = useProjectList();

  const projects = useMemo(() => {
    const pages = projectsQuery.data?.pages ?? [];
    return pages.flatMap((page) => page.items);
  }, [projectsQuery.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((project) =>
      project.name.toLowerCase().includes(q),
    );
  }, [projects, search]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Set active project</DialogTitle>
          <DialogDescription>
            Choose which research design drives this working session.
          </DialogDescription>
        </DialogHeader>

        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search projects…"
          autoComplete="off"
          aria-label="Search projects"
        />

        <div className="max-h-72 overflow-y-auto">
          {projectsQuery.isLoading ? (
            <LoadingState label="Loading projects…" />
          ) : filtered.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No matching projects.
            </p>
          ) : (
            <ul className="space-y-1">
              {filtered.map((project) => (
                <li key={project.project_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(project.project_id)}
                    data-testid="project-picker-row"
                    className="w-full rounded-md border-transparent px-3 py-2 text-left transition-colors outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  >
                    <span className="block truncate text-sm font-medium">
                      {project.name}
                    </span>
                    {project.description ? (
                      <span className="block truncate text-xs text-muted-foreground">
                        {project.description}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
