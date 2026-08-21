"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LoadingState, ErrorState } from "@/components/features/state";
import { PaginatedDataTable } from "@/components/features/explorer/paginated-data-table";
import { DetailDrawer } from "@/components/features/explorer/detail-drawer";
import { VideoMetadataPreview } from "@/components/features/video-metadata-preview";
import { useExploreRecords } from "@/services/explorer";
import type {
  ExplorerEntity,
  ExplorerFilter,
  ExplorePage,
} from "@/lib/explorer-types";

const ENTITIES: { value: ExplorerEntity; label: string }[] = [
  { value: "video", label: "Video" },
  { value: "channel", label: "Channel" },
  { value: "comment", label: "Comment" },
  { value: "recommendation", label: "Recommendation" },
  { value: "author", label: "Author" },
];

export function RecordExplorer({
  initialEntity,
  initialQuery,
}: {
  initialEntity?: string;
  initialQuery?: string;
}) {
  const initial = ENTITIES.some((e) => e.value === initialEntity)
    ? (initialEntity as ExplorerEntity)
    : "video";
  const [entity, setEntity] = useState<ExplorerEntity>(initial);
  const [query, setQuery] = useState(initialQuery ?? "");
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery ?? "");
  const [filters, setFilters] = useState<ExplorerFilter[]>([]);
  const [sort, setSort] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [selected, setSelected] = useState<{
    entity: string;
    entityId: string;
    row: Record<string, unknown>;
  } | null>(null);

  const result = useExploreRecords(entity, debouncedQuery, filters, sort, cursor);

  function runSearch() {
    setDebouncedQuery(query.trim());
    setCursor(null);
    setHistory([]);
  }

  function changeEntity(next: ExplorerEntity) {
    setEntity(next);
    setQuery("");
    setDebouncedQuery("");
    setFilters([]);
    setSort(null);
    setCursor(null);
    setHistory([]);
    setSelected(null);
  }

  function goNext() {
    if (!result.data?.has_more || !result.data.next_cursor) return;
    setHistory((prev) => [...prev, cursor ?? "0"]);
    setCursor(result.data.next_cursor);
  }

  function goPrev() {
    const prevCursor = history[history.length - 1];
    setHistory((prev) => prev.slice(0, -1));
    setCursor(prevCursor ?? null);
  }

  function openRecord(row: Record<string, unknown>) {
    const idColumn =
      entity === "recommendation" ? "observation_id" : `${entity}_id`;
    const entityId = String(row[idColumn] ?? "");
    if (!entityId) return;
    setSelected({ entity, entityId, row });
  }

  const columns = result.data?.columns ?? [];
  const rows = result.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="explorer-entity" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Entity
          </Label>
          <Select
            value={entity}
            onValueChange={(value) => changeEntity((value ?? "video") as ExplorerEntity)}
            items={ENTITIES.map((e) => ({ value: e.value, label: e.label }))}
          >
            <SelectTrigger id="explorer-entity" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ENTITIES.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <form
          className="flex min-w-64 flex-1 gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch();
          }}
        >
          <div className="relative flex-1">
            <Label htmlFor="explorer-search" className="sr-only">
              Search records
            </Label>
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              id="explorer-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search text fields…"
              className="pl-8"
              autoComplete="off"
            />
          </div>
          <Button type="submit" variant="outline" size="sm">
            Search
          </Button>
        </form>

        {sortOptions(result.data).length > 0 ? (
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Sort
            </Label>
            <Select
              value={sort ?? ""}
              onValueChange={(value) => {
                setSort(value || null);
                setCursor(null);
                setHistory([]);
              }}
              items={[
                { value: "", label: "Default order" },
                ...sortOptions(result.data).map((o) => ({
                  value: o.variable,
                  label: o.variable,
                })),
              ]}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Default order" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Default order</SelectItem>
                {sortOptions(result.data).map((o) => (
                  <SelectItem key={o.variable} value={o.variable}>
                    {o.variable}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </div>

      <FilterBar
        result={result.data}
        filters={filters}
        onChange={(next) => {
          setFilters(next);
          setCursor(null);
          setHistory([]);
        }}
      />

      {result.isLoading ? (
        <LoadingState label="Loading records…" />
      ) : result.isError ? (
        <ErrorState
          message={
            result.error instanceof Error
              ? result.error.message
              : "Failed to load explorer records"
          }
          retry={() => result.refetch()}
        />
      ) : (
        <PaginatedDataTable
          entity={entity}
          columns={columns}
          rows={rows}
          total={result.data?.total ?? null}
          hasMore={result.data?.has_more ?? false}
          nextCursor={result.data?.next_cursor ?? null}
          isFetching={result.isFetching}
          onNext={goNext}
          onPrev={goPrev}
          hasPrevious={history.length > 0}
          onSelectRow={openRecord}
          renderIdCell={(value, row) => {
            const href = detailHref(entity, row);
            if (!href) return null;
            return (
              <Link
                href={href}
                className="text-primary underline-offset-2 hover:underline"
              >
                {value}
              </Link>
            );
          }}
          renderExpandedActions={(row) => {
            const href =
              entity === "comment"
                ? commentThreadHref(row)
                : detailHref(entity, row);
            if (!href) return null;
            return (
              <Button
                render={<Link href={href} />}
                nativeButton={false}
                variant="outline"
                size="sm"
              >
                {entity === "comment" ? "View reply tree" : "View details"}
              </Button>
            );
          }}
        />
      )}

      <DetailDrawer
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
        entity={selected?.entity ?? entity}
        entityId={selected?.entityId ?? ""}
        row={selected?.row ?? {}}
        columns={columns}
      />
      {selected?.entity === "video" && (
        <VideoMetadataPreview
          open={!!selected}
          onOpenChange={(open) => {
            if (!open) setSelected(null);
          }}
          videoId={selected.entityId}
        />
      )}
    </div>
  );
}

function sortOptions(page: ExplorePage | undefined) {
  return page?.sort_options ?? [];
}

function hasValue(value: unknown): boolean {
  return value !== undefined && value !== null && String(value) !== "";
}

function detailHref(
  entity: ExplorerEntity,
  row: Record<string, unknown>,
): string | null {
  if (entity === "video" && hasValue(row.video_id)) {
    return `/videos/${row.video_id}`;
  }
  if (entity === "channel" && hasValue(row.channel_id)) {
    return `/channels/${row.channel_id}`;
  }
  return null;
}

function commentThreadHref(row: Record<string, unknown>): string | null {
  if (!hasValue(row.video_id) || !hasValue(row.comment_id)) return null;
  return `/videos/${row.video_id}?tab=comments&thread=${row.comment_id}`;
}

const FILTER_OPERATORS = [
  "eq",
  "neq",
  "contains",
  "not_contains",
  "in",
  "not_in",
  "gt",
  "gte",
  "lt",
  "lte",
  "is_null",
  "not_null",
] as const;

function FilterBar({
  result,
  filters,
  onChange,
}: {
  result: ExplorePage | undefined;
  filters: ExplorerFilter[];
  onChange: (next: ExplorerFilter[]) => void;
}) {
  const columns = result?.columns ?? [];
  const [draftVariable, setDraftVariable] = useState("");
  const [draftOperator, setDraftOperator] = useState<string>("eq");
  const [draftValue, setDraftValue] = useState("");

  function addFilter() {
    if (!draftVariable) return;
    const next: ExplorerFilter = {
      variable: draftVariable,
      operator: draftOperator as ExplorerFilter["operator"],
    };
    if (!draftOperator.startsWith("is_") && draftValue !== "") {
      const dataType = columns.find((c) => c.name === draftVariable)?.data_type;
      next.value =
        dataType === "int"
          ? Number(draftValue)
          : dataType === "float"
            ? Number(draftValue)
            : draftOperator === "in" || draftOperator === "not_in"
              ? draftValue
                  .split(",")
                  .map((part) => part.trim())
                  .filter(Boolean)
              : draftValue;
    }
    onChange([...filters, next]);
    setDraftVariable("");
    setDraftOperator("eq");
    setDraftValue("");
  }

  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">Filters</span>
        {filters.map((filter, index) => (
          <span
            key={`${filter.variable}-${index}`}
            className="inline-flex items-center gap-1 rounded-full border bg-background px-2 py-0.5 text-xs"
          >
            <code>{filter.variable}</code>
            <span className="text-muted-foreground">{filter.operator}</span>
            {filter.operator !== "is_null" && filter.operator !== "not_null" ? (
              <code className="text-muted-foreground">
                {Array.isArray(filter.value)
                  ? filter.value.join(",")
                  : String(filter.value)}
              </code>
            ) : null}
            <button
              type="button"
              onClick={() =>
                onChange(filters.filter((_, i) => i !== index))
              }
              aria-label={`Remove filter on ${filter.variable}`}
              className="text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </span>
        ))}
      </div>

      {columns.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label
              htmlFor="explorer-filter-variable"
              className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              Variable
            </Label>
            <Select
              value={draftVariable}
              onValueChange={(value) => setDraftVariable(value ?? "")}
              items={columns.map((c) => ({ value: c.name, label: c.name }))}
            >
              <SelectTrigger id="explorer-filter-variable" className="w-44">
                <SelectValue placeholder="Select variable…" />
              </SelectTrigger>
              <SelectContent>
                {columns.map((column) => (
                  <SelectItem key={column.name} value={column.name}>
                    {column.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label
              htmlFor="explorer-filter-operator"
              className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              Operator
            </Label>
            <Select
              value={draftOperator}
              onValueChange={(value) => setDraftOperator(value ?? "eq")}
              items={FILTER_OPERATORS.map((op) => ({ value: op, label: op }))}
            >
              <SelectTrigger id="explorer-filter-operator" className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FILTER_OPERATORS.map((op) => (
                  <SelectItem key={op} value={op}>
                    {op}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {!draftOperator.startsWith("is_") ? (
            <div className="space-y-1">
              <Label
                htmlFor="explorer-filter-value"
                className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
              >
                Value
              </Label>
              <Input
                id="explorer-filter-value"
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                placeholder={
                  draftOperator === "in" || draftOperator === "not_in"
                    ? "Comma-separated values"
                    : "Value"
                }
                className="w-48"
                autoComplete="off"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addFilter();
                  }
                }}
              />
            </div>
          ) : null}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addFilter}
            disabled={!draftVariable}
          >
            Add filter
          </Button>
          {filters.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onChange([])}
            >
              Clear
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
