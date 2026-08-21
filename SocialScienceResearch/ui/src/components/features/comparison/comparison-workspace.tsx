"use client";

import { useState } from "react";
import { Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { LoadingState } from "@/components/features/state";
import { useCompare } from "@/services/comparison";
import { ComparisonTable } from "@/components/features/comparison/comparison-table";
import { NormalizationSelect } from "@/components/features/comparison/normalization-select";
import {
  ENTITY_METRICS,
  NORMALIZATION_LABEL,
  type ComparisonMode,
  type Normalization,
} from "@/lib/comparison-types";

export function ComparisonWorkspace() {
  const [mode, setMode] = useState<ComparisonMode>("videos");
  const [idsText, setIdsText] = useState("");
  const [metrics, setMetrics] = useState<string[]>(["views"]);
  const [normalization, setNormalization] = useState<Normalization>("none");
  const [result, setResult] = useState<unknown>(null);
  const { toast } = useToast();

  const compare = useCompare();

  const ids = parseIds(idsText);

  function run() {
    if (ids.length === 0 && mode !== "periods") {
      toast({
        variant: "destructive",
        title: "No entities selected",
        description: "Enter at least one id to compare.",
      });
      return;
    }
    if (metrics.length === 0) {
      toast({
        variant: "destructive",
        title: "No metrics selected",
        description: "Choose at least one metric.",
      });
      return;
    }
    compare.mutate(
      { mode, body: buildBody(mode, ids, metrics, normalization) },
      {
        onSuccess: (data) => setResult(data),
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Comparison failed",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <Tabs
          value={mode}
          onValueChange={(value) => setMode(value as ComparisonMode)}
        >
          <TabsList>
            <TabsTrigger value="videos">Videos</TabsTrigger>
            <TabsTrigger value="channels">Channels</TabsTrigger>
            <TabsTrigger value="periods">Periods</TabsTrigger>
            <TabsTrigger value="cohorts">Cohorts</TabsTrigger>
            <TabsTrigger value="runs">Runs</TabsTrigger>
          </TabsList>
          <div className="mt-4 space-y-4">
            <ModeInputs
              mode={mode}
              idsText={idsText}
              onIdsText={setIdsText}
            />

            <div className="space-y-1.5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Metrics
              </Label>
              <div className="flex flex-wrap gap-2">
                {ENTITY_METRICS[mode === "channels" ? "channel" : "video"].map(
                  (metric) => {
                    const checked = metrics.includes(metric);
                    return (
                      <label
                        key={metric}
                        className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-muted"
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(value) => {
                            setMetrics((prev) =>
                              value === true
                                ? [...prev, metric]
                                : prev.filter((m) => m !== metric),
                            );
                          }}
                        />
                        {metric}
                      </label>
                    );
                  },
                )}
              </div>
            </div>

            {mode === "videos" || mode === "channels" ? (
              <NormalizationSelect
                value={normalization}
                onChange={setNormalization}
              />
            ) : null}

            <Button type="button" onClick={run} disabled={compare.isPending}>
              {compare.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Comparing…
                </>
              ) : (
                <>
                  Compare
                  <ArrowRight className="size-4" aria-hidden />
                </>
              )}
            </Button>
          </div>
        </Tabs>
      </Card>

      <ResultView
        mode={mode}
        result={result}
        normalization={normalization}
        comparing={compare.isPending}
      />
    </div>
  );
}

function parseIds(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function buildBody(
  mode: ComparisonMode,
  ids: string[],
  metrics: string[],
  normalization: Normalization,
): unknown {
  switch (mode) {
    case "videos":
      return { video_ids: ids, metrics, normalization };
    case "channels":
      return { channel_ids: ids, metrics, normalization };
    case "periods":
      return {
        period_a: { name: "Period A", start: "2020-01-01", end: "2021-12-31" },
        period_b: { name: "Period B", start: "2022-01-01", end: "2023-12-31" },
        entity: "video",
        metrics,
      };
    case "cohorts":
      return {
        cohorts: ids.length
          ? ids.map((id) => ({ name: id, channel_id: id }))
          : [{ name: "All videos" }],
        metrics,
      };
    case "runs":
      return { run_ids: ids, metrics };
  }
}

function ModeInputs({
  mode,
  idsText,
  onIdsText,
}: {
  mode: ComparisonMode;
  idsText: string;
  onIdsText: (value: string) => void;
}) {
  const placeholder = {
    videos: "video_id_1, video_id_2, …",
    channels: "channel_id_1, channel_id_2, …",
    periods: "Date windows are fixed presets in this preview",
    cohorts: "channel_id per cohort (empty = all videos)",
    runs: "run_id_1, run_id_2, …",
  }[mode];

  return (
    <div className="space-y-1.5">
      <Label htmlFor="compare-ids" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {mode === "periods"
          ? "Period comparison"
          : mode === "cohorts"
            ? "Cohorts (one channel id per cohort)"
            : "Entity ids"}
      </Label>
      <Input
        id="compare-ids"
        value={idsText}
        onChange={(event) => onIdsText(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
      <p className="text-xs text-muted-foreground">
        {mode === "periods"
          ? "Compares upload-date windows 2020–2021 vs 2022–2023 for video metrics."
          : mode === "cohorts"
            ? "Each id becomes a named cohort scoped to that channel; leave empty for one cohort over all videos."
            : "Space or comma separated ids. Only latest observed values are compared."}
      </p>
    </div>
  );
}

function ResultView({
  mode,
  result,
  normalization,
  comparing,
}: {
  mode: ComparisonMode;
  result: unknown;
  normalization: Normalization;
  comparing: boolean;
}) {
  if (comparing) {
    return <LoadingState label="Computing comparison…" />;
  }
  if (!result) {
    return null;
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Comparison result</h2>
        <Badge variant="secondary">{NORMALIZATION_LABEL[normalization]}</Badge>
      </div>
      <ComparisonTable mode={mode} result={result} />
    </div>
  );
}
