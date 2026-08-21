"use client";

import { useEffect, useRef, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/state";
import type { ExplorerColumn, ExplorerEntity } from "@/lib/explorer-types";

const MAX_COLUMNS = 8;
const ROW_HEIGHT = 36;
const OVERSCAN = 8;

export function columnValueClass(dataType: string): string {
  switch (dataType) {
    case "int":
    case "float":
      return "text-right tabular-nums";
    case "bool":
      return "text-center";
    default:
      return "font-mono text-xs";
  }
}

export function formatCellValue(value: unknown, dataType: string): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  switch (dataType) {
    case "bool":
      return <Badge variant={value === true ? "default" : "secondary"}>{String(value)}</Badge>;
    case "int":
    case "float":
      return new Intl.NumberFormat("en-US").format(Number(value));
    default:
      return String(value);
  }
}

export interface PaginatedDataTableProps {
  entity: ExplorerEntity;
  columns: ExplorerColumn[];
  rows: Record<string, unknown>[];
  total: number | null;
  hasMore: boolean;
  nextCursor: string | null;
  isFetching: boolean;
  onNext: () => void;
  onPrev: () => void;
  hasPrevious: boolean;
  onSelectRow?: (row: Record<string, unknown>) => void;
  renderIdCell?: (value: string, row: Record<string, unknown>) => React.ReactNode;
  renderExpandedActions?: (row: Record<string, unknown>) => React.ReactNode;
}

export function PaginatedDataTable({
  entity,
  columns,
  rows,
  total,
  hasMore,
  nextCursor,
  isFetching,
  onNext,
  onPrev,
  hasPrevious,
  onSelectRow,
  renderIdCell,
  renderExpandedActions,
}: PaginatedDataTableProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const scrollRef = useRef<HTMLDivElement>(null);
  const visibleColumns = columns.slice(0, MAX_COLUMNS);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setViewportHeight(el.clientHeight || 600);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") el.scrollTo({ top: 0 });
  }, [entity, rows]);

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No records match"
        description="Adjust the search text or filters to widen the result set."
      />
    );
  }

  const idColumn =
    entity === "recommendation"
      ? "observation_id"
      : `${entity}_id`;

  const totalRows = rows.length;
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const end = Math.min(
    totalRows,
    Math.ceil((scrollTop + viewportHeight) / ROW_HEIGHT) + OVERSCAN,
  );
  const visibleRows = rows.slice(start, end);
  const columnCount = visibleColumns.length + 1;

  function handleScroll(event: React.UIEvent<HTMLDivElement>) {
    setScrollTop(event.currentTarget.scrollTop);
  }

  // Generate a guaranteed-unique key per rendered row. The entity id is
  // prefixed for stable identity, and the absolute virtual index is appended so
  // two rows sharing the same id (e.g. historical duplicates in the store) can
  // never collide - React keys must be unique across the rendered list.
  function getRowKey(row: Record<string, unknown>, idx: number): string {
    const position = start + idx;
    const id = row[idColumn];
    if (id !== undefined && id !== null) {
      return `${String(id)}__${position}`;
    }
    const fallback = row.video_id ?? row.comment_id ?? row.channel_id ?? row.recommended_video_id ?? row.author_id;
    if (fallback !== undefined && fallback !== null) {
      return `${String(fallback)}__${position}`;
    }
    const rowStr = JSON.stringify(row);
    let hash = 0;
    for (let i = 0; i < rowStr.length; i++) {
      hash = ((hash << 5) - hash) + rowStr.charCodeAt(i);
      hash |= 0;
    }
    return `row-${position}-${Math.abs(hash)}`;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {total !== null && total !== undefined
            ? `${total.toLocaleString()} records`
            : `${rows.length} records on this page`}
        </span>
        <span className="font-mono">entity: {entity}</span>
      </div>

      <div className="w-full overflow-hidden rounded-md border">
        <Table
          aria-label={`${entity} explorer table`}
          wrapperRef={scrollRef}
          onWrapperScroll={handleScroll}
          wrapperClassName="max-h-[65vh] overflow-y-auto"
        >
          <TableHeader className="sticky top-0 z-10 bg-background">
            <TableRow>
              <TableHead className="w-10" aria-hidden />
              {visibleColumns.map((column) => (
                <TableHead key={column.name} className={columnValueClass(column.data_type)}>
                  {column.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {start > 0 ? (
              <tr aria-hidden="true" style={{ height: start * ROW_HEIGHT }}>
                <td colSpan={columnCount} style={{ height: start * ROW_HEIGHT, padding: 0 }} />
              </tr>
            ) : null}
            {visibleRows.map((row, index) => {
              const key = getRowKey(row, index);
              const isExpanded = expanded === start + index;
              return (
                <TableRow key={key}>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-expanded={isExpanded}
                      aria-label={isExpanded ? "Hide details" : "Show details"}
                      onClick={() =>
                        setExpanded(isExpanded ? null : start + index)
                      }
                    >
                      {isExpanded ? "–" : "+"}
                    </Button>
                  </TableCell>
                  {visibleColumns.map((column) => {
                    const value = row[column.name];
                    const isIdColumn = column.name === idColumn;
                    const content =
                      isIdColumn && renderIdCell && value !== undefined && value !== null
                        ? renderIdCell(String(value), row) ?? formatCellValue(value, column.data_type)
                        : formatCellValue(value, column.data_type);
                    return (
                      <TableCell key={column.name} className={columnValueClass(column.data_type)}>
                        {content}
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
            {end < totalRows ? (
              <tr aria-hidden="true" style={{ height: (totalRows - end) * ROW_HEIGHT }}>
                <td
                  colSpan={columnCount}
                  style={{ height: (totalRows - end) * ROW_HEIGHT, padding: 0 }}
                />
              </tr>
            ) : null}
          </TableBody>
        </Table>
      </div>

      {expanded !== null && expanded < rows.length ? (
        <div className="rounded-md border bg-muted/20 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-medium">Full row</h3>
            <div className="flex flex-wrap items-center gap-2">
              {renderExpandedActions ? renderExpandedActions(rows[expanded]) : null}
              {onSelectRow ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onSelectRow(rows[expanded])}
                >
                  Open record
                </Button>
              ) : null}
            </div>
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(rows[expanded]).map(([name, value]) => {
              const meta = columns.find((c) => c.name === name);
              return (
                <div key={name} className="flex items-baseline justify-between gap-2">
                  <dt className="text-xs text-muted-foreground">{name}</dt>
                  <dd className={columnValueClass(meta?.data_type ?? "string")}>
                    {formatCellValue(value, meta?.data_type ?? "string")}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3 border-t pt-3">
        <p className="text-xs text-muted-foreground">
          {hasMore ? "More records available" : "End of results"}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onPrev}
            disabled={isFetching || !hasPrevious}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onNext}
            disabled={isFetching || !hasMore || !nextCursor}
          >
            {isFetching ? "Loading…" : "Next"}
          </Button>
        </div>
      </div>
    </div>
  );
}
