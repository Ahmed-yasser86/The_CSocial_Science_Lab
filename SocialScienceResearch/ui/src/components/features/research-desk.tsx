"use client";

import Link from "next/link";
import { CollectTargetForm } from "@/components/features/collect-target-form";
import { RecentRunsPanel } from "@/components/features/recent-runs-panel";

/**
 * The collection surface that lives INSIDE the active workspace: collect form
 * plus the workspace-scoped recent runs. (Formerly rendered on `/`; moved
 * here when `/` became the pure workspace chooser — nothing was deleted.)
 */
export function ResearchDesk() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-6">
        <section>
          <h2 className="mb-3 text-sm font-medium">Collect data</h2>
          <CollectTargetForm />
        </section>
      </div>

      <aside className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Recent runs</h2>
          <Link
            href="/runs"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            View all
          </Link>
        </div>
        <RecentRunsPanel />
      </aside>
    </div>
  );
}
