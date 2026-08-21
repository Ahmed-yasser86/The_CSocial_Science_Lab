"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/features/state";
import { Pagination, type PaginationProps } from "@/components/ui/pagination";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => number | string | null | undefined;
  className?: string;
  headerClassName?: string;
}

type SortDirection = "asc" | "desc";

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  emptyTitle = "No records",
  emptyDescription,
  initialSortKey,
  initialSortDirection = "asc",
  ariaLabel,
  pagination,
  onRowClick,
}: {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  emptyTitle?: string;
  emptyDescription?: string;
  initialSortKey?: string;
  initialSortDirection?: SortDirection;
  ariaLabel?: string;
  pagination?: PaginationProps;
  onRowClick?: (row: T) => void;
}) {
  const [sortKey, setSortKey] = useState<string | undefined>(initialSortKey);
  const [sortDirection, setSortDirection] =
    useState<SortDirection>(initialSortDirection);

  const sorted = useMemo(() => {
    if (!sortKey || !rows) return rows;
    const column = columns.find((c) => c.key === sortKey);
    if (!column?.sortValue) return rows;
    const dir = sortDirection === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * dir;
      }
      return String(av).localeCompare(String(bv)) * dir;
    });
  }, [columns, rows, sortKey, sortDirection]);

  function toggleSort(key: string) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDirection("asc");
    } else {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    }
  }

  if (!rows || rows.length === 0) {
    return (
      <EmptyState title={emptyTitle} description={emptyDescription} />
    );
  }

  return (
    <div className="w-full overflow-x-auto rounded-md border">
      <Table aria-label={ariaLabel}>
        <TableHeader>
          <TableRow>
            {columns.map((column) => {
              const active = sortKey === column.key;
              const sortable = Boolean(column.sortable && column.sortValue);
              return (
                <TableHead
                  key={column.key}
                  className={column.headerClassName}
                  aria-sort={
                    active
                      ? sortDirection === "asc"
                        ? "ascending"
                        : "descending"
                      : undefined
                  }
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="inline-flex items-center gap-1 hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                    >
                      {column.header}
                      {active ? (
                        sortDirection === "asc" ? (
                          <ArrowUp className="size-3.5" aria-hidden />
                        ) : (
                          <ArrowDown className="size-3.5" aria-hidden />
                        )
                      ) : (
                        <ArrowUpDown className="size-3.5 opacity-40" aria-hidden />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => (
            <TableRow
              key={getRowKey(row)}
              className={onRowClick ? "cursor-pointer hover:bg-muted/50" : undefined}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((column) => (
                <TableCell key={column.key} className={cn(column.className)}>
                  {column.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {pagination ? <Pagination {...pagination} /> : null}
    </div>
  );
}
