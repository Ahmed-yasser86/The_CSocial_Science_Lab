"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NORMALIZATION_LABEL, type Normalization } from "@/lib/comparison-types";

const OPTIONS: Normalization[] = ["none", "per_1k", "z_score"];

export function NormalizationSelect({
  value,
  onChange,
}: {
  value: Normalization;
  onChange: (value: Normalization) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label
        htmlFor="normalization-select"
        className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
      >
        Normalization
      </Label>
      <Select
        value={value}
        onValueChange={(next) => onChange((next ?? "none") as Normalization)}
        items={OPTIONS.map((o) => ({ value: o, label: NORMALIZATION_LABEL[o] }))}
      >
        <SelectTrigger id="normalization-select" className="w-60">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {OPTIONS.map((option) => (
            <SelectItem key={option} value={option}>
              {NORMALIZATION_LABEL[option]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="max-w-xl text-xs text-muted-foreground">
        {value === "none"
          ? "Raw latest-observed values, untouched."
          : value === "per_1k"
            ? "Rate per 1,000 subscribers using each entity's own observed subscriber count."
            : "Z-scores computed over the compared set only — never over a hidden global population."}
      </p>
    </div>
  );
}
