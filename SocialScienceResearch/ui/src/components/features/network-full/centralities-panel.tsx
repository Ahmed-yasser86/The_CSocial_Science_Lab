"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNumber } from "@/lib/format";
import {
  CENTRALITY_MEASURES,
  type NetworkCentralities,
  type NodeCentrality,
} from "@/lib/network-full-types";
import { useNetworkCentralities } from "@/services/networkFull";

const DEFAULT_VISIBLE: (keyof NodeCentrality)[] = [
  "degree",
  "eigenvector",
  "betweenness",
  "pagerank",
];

export function CentralitiesPanel({
  runId,
  topN = 25,
  titleFor,
  hrefFor,
}: {
  runId?: string | null;
  topN?: number;
  /** Maps a node id to a human title (falls back to the raw id). */
  titleFor?: (id: string) => string | undefined;
  /** Link target for each node (e.g. the video's detail page). */
  hrefFor?: (id: string) => string | undefined;
}) {
  const { data, isLoading, isError, error, refetch } = useNetworkCentralities({
    run_id: runId ?? undefined,
    projection: "video",
  });

  if (isLoading) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-muted-foreground">Loading centralities…</p>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load centralities"}
        </p>
      </Card>
    );
  }

  if (!data || Object.keys(data.nodes).length === 0) {
    return (
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">Node centralities</h3>
        <p className="text-sm text-muted-foreground">
          No nodes available for centrality analysis.
        </p>
      </Card>
    );
  }

  return (
    <CentralitiesTable data={data} topN={topN} titleFor={titleFor} hrefFor={hrefFor} />
  );
}

function CentralitiesTable({
  data,
  topN,
  titleFor,
  hrefFor,
}: {
  data: NetworkCentralities;
  topN: number;
  titleFor?: (id: string) => string | undefined;
  hrefFor?: (id: string) => string | undefined;
}) {
  const [visible, setVisible] = useState<Set<keyof NodeCentrality>>(
    () => new Set(DEFAULT_VISIBLE),
  );

  const rows = useMemo(() => {
    const entries = Object.entries(data.nodes).map(([node, c]) => ({
      node,
      ...c,
    }));
    return entries
      .sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0))
      .slice(0, topN);
  }, [data, topN]);

  const measures = CENTRALITY_MEASURES.filter((m) => visible.has(m.key));

  const toggle = (key: keyof NodeCentrality) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Node centralities</h3>
        <div className="flex items-center gap-2">
          {data.approximate ? (
            <Badge variant="outline" title="Betweenness/bridging use k-sampled approximation on large graphs">
              approximate
            </Badge>
          ) : null}
          <Badge variant="outline" className="tabular-nums">
            {Object.keys(data.nodes).length} nodes · {data.algorithm}
          </Badge>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Measures
        </Label>
        {CENTRALITY_MEASURES.map((m) => {
          const on = visible.has(m.key);
          return (
            <button
              key={String(m.key)}
              type="button"
              aria-pressed={on}
              title={m.meaning}
              onClick={() => toggle(m.key)}
              className={
                "rounded-full border px-2.5 py-0.5 text-xs outline-none focus-visible:border-ring " +
                (on
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted")
              }
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {data.global?.assortativity != null ? (
        <p className="mb-2 text-xs text-muted-foreground">
          Degree assortativity: {data.global.assortativity.toFixed(3)} (
          {data.global.assortativity >= 0
            ? "popular nodes link popular nodes"
            : "popular nodes link niche nodes"}
          )
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-md border">
        <Table aria-label="Node centralities">
          <TableHeader>
            <TableRow>
              <TableHead>Node</TableHead>
              {measures.map((m) => (
                <TableHead key={String(m.key)} className="text-right" title={m.meaning}>
                  {m.label}
                </TableHead>
              ))}
              <TableHead className="text-right">Community</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const nodeTitle = titleFor?.(row.node);
              const nodeHref = hrefFor?.(row.node);
              return (
              <TableRow key={row.node}>
                <TableCell className="font-mono text-xs">
                  {nodeHref ? (
                    <Link
                      href={nodeHref}
                      className="flex min-w-0 flex-col hover:text-primary"
                      title={row.node}
                    >
                      <span className="truncate">{nodeTitle ?? row.node}</span>
                      {nodeTitle ? (
                        <span className="truncate text-[10px] font-normal text-muted-foreground">
                          {row.node}
                        </span>
                      ) : null}
                    </Link>
                  ) : (
                    <span className="truncate">{nodeTitle ?? row.node}</span>
                  )}
                </TableCell>
                {measures.map((m) => (
                  <TableCell key={String(m.key)} className="text-right tabular-nums">
                    {formatNumber(row[m.key] as number)}
                  </TableCell>
                ))}
                <TableCell className="text-right tabular-nums">
                  {row.community_id === null || row.community_id === undefined
                    ? "—"
                    : formatNumber(row.community_id)}
                </TableCell>
              </TableRow>
            );
            })}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}
