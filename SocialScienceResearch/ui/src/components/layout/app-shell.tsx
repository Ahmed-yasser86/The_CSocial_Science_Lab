"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Boxes,
  ChevronDown,
  Compass,
  Database,
  FolderKanban,
  FolderOpen,
  FlaskConical,
  GitCompare,
  Layers,
  LayoutDashboard,
  ListOrdered,
  Menu,
  Microscope,
  Network,
  Radio,
  Search,
  Table2,
  Users,
  Waypoints,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CommandPalette } from "@/components/features/command-palette";
import { ResearchContextBar } from "@/components/features/research-context-bar";
import { JobsTray } from "@/components/features/jobs-tray";
import { ThemeToggle } from "@/components/features/theme-toggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useActiveWorkspace } from "@/lib/session";
import {
  useResearchContext,
  withContext,
  type ResearchContext,
} from "@/lib/context";

type NavIcon = React.ComponentType<{
  className?: string;
  "aria-hidden"?: boolean;
}>;

interface NavEntry {
  href: string;
  label: string;
  icon: NavIcon;
}

const WORKSPACE_ENTRY: NavEntry = {
  href: "/",
  label: "Workspace",
  icon: LayoutDashboard,
};
const COLLECT_ENTRY: NavEntry = {
  href: "/collect",
  label: "Collect",
  icon: Compass,
};
const DOCS_ENTRY: NavEntry = { href: "/docs", label: "Docs", icon: BookOpen };

const ANALYZE_ENTRIES: NavEntry[] = [
  { href: "/network", label: "Overview", icon: Network },
  { href: "/network/full", label: "Lab", icon: Microscope },
  { href: "/network/echo-chambers", label: "Echo Chambers", icon: Radio },
  { href: "/network/commenters", label: "Commenters", icon: Users },
  { href: "/compare", label: "Compare", icon: GitCompare },
  { href: "/query", label: "Query", icon: Search },
  { href: "/explore", label: "Explorer", icon: Boxes },
];

const DATA_ENTRIES: NavEntry[] = [
  { href: "/data", label: "Coverage", icon: Table2 },
  { href: "/datasets", label: "Datasets", icon: FolderOpen },
  { href: "/samples", label: "Samples", icon: Layers },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/runs", label: "Runs", icon: ListOrdered },
];

const TOP_LEVEL_ENTRIES: NavEntry[] = [
  WORKSPACE_ENTRY,
  COLLECT_ENTRY,
  DOCS_ENTRY,
];

function routeIsActive(pathname: string, href: string): boolean {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

const NAV_TRIGGER_CLASSES =
  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none data-[popup-open]:bg-muted data-[popup-open]:text-foreground";

function NavLink({
  entry,
  active,
  context,
}: {
  entry: NavEntry;
  active: boolean;
  context: ResearchContext;
}) {
  return (
    <Link
      href={withContext(entry.href, context)}
      aria-current={active ? "page" : undefined}
      className={cn(NAV_TRIGGER_CLASSES, active && "bg-muted text-foreground")}
    >
      <entry.icon className="size-4" aria-hidden />
      <span>{entry.label}</span>
    </Link>
  );
}

function NavMenuEntries({
  entries,
  pathname,
  context,
}: {
  entries: NavEntry[];
  pathname: string;
  context: ResearchContext;
}) {
  return (
    <>
      {entries.map((entry) => (
        <DropdownMenuItem
          key={entry.href}
          render={<Link href={withContext(entry.href, context)} />}
        >
          <entry.icon className="size-4" aria-hidden />
          {entry.label}
          {routeIsActive(pathname, entry.href) ? (
            <span className="ml-auto size-1.5 rounded-full bg-primary" aria-hidden />
          ) : null}
        </DropdownMenuItem>
      ))}
    </>
  );
}

function NavHub({
  label,
  icon: Icon,
  entries,
  pathname,
  context,
}: {
  label: string;
  icon: NavIcon;
  entries: NavEntry[];
  pathname: string;
  context: ResearchContext;
}) {
  const active = entries.some((entry) => routeIsActive(pathname, entry.href));
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        openOnHover
        delay={120}
        closeDelay={120}
        aria-haspopup="menu"
        className={cn(
          NAV_TRIGGER_CLASSES,
          active && "bg-muted text-foreground",
        )}
      >
        <Icon className="size-4" aria-hidden />
        <span>{label}</span>
        <ChevronDown className="size-3 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-auto min-w-44">
        <NavMenuEntries entries={entries} pathname={pathname} context={context} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function CompactNavMenu({
  pathname,
  context,
}: {
  pathname: string;
  context: ResearchContext;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Browse sections"
        aria-haspopup="menu"
        className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none data-[popup-open]:bg-muted data-[popup-open]:text-foreground"
      >
        <Menu className="size-5" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-auto min-w-48">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Analyze</DropdownMenuLabel>
          <NavMenuEntries
            entries={ANALYZE_ENTRIES}
            pathname={pathname}
            context={context}
          />
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>Data</DropdownMenuLabel>
          <NavMenuEntries
            entries={DATA_ENTRIES}
            pathname={pathname}
            context={context}
          />
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>Workspace</DropdownMenuLabel>
          <NavMenuEntries
            entries={TOP_LEVEL_ENTRIES}
            pathname={pathname}
            context={context}
          />
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

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
              <div className="hidden items-center gap-1 lg:flex">
                <NavLink
                  entry={WORKSPACE_ENTRY}
                  active={routeIsActive(pathname, WORKSPACE_ENTRY.href)}
                  context={context}
                />
                <NavLink
                  entry={COLLECT_ENTRY}
                  active={routeIsActive(pathname, COLLECT_ENTRY.href)}
                  context={context}
                />
                <NavHub
                  label="Analyze"
                  icon={Waypoints}
                  entries={ANALYZE_ENTRIES}
                  pathname={pathname}
                  context={context}
                />
                <NavHub
                  label="Data"
                  icon={Database}
                  entries={DATA_ENTRIES}
                  pathname={pathname}
                  context={context}
                />
                <NavLink
                  entry={DOCS_ENTRY}
                  active={routeIsActive(pathname, DOCS_ENTRY.href)}
                  context={context}
                />
              </div>
              <div className="lg:hidden">
                <CompactNavMenu pathname={pathname} context={context} />
              </div>
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

