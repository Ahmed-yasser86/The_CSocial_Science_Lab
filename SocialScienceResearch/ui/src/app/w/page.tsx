"use client";

import Link from "next/link";
import {
  Compass,
  FolderKanban,
  Network,
  Table2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { RecentRunsPanel } from "@/components/features/recent-runs-panel";
import { useWorkspace } from "@/services/queries";
import { useActiveSession, useActiveWorkspace } from "@/lib/session";

const QUICK_LINKS = [
  { href: "/collect", label: "Collect data", icon: Compass },
  { href: "/network/full", label: "Network Lab", icon: Network },
  { href: "/datasets", label: "Datasets", icon: Table2 },
  { href: "/projects", label: "Projects", icon: FolderKanban },
];

export default function WorkspaceHome() {
  const { hydrated, workspaceId } = useActiveWorkspace();
  // Route guarding happens globally in the app shell; until hydration
  // completes we render nothing so a stale workspace is never shown.
  if (!hydrated || !workspaceId) {
    return (
      <div
        className="h-48 animate-pulse rounded-xl border bg-muted/40"
        aria-hidden
        data-testid="workspace-home-loading"
      />
    );
  }
  return <WorkspaceHomeContent />;
}

function WorkspaceHomeContent() {
  const { workspaceId } = useActiveWorkspace();
  const { session } = useActiveSession();
  const workspaceQuery = useWorkspace(workspaceId ?? "");

  const name =
    workspaceQuery.data?.name ?? workspaceId ?? "";
  const stats = workspaceQuery.data?.stats;

  return (
    <div className="space-y-6" data-testid="workspace-home">
      <header className="space-y-1">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Workspace
        </p>
        <h1
          className="text-xl font-semibold tracking-tight"
          data-testid="workspace-home-title"
        >
          {name}
        </h1>
        <p className="text-sm text-muted-foreground" data-testid="workspace-home-stats">
          {stats
            ? `${stats.runs} runs · ${stats.videos} videos · ${stats.comments} comments · ${stats.datasets} datasets · ${stats.projects} projects`
            : "Loading stats…"}
        </p>
      </header>

      <nav className="grid gap-3 sm:grid-cols-4" aria-label="Workspace tools">
        {QUICK_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-center gap-2 rounded-lg border p-3 text-sm font-medium transition-colors hover:bg-muted"
          >
            <link.icon className="size-4 text-muted-foreground" aria-hidden />
            {link.label}
          </Link>
        ))}
      </nav>

      {session ? null : (
        <Card className="border-dashed p-4 text-sm text-muted-foreground">
          No active project in this workspace yet — pick one from{" "}
          <Link href="/projects" className="underline underline-offset-2">
            Projects
          </Link>{" "}
          or just start collecting.
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Recent runs</h2>
        <RecentRunsPanel />
      </section>
    </div>
  );
}
