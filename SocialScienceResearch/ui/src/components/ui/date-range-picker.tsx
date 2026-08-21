"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export interface DateRange {
  from?: string
  to?: string
}

const PRESETS: { label: string; days?: number; yearToDate?: boolean }[] = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "YTD", yearToDate: true },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - (days - 1));
  return d.toISOString().slice(0, 10);
}

function isoToday(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString().slice(0, 10);
}

function isoYearStart(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setMonth(0, 1);
  return d.toISOString().slice(0, 10);
}

export function DateRangePicker({
  value,
  onChange,
  className,
  fromLabel = "From",
  toLabel = "To",
}: {
  value?: DateRange
  onChange: (range: DateRange) => void
  className?: string
  fromLabel?: string
  toLabel?: string
}) {
  function applyPreset(preset: (typeof PRESETS)[number]) {
    if (preset.yearToDate) {
      onChange({ from: isoYearStart(), to: isoToday() });
    } else {
      onChange({ from: isoDaysAgo(preset.days ?? 0), to: isoToday() });
    }
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => applyPreset(preset)}
            className="h-6 rounded-md border border-input px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 space-y-1">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {fromLabel}
          </Label>
          <Input
            type="date"
            value={value?.from ?? ""}
            max={value?.to ?? undefined}
            onChange={(e) => onChange({ ...value, from: e.target.value || undefined })}
          />
        </div>
        <div className="flex-1 space-y-1">
          <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {toLabel}
          </Label>
          <Input
            type="date"
            value={value?.to ?? ""}
            min={value?.from ?? undefined}
            onChange={(e) => onChange({ ...value, to: e.target.value || undefined })}
          />
        </div>
      </div>
    </div>
  );
}
