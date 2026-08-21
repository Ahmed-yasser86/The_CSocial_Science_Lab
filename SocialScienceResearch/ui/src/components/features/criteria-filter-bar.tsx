"use client";

import { useState, useMemo } from "react";
import { X, Plus, SlidersHorizontal } from "lucide-react";
import { useResearchVariables } from "@/services/queries";
import type {
  QueryCondition,
  QueryGroup,
  QueryOperator,
  ResearchEntity,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

const _THIS_YEAR_START = new Date(new Date().getFullYear(), 0, 1)
  .toISOString()
  .split("T")[0];
const _RECENT_COMMENT_CUTOFF = new Date(
  Date.now() - 30 * 24 * 60 * 60 * 1000
).toISOString();

interface CriteriaFilterBarProps {
  entity: ResearchEntity;
  onChange: (group: QueryGroup) => void;
  initialGroup?: QueryGroup | null;
}

const NUMERIC_OPERATORS: { value: QueryOperator; label: string }[] = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
];

const STRING_OPERATORS: { value: QueryOperator; label: string }[] = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
  { value: "contains", label: "contains" },
  { value: "not_contains", label: "not contains" },
  { value: "in", label: "in" },
  { value: "not_in", label: "not in" },
];

const DATETIME_OPERATORS: { value: QueryOperator; label: string }[] = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
];

const BOOL_OPERATORS: { value: QueryOperator; label: string }[] = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
];

const LIST_OPERATORS: { value: QueryOperator; label: string }[] = [
  { value: "contains", label: "contains" },
  { value: "not_in", label: "not in" },
];

function getOperatorsForType(
  dataType: string | undefined,
): { value: QueryOperator; label: string }[] {
  if (!dataType) return STRING_OPERATORS;
  switch (dataType) {
    case "int":
    case "float":
      return NUMERIC_OPERATORS;
    case "datetime":
      return DATETIME_OPERATORS;
    case "bool":
      return BOOL_OPERATORS;
    case "list":
      return LIST_OPERATORS;
    default:
      return STRING_OPERATORS;
  }
}

function getInputType(dataType: string | undefined): "text" | "number" | "date" | "checkbox" {
  if (!dataType) return "text";
  switch (dataType) {
    case "int":
    case "float":
      return "number";
    case "datetime":
      return "date";
    case "bool":
      return "checkbox";
    default:
      return "text";
  }
}

interface Preset {
  label: string;
  group: QueryGroup;
}

export function CriteriaFilterBar({ entity, onChange, initialGroup }: CriteriaFilterBarProps) {
  const variablesQuery = useResearchVariables(entity);
  const variables = useMemo(() => variablesQuery.data ?? [], [variablesQuery.data]);

  const [conditions, setConditions] = useState<QueryCondition[]>(() => {
    if (initialGroup?.conditions) {
      return initialGroup.conditions.filter(
        (c): c is QueryCondition => !("operator" in c && "conditions" in c)
      );
    }
    return [];
  });
  const [draftVariable, setDraftVariable] = useState("");
  const [draftOperator, setDraftOperator] = useState<QueryOperator>("eq");
  const [draftValue, setDraftValue] = useState<string>("");

  const selectedMeta = useMemo(
    () => variables.find((v) => v.name === draftVariable),
    [variables, draftVariable],
  );

  const operators = useMemo(
    () => getOperatorsForType(selectedMeta?.data_type),
    [selectedMeta],
  );

  function emitChange(next: QueryCondition[]) {
    const group: QueryGroup = { operator: "AND", conditions: next };
    onChange(group);
  }

  function addCondition() {
    if (!draftVariable) return;
    const next: QueryCondition = {
      variable: draftVariable,
      operator: draftOperator,
    };
    const isInOperator = draftOperator === "in" || draftOperator === "not_in";
    if (draftOperator !== "is_null" && draftOperator !== "not_null" && draftValue !== "") {
      if (selectedMeta?.data_type === "int" || selectedMeta?.data_type === "float") {
        if (isInOperator) {
          next.values = draftValue.split(",").map((v) => Number(v.trim())).filter((v) => !Number.isNaN(v));
        } else {
          next.value = Number(draftValue);
        }
      } else if (selectedMeta?.data_type === "bool") {
        next.value = draftValue === "true";
      } else {
        if (isInOperator) {
          next.values = draftValue.split(",").map((v) => v.trim()).filter(Boolean);
        } else {
          next.value = draftValue;
        }
      }
    }
    const updated = [...conditions, next];
    setConditions(updated);
    emitChange(updated);
    setDraftVariable("");
    setDraftOperator("eq");
    setDraftValue("");
  }

  function removeCondition(index: number) {
    const updated = conditions.filter((_, i) => i !== index);
    setConditions(updated);
    emitChange(updated);
  }

  function applyPreset(preset: Preset) {
    const updated = [...conditions, ...preset.group.conditions] as QueryCondition[];
    setConditions(updated);
    emitChange(updated);
  }

  const presets: Preset[] = useMemo(() => {
    if (entity === "video") {
      return [
        {
          label: "Top 10% by views",
          group: { operator: "AND", conditions: [{ variable: "view_count", operator: "top_pct", value: 10 }] },
        },
        {
          label: "Long-form (>10min)",
          group: { operator: "AND", conditions: [{ variable: "duration", operator: "gt", value: 600 }] },
        },
        {
          label: "Shorts only",
          group: { operator: "AND", conditions: [{ variable: "is_short", operator: "eq", value: true }] },
        },
        {
          label: "High engagement",
          group: { operator: "AND", conditions: [{ variable: "like_count", operator: "gt", value: 1000 }] },
        },
        {
          label: "Published this year",
          group: { operator: "AND", conditions: [{ variable: "upload_date", operator: "gte", value: _THIS_YEAR_START }] },
        },
      ];
    }
    if (entity === "comment") {
      return [
        {
          label: "Many likes (>100)",
          group: { operator: "AND", conditions: [{ variable: "like_count", operator: "gt", value: 100 }] },
        },
        {
          label: "Recent",
          group: { operator: "AND", conditions: [{ variable: "published_at", operator: "gte", value: _RECENT_COMMENT_CUTOFF }] },
        },
      ];
    }
    return [];
  }, [entity]);

  const inputType = getInputType(selectedMeta?.data_type);
  const needsValue = draftOperator !== "is_null" && draftOperator !== "not_null";
  const isInOperator = draftOperator === "in" || draftOperator === "not_in";

  return (
    <div className="rounded-md border bg-muted/20 p-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <SlidersHorizontal className="size-3.5" aria-hidden />
          Criteria filters
        </span>
        {presets.length > 0 && (
          <div className="flex flex-wrap gap-1 ml-2">
            {presets.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => applyPreset(preset)}
                className="rounded-full border bg-background px-2 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {conditions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {conditions.map((cond, index) => (
            <Badge
              key={`${cond.variable}-${index}`}
              variant="secondary"
              className="inline-flex items-center gap-1.5 pl-2 pr-1.5 py-1 text-xs"
            >
              <span className="font-mono">{cond.variable}</span>
              <span className="text-muted-foreground">{cond.operator}</span>
              <span className="font-mono text-muted-foreground">
                {cond.operator === "in" || cond.operator === "not_in"
                  ? cond.values
                    ? cond.values.join(", ")
                    : "[]"
                  : cond.value === null || cond.value === undefined
                  ? "null"
                  : typeof cond.value === "boolean"
                  ? cond.value.toString()
                  : String(cond.value)}
              </span>
              <button
                type="button"
                onClick={() => removeCondition(index)}
                className="ml-0.5 rounded outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                aria-label={`Remove ${cond.variable} filter`}
              >
                <X className="size-3" aria-hidden />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {variables.length > 0 && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Variable
            </Label>
            <Select
              value={draftVariable}
              onValueChange={(value) => {
                setDraftVariable(value ?? "");
                const meta = variables.find((v) => v.name === value);
                if (meta) {
                  const ops = getOperatorsForType(meta.data_type);
                  if (!ops.find((o) => o.value === draftOperator)) {
                    setDraftOperator(ops[0]?.value ?? "eq");
                  }
                }
              }}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Select variable…" />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {variables.map((v) => (
                  <SelectItem key={v.name} value={v.name}>
                    {v.name} <span className="text-muted-foreground">({v.data_type})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Operator
            </Label>
            <Select
              value={draftOperator}
              onValueChange={(value) => setDraftOperator((value ?? "eq") as QueryOperator)}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {operators.map((op) => (
                  <SelectItem key={op.value} value={op.value}>
                    {op.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {needsValue && (
            <div className="space-y-1">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Value
              </Label>
              {inputType === "checkbox" ? (
                <div className="flex items-center gap-2 h-9">
                  <Checkbox
                    id="filter-bool-value"
                    checked={draftValue === "true"}
                    onCheckedChange={(v) => setDraftValue(v === true ? "true" : "false")}
                  />
                  <Label htmlFor="filter-bool-value" className="text-xs font-normal">
                    {draftValue === "true" ? "True" : "False"}
                  </Label>
                </div>
              ) : (
                <Input
                  type={inputType}
                  value={draftValue}
                  onChange={(e) => setDraftValue(e.target.value)}
                  placeholder={isInOperator ? "Comma-separated values" : "Value"}
                  className="w-48"
                  autoComplete="off"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCondition();
                    }
                  }}
                />
              )}
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addCondition}
            disabled={!draftVariable}
          >
            <Plus className="size-3.5" aria-hidden />
            Add
          </Button>

          {conditions.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setConditions([]);
                emitChange([]);
              }}
            >
              Clear all
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
