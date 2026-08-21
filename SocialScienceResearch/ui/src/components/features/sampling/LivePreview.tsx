"use client";

import { RefreshCw, Users, FlaskConical, ListChecks } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/format";
import type { SamplingResult } from "@/services/api";

export interface WorkbenchFilters {
  excludeAuthorIds: string[];
  includeAuthorIds: string[];
  excludeAuthorNames: string[];
  includeAuthorNames: string[];
  includeChannelIds: string[];
  excludeVideoAuthor: boolean;
  videoType: string;
  durationMin?: number;
  durationMax?: number;
  viewsMin?: number;
  viewsMax?: number;
  uploadDateFrom?: string;
  uploadDateTo?: string;
  categories: string[];
  videoIds: string[];
  tags: string[];
  minLikes?: number;
  maxLikes?: number;
  minReplies?: number;
  maxReplies?: number;
  commentType: "all" | "roots" | "replies";
  commentKeywords: string[];
  matchMode: "any" | "all";
  overlapMode: "off" | "video" | "channel";
  overlapMin: number;
  overlapVideoIds: string[];
  overlapChannelIds: string[];
  videoDateFrom?: string;
  videoDateTo?: string;
}

export interface WorkbenchLabels {
  researchQuestion: string;
  methodology: string;
  notes: string;
  customLabels: { key: string; value: string }[];
}

export type SamplingMethod = "full" | "random" | "stratified" | "topMetric";

export type TopMetric = "views" | "likes" | "comments" | "replies";

export interface WorkbenchState {
  scopeType: "all" | "channel" | "author" | "custom";
  channelIds: string[];
  authorIds: string[];
  runScope: "all" | "specific";
  runIds: string[];
  filters: WorkbenchFilters;
  samplingMethod: SamplingMethod;
  sampleSize: string;
  samplePercent: string;
  seed: string;
  strataVariable: string;
  samplesPerStratum: string;
  topMetric: TopMetric;
  topPercent: string;
  labels: WorkbenchLabels;
  saveOption: "individual" | "dataset";
  datasetName: string;
  entityType: "video" | "comment";
}

export interface LivePreviewProps {
  state: WorkbenchState;
  onRefresh: () => void;
  isRefreshing: boolean;
  previewResult?: SamplingResult | null;
}

const INITIAL_FILTERS: WorkbenchFilters = {
  excludeAuthorIds: [],
  includeAuthorIds: [],
  excludeAuthorNames: [],
  includeAuthorNames: [],
  includeChannelIds: [],
  excludeVideoAuthor: false,
  videoType: "any",
  durationMin: undefined,
  durationMax: undefined,
  viewsMin: undefined,
  viewsMax: undefined,
  uploadDateFrom: undefined,
  uploadDateTo: undefined,
  categories: [],
  videoIds: [],
  tags: [],
  minLikes: undefined,
  maxLikes: undefined,
  minReplies: undefined,
  maxReplies: undefined,
  commentType: "all",
  commentKeywords: [],
  matchMode: "any",
  overlapMode: "off",
  overlapMin: 2,
  overlapVideoIds: [],
  overlapChannelIds: [],
  videoDateFrom: undefined,
  videoDateTo: undefined,
};

const INITIAL_LABELS: WorkbenchLabels = {
  researchQuestion: "",
  methodology: "",
  notes: "",
  customLabels: [],
};

const INITIAL_STATE: WorkbenchState = {
  scopeType: "all",
  channelIds: [],
  authorIds: [],
  runScope: "all",
  runIds: [],
  filters: { ...INITIAL_FILTERS },
  samplingMethod: "random",
  sampleSize: "500",
  samplePercent: "",
  seed: "",
  strataVariable: "month",
  samplesPerStratum: "50",
  topMetric: "replies",
  topPercent: "10",
  labels: { ...INITIAL_LABELS },
  saveOption: "individual",
  datasetName: "",
  entityType: "comment",
};

export function LivePreview({ onRefresh, isRefreshing, previewResult }: LivePreviewProps) {
  const sampleIds = previewResult?.entity_ids ?? [];
  const displayIds = sampleIds.slice(0, 10);
  const populationSize = previewResult?.population_size ?? 0;
  const sampleSize = previewResult?.sample_size ?? 0;

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
                <FlaskConical className="size-3.5" aria-hidden />
              </span>
              Live Preview
            </CardTitle>
            <CardDescription>
              Sizes update when you preview or run a sample.
            </CardDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label="Refresh preview"
          >
            <RefreshCw className={`size-4 ${isRefreshing ? "animate-spin" : ""}`} aria-hidden />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border bg-muted/40 p-3.5">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Users className="size-3.5" aria-hidden />
              Population
            </div>
            <p className="mt-1.5 text-xl font-semibold tabular-nums tracking-tight">
              {previewResult ? formatNumber(populationSize) : "—"}
            </p>
          </div>
          <div className="rounded-xl border bg-muted/40 p-3.5">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ListChecks className="size-3.5" aria-hidden />
              Sample size
            </div>
            <p className="mt-1.5 text-xl font-semibold tabular-nums tracking-tight">
              {previewResult ? formatNumber(sampleSize) : "—"}
            </p>
          </div>
        </div>

        {previewResult && (
          <Badge variant="secondary" className="w-fit">
            {previewResult.strategy} · {previewResult.entity_type}
          </Badge>
        )}

        <div className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Sample IDs
          </span>
          {sampleIds.length > 0 ? (
            <div className="max-h-52 space-y-1.5 overflow-y-auto">
              {displayIds.map((id) => (
                <code
                  key={id}
                  className="block truncate rounded-md border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-xs"
                >
                  {id}
                </code>
              ))}
              {sampleIds.length > 10 && (
                <p className="pt-1 text-xs text-muted-foreground">
                  + {formatNumber(sampleIds.length - 10)} more
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              Run the sample to see IDs
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export { INITIAL_STATE, INITIAL_FILTERS, INITIAL_LABELS };