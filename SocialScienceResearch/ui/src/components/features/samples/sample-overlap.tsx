"use client";

import { useMemo } from "react";
import { Loader2, GitCompareArrows } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/features/state";
import { useCompareSamples } from "@/services/samples";
import { useToast } from "@/components/ui/toast";
import { formatPercent } from "@/lib/format";
import type { Sample, SampleCompareResult } from "@/lib/sample-types";

export function SampleOverlap({
  samples,
  onSelect,
  selected,
}: {
  samples: Sample[];
  onSelect: (sampleId: string) => void;
  selected: Set<string>;
}) {
  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">Compare samples</h3>
      <p className="mb-3 text-xs text-muted-foreground">
        Select two or more samples to compute pairwise overlap, union and
        Jaccard similarity.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        {samples.map((sample) => {
          const isSelected = selected.has(sample.sample_id);
          return (
            <button
              key={sample.sample_id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onSelect(sample.sample_id)}
              className="rounded-md border border-border px-2.5 py-1 text-xs outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:bg-primary aria-pressed:text-primary-foreground"
            >
              {sample.sample_id}
            </button>
          );
        })}
      </div>
    </Card>
  );
}

export function SampleCompareButton({
  selected,
}: {
  selected: string[];
}) {
  const { toast } = useToast();
  const compare = useCompareSamples();

  function run() {
    if (selected.length < 2) {
      toast({
        variant: "destructive",
        title: "Select at least two samples",
        description: "Pairwise overlap needs two or more samples.",
      });
      return;
    }
    compare.mutate(selected, {
      onError: (error) => {
        toast({
          variant: "destructive",
          title: "Comparison failed",
          description: error instanceof Error ? error.message : "Unknown error",
        });
      },
    });
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={run}
      disabled={compare.isPending}
    >
      {compare.isPending ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        <GitCompareArrows className="size-4" aria-hidden />
      )}
      Compare selected
    </Button>
  );
}

export function SampleCompareResultView({
  result,
}: {
  result: SampleCompareResult;
}) {
  const pairs = useMemo(() => {
    return Object.entries(result.pairwise).map(([key, value]) => {
      const [a, b] = key.split("|");
      return { a, b, ...value };
    });
  }, [result]);

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-medium">Overlap result</h3>
        <Badge variant="outline">{result.sample_ids.length} samples</Badge>
        <Badge variant="secondary">
          union {result.union_size.toLocaleString()}
        </Badge>
        <Badge variant="secondary">
          shared by all {result.intersection_size.toLocaleString()}
        </Badge>
      </div>

      {pairs.length > 0 ? (
        <Table aria-label="Pairwise sample overlap">
          <TableHeader>
            <TableRow>
              <TableHead>Sample A</TableHead>
              <TableHead>Sample B</TableHead>
              <TableHead className="text-right">Intersection</TableHead>
              <TableHead className="text-right">Union</TableHead>
              <TableHead className="text-right">Jaccard</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pairs.map((pair) => (
              <TableRow key={`${pair.a}|${pair.b}`}>
                <TableCell className="font-mono text-xs">{pair.a}</TableCell>
                <TableCell className="font-mono text-xs">{pair.b}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {pair.intersection_size.toLocaleString()}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {pair.union_size.toLocaleString()}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatPercent(pair.jaccard)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <EmptyState
          title="No pairwise results"
          description="The comparison returned no pairwise statistics."
        />
      )}

      {Object.keys(result.criteria_diffs).length > 0 ? (
        <div className="mt-4 space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Criteria differences vs first sample
          </h4>
          {Object.entries(result.criteria_diffs).map(([sampleId, fields]) =>
            fields.length === 0 ? null : (
              <div key={sampleId} className="flex items-start gap-2 text-xs">
                <code className="shrink-0">{sampleId}</code>
                <span className="text-muted-foreground">
                  {fields.join(", ")}
                </span>
              </div>
            ),
          )}
        </div>
      ) : null}
    </Card>
  );
}
