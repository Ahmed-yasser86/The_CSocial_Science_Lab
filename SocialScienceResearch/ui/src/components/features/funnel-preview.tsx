"use client";

import { Loader2, TrendingDown } from "lucide-react";
import type { QueryPreviewResult } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export function FunnelPreview({
  result,
  loading,
  error,
}: {
  result: QueryPreviewResult | null;
  loading: boolean;
  error?: string | null;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm font-medium">
          <TrendingDown className="size-4 text-muted-foreground" aria-hidden />
          Funnel preview
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <div className="flex min-h-24 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            <p className="text-sm">Evaluating population…</p>
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : !result ? (
          <p className="text-sm text-muted-foreground">
            Add at least one condition to preview the funnel.
          </p>
        ) : (
          <>
            <div className="flex items-baseline justify-between text-xs text-muted-foreground">
              <span>
                Population{" "}
                <span className="font-medium text-foreground">
                  {formatNumber(result.population_size)}
                </span>
              </span>
              <span>
                Matched{" "}
                <span className="font-medium text-foreground">
                  {formatNumber(result.n)}
                </span>
                {" · "}
                <span className="font-medium text-foreground">
                  {formatNumber(result.total)}
                </span>{" "}
                total
              </span>
            </div>
            <Separator />
            {result.stages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Empty funnel. Conditions only match observed values.
              </p>
            ) : (
              <div className="space-y-2">
                {result.stages.map((stage, index) => {
                  const share =
                    result.population_size > 0
                      ? (stage.cumulative / result.population_size) * 100
                      : 0;
                  return (
                    <div key={index} className="space-y-1">
                      <div className="flex items-baseline justify-between gap-2 text-xs">
                        <span
                          className="truncate text-muted-foreground"
                          title={stage.condition}
                        >
                          {stage.condition}
                        </span>
                        <span className="shrink-0 text-muted-foreground">
                          {formatNumber(stage.matched)} dropped ·{" "}
                          <span className="font-medium text-foreground">
                            {formatNumber(stage.cumulative)}
                          </span>{" "}
                          kept
                        </span>
                      </div>
                      <div
                        className="h-2 overflow-hidden rounded-full bg-muted"
                        role="presentation"
                      >
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${share}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}