"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/features/state";
import { getDatasetQuality } from "@/services/datasets";
import { useDatasetList } from "@/services/queries";
import { formatNumber, formatPercent, formatDateTime } from "@/lib/format";

export function QualityPanel({ datasetId }: { datasetId: string }) {
  const query = useQuery({
    queryKey: ["datasets", datasetId, "quality"],
    queryFn: () => getDatasetQuality(datasetId),
  });
  const datasetsQuery = useDatasetList();
  const datasetName =
    (datasetsQuery.data?.pages ?? [])
      .flatMap((p) => p.items)
      .find((d) => d.dataset_id === datasetId)?.name ?? null;

  if (query.isLoading) return <LoadingState label="Loading quality…" />;
  if (query.isError)
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : "Failed to load dataset quality"
        }
        retry={() => query.refetch()}
      />
    );

  const quality = query.data;
  if (!quality) return <LoadingState label="Loading quality…" />;
  const coveragePct = Math.min(
    Math.max(Math.round(quality.overall_coverage * 100), 0),
    100,
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="truncate">
          {datasetName ?? datasetId}
          {datasetName ? (
            <code className="ml-2 text-muted-foreground">{datasetId}</code>
          ) : null}
        </span>
        <span>generated {formatDateTime(quality.generated_at)}</span>
      </div>

      <div className="space-y-2">
        <Progress value={coveragePct}>
          <ProgressLabel>Overall coverage</ProgressLabel>
          <ProgressValue>
            {() => formatPercent(quality.overall_coverage)}
          </ProgressValue>
        </Progress>
      </div>

      {quality.columns.length === 0 ? (
        <EmptyState
          title="No columns reported"
          description="The quality report returned no column breakdown for this dataset."
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Column</TableHead>
                <TableHead className="text-right">Present</TableHead>
                <TableHead className="text-right">Missing</TableHead>
                <TableHead className="text-right">Missing share</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {quality.columns.map((column) => (
                <TableRow key={column.name}>
                  <TableCell className="font-mono text-xs">
                    {column.name}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(column.present)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(column.missing)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {formatPercent(column.missing_share)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}