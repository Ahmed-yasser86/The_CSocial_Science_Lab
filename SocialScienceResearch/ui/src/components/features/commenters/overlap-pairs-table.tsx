"use client";

import { useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable, type Column } from "@/components/features/data-table";
import type { PairOverlap } from "@/lib/commenter-overlap-types";

const fmt = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "–" : v.toFixed(digits);

export function OverlapPairsTable({ pairs }: { pairs: PairOverlap[] }) {
  const [selectedPair, setSelectedPair] = useState<PairOverlap | null>(null);

  const columns: Column<PairOverlap>[] = [
    {
      key: "entity_a",
      header: "Entity A",
      cell: (p) => p.entity_a,
      sortValue: (p) => p.entity_a,
    },
    {
      key: "entity_b",
      header: "Entity B",
      cell: (p) => p.entity_b,
      sortValue: (p) => p.entity_b,
    },
    {
      key: "set_size_a",
      header: "|A|",
      cell: (p) => p.set_size_a,
      sortValue: (p) => p.set_size_a,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "set_size_b",
      header: "|B|",
      cell: (p) => p.set_size_b,
      sortValue: (p) => p.set_size_b,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "intersection_size",
      header: "Shared",
      cell: (p) => p.intersection_size,
      sortValue: (p) => p.intersection_size,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "unique_a",
      header: "Unique A",
      cell: (p) => p.unique_a,
      sortValue: (p) => p.unique_a,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "unique_b",
      header: "Unique B",
      cell: (p) => p.unique_b,
      sortValue: (p) => p.unique_b,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "jaccard",
      header: "Jaccard",
      cell: (p) => fmt(p.jaccard),
      sortValue: (p) => p.jaccard ?? null,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "overlap_coefficient",
      header: "Overlap coeff.",
      cell: (p) => fmt(p.overlap_coefficient),
      sortValue: (p) => p.overlap_coefficient ?? null,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "reach_overlap_pct",
      header: "Reach %",
      cell: (p) => fmt(p.reach_overlap_pct, 1),
      sortValue: (p) => p.reach_overlap_pct ?? null,
      className: "text-right",
      headerClassName: "text-right",
    },
    {
      key: "total_shared",
      header: "Shared count",
      cell: (p) => p.total_shared,
      sortValue: (p) => p.total_shared,
      className: "text-right",
      headerClassName: "text-right",
    },
  ];

  return (
    <div className="space-y-4">
      <DataTable
        columns={columns}
        rows={pairs}
        getRowKey={(p) => `${p.entity_a}:${p.entity_b}`}
        initialSortKey="jaccard"
        initialSortDirection="desc"
        ariaLabel="Overlap pairs"
        onRowClick={setSelectedPair}
      />

      {selectedPair ? (
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="text-sm font-medium">
              Shared commenters: {selectedPair.entity_a} ↔ {selectedPair.entity_b}
            </h4>
            <Badge variant="outline">
              {selectedPair.total_shared} shared
            </Badge>
          </div>
          {selectedPair.shared_commenters.length ? (
            <ul className="divide-y divide-border">
              {selectedPair.shared_commenters.map((commenter) => (
                <li key={commenter.author_key} className="py-1.5">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <Link
                      href={`/network/commenters/${encodeURIComponent(commenter.author_key)}`}
                      className="font-medium underline underline-offset-2 hover:text-foreground"
                    >
                      {commenter.author_name ?? commenter.author_key}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {commenter.author_key}
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      {commenter.identity_kind === "id" ? "id-backed" : "name-only"}
                    </Badge>
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                      {commenter.count_a} on A · {commenter.count_b} on B ·{" "}
                      {commenter.total_comments} total
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No shared commenters.</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}
