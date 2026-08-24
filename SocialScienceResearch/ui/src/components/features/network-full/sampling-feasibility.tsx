"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/features/state";
import {
  useSamplingFeasibility,
  type SamplingFeasibilityResponse,
} from "@/services/networkFull";

interface SamplingFeasibilityProps {
  defaultChannelId?: string;
  runIds?: string[];
}

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold">{value ?? "—"}</div>
    </div>
  );
}

function render(result: SamplingFeasibilityResponse) {
  const feasible =
    result.requested_size == null
      ? true
      : result.requested_size <= result.max_sample_size;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Population" value={result.population_size} />
        <Stat label="With metric" value={result.available_metric} />
        <Stat label="Coverage" value={
          result.coverage === null
            ? "—"
            : `${Math.round(result.coverage * 100)}%`
        } />
        <Stat label="Recommended" value={result.recommended_sample_size} />
      </div>
      <p
        className={
          feasible ? "text-xs text-emerald-600" : "text-xs text-destructive"
        }
      >
        {feasible
          ? `Requested sample of ${result.requested_size ?? result.population_size} is feasible (max ${result.max_sample_size}).`
          : `Requested sample of ${result.requested_size} exceeds population (${result.population_size}). Cap: ${result.max_sample_size}.`}
        {result.missing_metric > 0
          ? ` ${result.missing_metric} entities lack the ranking metric.`
          : ""}
      </p>
    </div>
  );
}

export function SamplingFeasibility({
  defaultChannelId,
  runIds,
}: SamplingFeasibilityProps) {
  const [entityType, setEntityType] = useState<string>("video");
  const [channelId, setChannelId] = useState<string>(defaultChannelId ?? "");
  const [metric, setMetric] = useState<string>("views");
  const [requested, setRequested] = useState<string>("");

  const { data, isLoading, isError, error, refetch } = useSamplingFeasibility({
    entity_type: entityType,
    channel_id: channelId || undefined,
    run_ids: runIds,
    metric,
    requested_size: requested ? Number(requested) : undefined,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          Sampling feasibility (US-32/33)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Entity</Label>
            <Select value={entityType} onValueChange={(v) => setEntityType(v ?? "video")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="video">Video</SelectItem>
                <SelectItem value="comment">Comment</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Channel</Label>
            <Input
              value={channelId}
              placeholder="channel_id"
              onChange={(e) => setChannelId(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Metric</Label>
            <Select value={metric} onValueChange={(v) => setMetric(v ?? "views")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="views">Views</SelectItem>
                <SelectItem value="likes">Likes</SelectItem>
                <SelectItem value="comments">Comments</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Requested size</Label>
            <Input
              type="number"
              min={0}
              value={requested}
              placeholder="optional"
              onChange={(e) => setRequested(e.target.value)}
            />
          </div>
        </div>
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : "Failed"}
            retry={() => refetch()}
          />
        ) : data ? (
          render(data)
        ) : null}
      </CardContent>
    </Card>
  );
}
