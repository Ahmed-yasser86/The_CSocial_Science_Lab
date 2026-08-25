"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FlaskConical,
  Compass,
  ListOrdered,
  MessageSquare,
  Network,
  Play,
  Search,
  GitCompare,
  Share2,
  Database,
  FolderOpen,
  FolderKanban,
  BookOpen,
  Boxes,
  Microscope,
  Table2,
  Tv,
  User,
  Users,
} from "lucide-react";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import { useGlobalSearch, useRuns } from "@/services/queries";
import { formatDateTime } from "@/lib/format";
import { RunStatusBadge } from "@/components/features/run-status-badge";
import { LoadingState } from "@/components/features/state";
import { useResearchContext, withContext } from "@/lib/context";
import type { SearchHit } from "@/lib/types";

const SEARCH_ENTITIES: {
  value: string;
  label: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}[] = [
  { value: "channel", label: "Channels", icon: Tv },
  { value: "video", label: "Videos", icon: Play },
  { value: "comment", label: "Comments", icon: MessageSquare },
  { value: "author", label: "Authors", icon: User },
  { value: "recommendation", label: "Recommendations", icon: Share2 },
];

function useDebouncedValue(value: string, delay = 200): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function searchHref(hit: SearchHit): string {
  const term = hit.title ?? hit.subtitle ?? hit.entity_id;
  return `/explore?entity=${encodeURIComponent(hit.entity)}&q=${encodeURIComponent(term)}`;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const { context } = useResearchContext();
  const { data: runs } = useRuns();
  const debouncedQuery = useDebouncedValue(query);
  const search = useGlobalSearch(debouncedQuery);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleOpenChange = useCallback(
    (next: boolean) => {
      setOpen(next);
      if (!next) setQuery("");
    },
    [],
  );

  const runAction = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router],
  );

  const recentRuns = runs?.slice(-8).reverse() ?? [];
  const hits = search.data?.items ?? [];
  const resultGroups = SEARCH_ENTITIES.map(({ value, label, icon }) => ({
    value,
    label,
    icon,
    hits: hits.filter((hit) => hit.entity === value),
  })).filter((group) => group.hits.length > 0);
  const hasSearchTerm = debouncedQuery.trim().length > 0;
  const searching = hasSearchTerm && search.isFetching && !search.data;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-8 w-56 items-center gap-2 rounded-md border border-input bg-muted/30 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <Search className="size-4" aria-hidden />
        <span className="flex-1 text-left">Search…</span>
        <kbd className="pointer-events-none inline-flex h-5 items-center gap-0.5 rounded border bg-muted px-1 font-mono text-[10px]">
          Ctrl<span className="text-muted-foreground">K</span>
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={handleOpenChange}>
        <CommandInput
          placeholder="Search runs, targets, entities…"
          value={query}
          onValueChange={setQuery}
        />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>

          <CommandGroup heading="Workspace">
            <CommandItem onSelect={() => runAction(withContext("/", context))}>
              <FlaskConical aria-hidden />
              Back to workspace
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/collect", context))}>
              <Compass aria-hidden />
              Collect data
            </CommandItem>
          </CommandGroup>

          <CommandGroup heading="Analyze">
            <CommandItem onSelect={() => runAction(withContext("/network", context))}>
              <Network aria-hidden />
              Recommendation network
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/network/full", context))}>
              <Microscope aria-hidden />
              Full network analytics
            </CommandItem>
            <CommandItem
              onSelect={() => runAction(withContext("/network/commenters", context))}
            >
              <Users aria-hidden />
              Commenters
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/compare", context))}>
              <GitCompare aria-hidden />
              Comparison workspace
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/query", context))}>
              <Search aria-hidden />
              Query console
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/explore", context))}>
              <Boxes aria-hidden />
              Record explorer
            </CommandItem>
          </CommandGroup>

          <CommandGroup heading="Data">
            <CommandItem onSelect={() => runAction(withContext("/data", context))}>
              <Table2 aria-hidden />
              Data coverage
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/datasets", context))}>
              <FolderOpen aria-hidden />
              Datasets
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/samples", context))}>
              <Database aria-hidden />
              Research samples
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/projects", context))}>
              <FolderKanban aria-hidden />
              Projects
            </CommandItem>
            <CommandItem onSelect={() => runAction(withContext("/runs", context))}>
              <ListOrdered aria-hidden />
              Provenance ledger
            </CommandItem>
          </CommandGroup>

          <CommandGroup heading="Docs">
            <CommandItem onSelect={() => runAction(withContext("/docs", context))}>
              <BookOpen aria-hidden />
              Documentation
            </CommandItem>
          </CommandGroup>

          {hasSearchTerm ? (
            <>
              <CommandSeparator />
              {searching ? (
                <LoadingState
                  label="Searching…"
                  className="min-h-24 py-4"
                />
              ) : resultGroups.length > 0 ? (
                resultGroups.map((group) => (
                  <CommandGroup
                    key={group.value}
                    heading={`${group.label} (${group.hits.length})`}
                  >
                    {group.hits.map((hit) => (
                      <CommandItem
                        key={`${hit.entity}-${hit.entity_id}`}
                        value={`${hit.entity} ${hit.title ?? ""} ${hit.subtitle ?? ""} ${hit.entity_id}`}
                        onSelect={() => runAction(searchHref(hit))}
                      >
                        <group.icon className="size-3.5 text-muted-foreground" aria-hidden />
                        <span className="truncate">
                          {hit.title ?? hit.entity_id}
                        </span>
                        {hit.subtitle ? (
                          <span className="ml-2 truncate text-xs text-muted-foreground">
                            {hit.subtitle}
                          </span>
                        ) : null}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                ))
              ) : null}
            </>
          ) : null}

          <CommandSeparator />

          <CommandGroup heading={`Recent runs (${recentRuns.length})`}>
            {recentRuns.map((run) => (
              <CommandItem
                key={run.run_id}
                value={`${run.run_id} ${run.target_url} ${run.target_channel_id ?? ""} ${run.target_video_id ?? ""}`}
                onSelect={() => runAction(withContext(`/runs/${run.run_id}`, context))}
              >
                <Play className="size-3.5 text-muted-foreground" aria-hidden />
                <span className="truncate">
                  {run.name ?? run.run_id} · {run.target_url}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(run.started_at)}
                  </span>
                  <RunStatusBadge status={run.status} />
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
