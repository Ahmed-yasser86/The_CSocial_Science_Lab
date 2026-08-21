"use client";

import { HelpCircle, Dices, Layers, Shuffle, Grid3x3, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { TopMetric } from "./LivePreview";
import type { ComponentType, ReactNode } from "react";

export type SamplingMethod = "full" | "random" | "stratified" | "topMetric";

export interface SamplingMethodProps {
  value: SamplingMethod;
  onChange: (method: SamplingMethod) => void;
  randomSize?: string;
  onRandomSizeChange?: (size: string) => void;
  randomPercent?: string;
  onRandomPercentChange?: (percent: string) => void;
  seed?: string;
  onSeedChange?: (seed: string) => void;
  strataVariable?: string;
  onStrataVariableChange?: (variable: string) => void;
  samplesPerStratum?: string;
  onSamplesPerStratumChange?: (count: string) => void;
  topMetric?: TopMetric;
  onTopMetricChange?: (metric: TopMetric) => void;
  topPercent?: string;
  onTopPercentChange?: (percent: string) => void;
}

const STRATA_VARIABLES = [
  { value: "month", label: "Upload Month" },
  { value: "weekday", label: "Upload Weekday" },
  { value: "channel", label: "Channel" },
  { value: "author", label: "Author" },
  { value: "views_quartile", label: "Views Quartile" },
];

const TOP_METRICS: { value: TopMetric; label: string }[] = [
  { value: "likes", label: "Most liked" },
  { value: "replies", label: "Most replied-to" },
  { value: "views", label: "Most viewed" },
  { value: "comments", label: "Most commented" },
];

function HelpTooltip({ content }: { content: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="inline-flex cursor-help" aria-label="Help" tabIndex={0} />
        }
      >
        <HelpCircle className="size-3.5 shrink-0 text-muted-foreground cursor-help" />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-64">
        <p>{content}</p>
      </TooltipContent>
    </Tooltip>
  );
}

function MethodOption({
  icon: Icon,
  title,
  description,
  selected,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  selected: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      data-selected={selected || undefined}
      className={cn(
        "flex flex-col gap-2 rounded-xl border p-4 transition-colors",
        selected
          ? "border-primary/50 bg-primary/[0.04]"
          : "border-border bg-background hover:bg-muted/40"
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg",
            selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="size-4" aria-hidden />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {selected && children ? <div className="pt-1">{children}</div> : null}
    </div>
  );
}

export function SamplingMethodSelector({
  value,
  onChange,
  randomSize,
  onRandomSizeChange,
  randomPercent,
  onRandomPercentChange,
  seed,
  onSeedChange,
  strataVariable,
  onStrataVariableChange,
  samplesPerStratum,
  onSamplesPerStratumChange,
  topMetric,
  onTopMetricChange,
  topPercent,
  onTopPercentChange,
}: SamplingMethodProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Dices className="size-4" aria-hidden />
          </span>
          <div>
            <CardTitle className="text-base font-semibold">
              Sampling Method
              <HelpTooltip content="Choose how to select records from the filtered population" />
            </CardTitle>
            <CardDescription>
              How records are drawn from the filtered population.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <RadioGroup value={value} onValueChange={onChange} className="grid gap-3">
          <RadioGroupItem value="full" className="grid w-full">
            <MethodOption
              icon={Layers}
              title="Full Population"
              description="Return all matching records. No sampling applied."
              selected={value === "full"}
            />
          </RadioGroupItem>

          <RadioGroupItem value="random" className="grid w-full">
            <MethodOption
              icon={Shuffle}
              title="Random Sample"
              description="Select a random subset of the population."
              selected={value === "random"}
            >
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Sample Size</Label>
                  <Input
                    type="number"
                    min={0}
                    value={randomSize ?? ""}
                    onChange={(e) => onRandomSizeChange?.(e.target.value)}
                    placeholder="500"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Or Percent (%)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={randomPercent ?? ""}
                    onChange={(e) => onRandomPercentChange?.(e.target.value)}
                    placeholder="10"
                  />
                </div>
                <div className="space-y-1.5 col-span-2">
                  <Label className="text-xs font-medium">Seed (optional)</Label>
                  <Input
                    type="number"
                    value={seed ?? ""}
                    onChange={(e) => onSeedChange?.(e.target.value)}
                    placeholder="Auto-generated"
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave blank for a new random seed each run.
                  </p>
                </div>
              </div>
            </MethodOption>
          </RadioGroupItem>

          <RadioGroupItem value="stratified" className="grid w-full">
            <MethodOption
              icon={Grid3x3}
              title="Stratified Sample"
              description="Balanced selection across groups (strata)."
              selected={value === "stratified"}
            >
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Stratification Variable</Label>
                  <Select
                    value={strataVariable ?? ""}
                    onValueChange={(val) => onStrataVariableChange?.(val ?? "")}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select variable" />
                    </SelectTrigger>
                    <SelectContent>
                      {STRATA_VARIABLES.map((v) => (
                        <SelectItem key={v.value} value={v.value}>
                          {v.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Samples Per Stratum</Label>
                  <Input
                    type="number"
                    min={1}
                    value={samplesPerStratum ?? ""}
                    onChange={(e) => onSamplesPerStratumChange?.(e.target.value)}
                    placeholder="50"
                  />
                </div>
              </div>
            </MethodOption>
          </RadioGroupItem>

          <RadioGroupItem value="topMetric" className="grid w-full">
            <MethodOption
              icon={TrendingUp}
              title="Top X% by Metric"
              description="Keep the top fraction of records ranked by likes, replies, views or comments."
              selected={value === "topMetric"}
            >
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Rank By</Label>
                  <Select
                    value={topMetric ?? "replies"}
                    onValueChange={(val) =>
                      onTopMetricChange?.((val ?? "replies") as TopMetric)
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TOP_METRICS.map((m) => (
                        <SelectItem key={m.value} value={m.value}>
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Top Percent (%)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={topPercent ?? ""}
                    onChange={(e) => onTopPercentChange?.(e.target.value)}
                    placeholder="10"
                  />
                </div>
                <div className="space-y-1.5 col-span-2">
                  <Label className="text-xs font-medium">Seed (optional)</Label>
                  <Input
                    type="number"
                    value={seed ?? ""}
                    onChange={(e) => onSeedChange?.(e.target.value)}
                    placeholder="Auto-generated"
                  />
                </div>
              </div>
            </MethodOption>
          </RadioGroupItem>
        </RadioGroup>
      </CardContent>
    </Card>
  );
}