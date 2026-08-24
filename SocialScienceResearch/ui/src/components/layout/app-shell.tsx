"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FlaskConical, Compass, Network, FolderOpen, ListOrdered, Scale, Database, FolderKanban, GitCompare, Table2, Search, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { CommandPalette } from "@/components/features/command-palette";
import { ResearchContextBar } from "@/components/features/research-context-bar";
import { JobsTray } from "@/components/features/jobs-tray";
import { ThemeToggle } from "@/components/features/theme-toggle";
import { useActiveWorkspace } from "@/lib/session";
import { useResearchContext, withContext } from "@/lib/context";

const NAV_ITEMS = [
  { href: "/", label: "Workspace", icon: FlaskConical },
  { href: "/collect", label: "Collect", icon: Compass },
  { href: "/explore", label: "Explorer", icon: Scale },
  { href: "/network", label: "Network", icon: Network },
  { href: "/network/full", label: "Lab", icon: Network },
  { href: "/compare", label: "Compare", icon: GitCompare },
  { href: "/query", label: "Query", icon: Search },
  { href: "/data", label: "Data", icon: Table2 },
  { href: "/samples", label: "Samples", icon: Database },
  { href: "/datasets", label: "Datasets", icon: FolderOpen },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/runs", label: "Runs", icon: ListOrdered },
  { href: "/docs", label: "Docs", icon: BookOpen },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { context } = useResearchContext();
  const { hydrated, reconciled, workspaceId } = useActiveWorkspace();

  // Route guard: content routes live INSIDE a workspace. Without an active
  // workspace the only valid destination is the chooser at `/`. Waits for the
  // server reconciliation so a fresh browser (empty localStorage, pointer
  // only on the server) is never bounced before the pointer is restored.
  useEffect(() => {
    if (hydrated && reconciled && !workspaceId && pathname !== "/") {
      router.replace("/");
    }
  }, [hydrated, reconciled, workspaceId, pathname, router]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center gap-6 px-4 md:px-6">
          <Link
            href={withContext("/", context)}
            className="flex items-center gap-2 font-medium text-sm tracking-tight"
          >
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <FlaskConical className="size-4" aria-hidden />
            </span>
            <span className="hidden sm:inline">Social Science Research</span>
          </Link>

          {workspaceId ? (
            <nav aria-label="Primary" className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={withContext(item.href, context)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
                      active && "bg-muted text-foreground",
                    )}
                  >
                    <item.icon className="size-4" aria-hidden />
                    <span className="hidden md:inline">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          ) : null}

          <div className="ml-auto flex items-center gap-3">
            <ThemeToggle />
            {workspaceId ? <JobsTray /> : null}
            <CommandPalette />
          </div>
        </div>
        <ResearchContextBar />
      </header>

      <main className="flex-1 px-4 py-6 md:px-6">
        <div className="mx-auto w-full max-w-7xl">{children}</div>
      </main>

      <footer className="border-t py-4 px-6 text-xs text-muted-foreground">
        Computational Social Science Research Workbench · data is observed, never
        estimated · missing values are reported explicitly
      </footer>
    </div>
  );
}
