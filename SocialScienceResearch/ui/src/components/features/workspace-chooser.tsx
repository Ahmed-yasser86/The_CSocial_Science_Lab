"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FlaskConical,
  Loader2,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useCreateWorkspace,
  useWorkspaces,
} from "@/services/queries";
import type { Workspace } from "@/services/workspaces";
import { useActiveWorkspace } from "@/lib/session";

function statsLine(workspace: Workspace): string {
  const s = workspace.stats;
  return `${s.runs} runs · ${s.videos} videos · ${s.datasets} datasets · ${s.projects} projects`;
}

function lastOpenedLabel(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60_000));
  if (minutes < 1) return "opened just now";
  if (minutes < 60) return `opened ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `opened ${hours} h ago`;
  const days = Math.round(hours / 24);
  return `opened ${days} d ago`;
}

export function WorkspaceChooser() {
  const router = useRouter();
  const { hydrated, setActiveWorkspace } = useActiveWorkspace();
  const workspacesQuery = useWorkspaces();
  const [createOpen, setCreateOpen] = useState(false);

  const workspaces = workspacesQuery.data ?? [];

  function enter(workspaceId: string) {
    setActiveWorkspace(workspaceId);
    router.push("/w");
  }

  if (!hydrated || workspacesQuery.isLoading) {
    return (
      <div
        className="h-48 animate-pulse rounded-xl border bg-muted/40"
        aria-hidden
        data-testid="workspace-chooser-loading"
      />
    );
  }

  if (workspacesQuery.isError) {
    return (
      <Card className="p-6 text-sm text-destructive" data-testid="workspace-chooser-error">
        Could not load workspaces. Is the research API running?
      </Card>
    );
  }

  return (
    <div className="space-y-4" data-testid="workspace-chooser">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Each workspace is a fully isolated environment: its own database and
          data directory. Nothing is ever shared between workspaces.
        </p>
      </div>
      <ul
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        data-testid="workspace-grid"
      >
        {workspaces.map((workspace) => (
          <li key={workspace.workspace_id}>
            <button
              type="button"
              onClick={() => enter(workspace.workspace_id)}
              data-testid="workspace-card"
              data-workspace-id={workspace.workspace_id}
              className="group w-full rounded-xl border bg-card p-5 text-left shadow-sm transition-all outline-none hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <div className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
                  {workspace.name.trim().charAt(0).toUpperCase() || "?"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3
                      className="truncate text-base font-semibold tracking-tight"
                      data-testid="workspace-card-name"
                    >
                      {workspace.name}
                    </h3>
                    {workspace.active ? (
                      <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                        Active
                      </span>
                    ) : null}
                    {workspace.is_legacy ? (
                      <span className="hidden shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground sm:inline">
                        Original
                      </span>
                    ) : null}
                  </div>
                  {workspace.research_topic ? (
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {workspace.research_topic}
                    </p>
                  ) : null}
                </div>
              </div>
              <p
                className="mt-4 text-xs tabular-nums text-muted-foreground"
                data-testid="workspace-card-stats"
              >
                {statsLine(workspace)}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {lastOpenedLabel(workspace.last_opened_at)}
              </p>
            </button>
          </li>
        ))}
        <li>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            data-testid="workspace-new-button"
            className="flex min-h-36 w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-5 text-muted-foreground transition-colors outline-none hover:border-primary/50 hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <Plus className="size-5" aria-hidden />
            <span className="text-sm font-medium">New workspace</span>
            <span className="text-xs">Fresh database, fresh start</span>
          </button>
        </li>
      </ul>

      <CreateWorkspaceDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(workspace) => enter(workspace.workspace_id)}
      />
    </div>
  );
}

export function CreateWorkspaceDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (workspace: Workspace) => void;
}) {
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const createMutation = useCreateWorkspace();

  const trimmed = name.trim();
  const canSubmit =
    trimmed.length > 0 && !createMutation.isPending;

  const error = useMemo(() => {
    if (createMutation.isError) {
      return createMutation.error instanceof Error
        ? createMutation.error.message
        : "Creating the workspace failed.";
    }
    return null;
  }, [createMutation.isError, createMutation.error]);

  function submit() {
    if (!canSubmit) return;
    createMutation.mutate(
      { name: trimmed, research_topic: topic.trim() || null },
      {
        onSuccess: (workspace) => {
          setName("");
          setTopic("");
          onOpenChange(false);
          onCreated?.(workspace);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New workspace</DialogTitle>
          <DialogDescription>
            Provisions a fresh PostgreSQL database and an empty data directory.
            Existing workspaces are never touched.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Workspace name (required)"
            aria-label="Workspace name"
            autoFocus
            data-testid="new-workspace-name"
          />
          <Textarea
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="Research topic (optional)"
            aria-label="Research topic"
            rows={2}
            data-testid="new-workspace-topic"
          />
          {error ? (
            <p className="text-xs text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!canSubmit}
              data-testid="new-workspace-submit"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  Provisioning…
                </>
              ) : (
                <>
                  <FlaskConical className="size-3.5" aria-hidden />
                  Create &amp; enter
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
